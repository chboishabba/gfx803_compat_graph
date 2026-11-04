#!/usr/bin/env bash
# Publish only already-admitted gfx803 Nix store closures to Cachix.
set -euo pipefail
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: publish-gfx803-accepted.sh <accepted-release.json> [--dry-run]" >&2
  exit 2
fi
manifest="$1"
dry_run="${2:-}"
[[ -z "$dry_run" || "$dry_run" == "--dry-run" ]] || exit 2
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
lock="$repo_root/nix/gfx803/upstream.json"

# Validate in a separate invocation with explicit PYTHONPATH and capture output.
paths_json="$(PYTHONPATH="$repo_root" python3 - "$manifest" "$lock" <<'PY'
import json
import sys
from scripts.gfx803_release import load, validate_candidate, AdmissionError

manifest, lock = load(sys.argv[1]), load(sys.argv[2])
if manifest.get("state") != "accepted":
    raise SystemExit("NOT ADMITTED: only accepted manifests may be published")
if manifest.get("official_amd_support") is not False:
    raise SystemExit("NOT ADMITTED: official support must not be asserted")
candidate = dict(manifest)
candidate["state"] = "validated"
errors = validate_candidate(candidate, lock, require_evidence=True)
if errors:
    raise SystemExit("NOT ADMITTED: " + "; ".join(errors))
print(json.dumps([manifest["store_paths"][key]
                  for key in sorted(manifest["store_paths"])]))
PY
)"
mapfile -t paths < <(python3 -c 'import json,sys; print("\n".join(json.loads(sys.argv[1])))' "$paths_json")
if [[ ${#paths[@]} -eq 0 ]]; then
  echo "No store paths to publish" >&2
  exit 2
fi
for path in "${paths[@]}"; do
  nix path-info "$path" >/dev/null || {
    echo "Missing local closure $path" >&2
    exit 3
  }
done
if [[ "$dry_run" == "--dry-run" ]]; then
  printf 'Would publish accepted closure: %s\n' "${paths[@]}"
  exit 0
fi
cache="${CACHIX_CACHE:-gfx803-rocm}"
cachix push "$cache" "${paths[@]}"
printf 'Accepted closure(s) published to %s\n' "$cache"
