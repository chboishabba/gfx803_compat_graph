#!/usr/bin/env bash
# Publish only hardware-admitted, digest-locked gfx803 closures with retained logs.
# Requires original evidence bytes; a self-asserted "accepted" JSON is not enough.
set -euo pipefail

usage() {
  echo "Usage: publish-gfx803-accepted.sh accepted-release.json --evidence-root LOG_DIR [--dry-run]" >&2
}
[[ $# -ge 3 ]] || { usage; exit 2; }
manifest="$1"
shift
evidence_root=''
dry_run=0
while (($#)); do
  case "$1" in
    --evidence-root) [[ $# -ge 2 ]] || { usage; exit 2; }
                     evidence_root="$2"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    *) usage; exit 2 ;;
  esac
done
[[ -n "$evidence_root" && -d "$evidence_root" ]] || {
  echo "NOT ADMITTED: real --evidence-root directory is mandatory" >&2
  exit 2
}
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Re-open and hash the ORIGINAL GPU/source/relocation test logs on publication.
# Match both the OCI pin and frozen release_source_lock.
paths_json="$(PYTHONPATH="$repo_root" python3 - "$manifest" "$evidence_root" <<'PY'
import json
import sys
from pathlib import Path
from scripts.gfx803_release import load, validate_candidate

manifest = load(sys.argv[1])
lock = manifest.get("release_source_lock", {})
if manifest.get("state") != "accepted":
    raise SystemExit("NOT ADMITTED: only accepted manifests may be published")
if manifest.get("official_amd_support") is not False:
    raise SystemExit("NOT ADMITTED: official support must not be asserted")
if manifest.get("admission_scope") != "tested-gfx803-hardware-and-declared-checks":
    raise SystemExit("NOT ADMITTED: unrecognized acceptance scope")
candidate = dict(manifest)
candidate["state"] = "validated"
errors = validate_candidate(candidate, lock, require_evidence=True,
                            evidence_root=Path(sys.argv[2]))
if errors:
    raise SystemExit("NOT ADMITTED: " + "; ".join(errors))
print(json.dumps([manifest["store_paths"][key]
                  for key in sorted(manifest["store_paths"])]))
PY
)"
mapfile -t paths < <(python3 -c 'import json,sys; print("\n".join(json.loads(sys.argv[1])))' "$paths_json")
[[ ${#paths[@]} -gt 0 ]] || { echo "No store paths to publish" >&2; exit 2; }
for path in "${paths[@]}"; do
  nix path-info "$path" >/dev/null || {
    echo "Missing local Nix closure: $path" >&2; exit 3
  }
done
if ((dry_run)); then
  printf 'Would publish admitted, evidence-verified closure: %s\n' "${paths[@]}"
  exit 0
fi
cache="${CACHIX_CACHE:-gfx803-rocm}"
cachix push "$cache" "${paths[@]}"
printf 'Evidence-verified closure(s) published to %s\n' "$cache"
