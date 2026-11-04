#!/usr/bin/env bash
# Bootstrap Schaka's already-built, digest-pinned OCI payload into Nix store.
# No docker daemon, package installation, Nixpkgs ROCm mixing, or stable promotion.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: import-schaka-oci-to-nix.sh --image ghcr.io/schaka/rocm-migraphx-ort-torch-builder@sha256:<digest>
                                   --source-revision <Schaka-commit-sha>
                                   [--out DIR] [--with-venv] [--dry-run]

Downloads by immutable OCI digest through skopeo, unpacks rootlessly using umoci,
imports selected /opt trees into the Nix store, and writes a CANDIDATE manifest.
This is binary-import provenance, NOT a native-from-source Nix build. Do not
describe these paths as validated or relocatable until separate checks succeed.
EOF
}

IMAGE=''
SOURCE_REV=''
OUT=''
WITH_VENV=0
DRY_RUN=0
while (($#)); do
  case "$1" in
    --image) IMAGE="${2:?missing image}"; shift 2 ;;
    --source-revision) SOURCE_REV="${2:?missing revision}"; shift 2 ;;
    --out) OUT="${2:?missing output}"; shift 2 ;;
    --with-venv) WITH_VENV=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! "$IMAGE" =~ ^ghcr[.]io/schaka/rocm-migraphx-ort-torch-builder@sha256:[0-9a-f]{64}$ ]]; then
  echo "An immutable Schaka image digest is required; floating tags are refused." >&2
  exit 2
fi
if [[ ! "$SOURCE_REV" =~ ^[0-9a-f]{40}$ ]]; then
  echo "A full pinned Schaka git commit is required." >&2
  exit 2
fi
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
lock_path="$repo_root/nix/gfx803/upstream.json"
[[ -f "$lock_path" ]] || { echo "Missing checked-in Schaka source lock" >&2; exit 2; }
read -r locked_sha rocm_version < <(python3 - "$lock_path" <<'PY'
import json,sys
lock=json.load(open(sys.argv[1]))
print(lock["source_revision"], lock["rocm_version"])
PY
)
[[ "$SOURCE_REV" == "$locked_sha" ]] || {
  echo "Selected Schaka commit differs from checked-in source lock." >&2
  exit 2
}
OUT="${OUT:-out/schaka-oci/${SOURCE_REV:0:12}}"
if ((DRY_RUN)); then
  printf 'dry-run: pinned image=%s source=%s output=%s venv=%s\n' \
    "$IMAGE" "$SOURCE_REV" "$OUT" "$WITH_VENV"
  exit 0
fi

for tool in skopeo umoci nix python3 mktemp; do
  command -v "$tool" >/dev/null || {
    echo "Missing $tool (use nix develop .#gfx803-oci-build)" >&2
    exit 2
  }
done

# The original container layers may be large. Only selected extracted subtrees
# enter Nix's store; no image/OCI archive is retained in the consumer closure.
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/layout"
echo "Fetching immutable OCI image digest: $IMAGE"
skopeo copy --override-os linux --override-arch amd64 \
  "docker://$IMAGE" "oci:$scratch/layout:locked"
umoci unpack --rootless --image "$scratch/layout:locked" "$scratch/unpacked"

root="$scratch/unpacked/rootfs"
[[ -d "$root/opt/rocm" ]] || { echo "No /opt/rocm in image" >&2; exit 3; }
rocm_store="$(nix store add-path "$root/opt/rocm")"
venv_store=''
if ((WITH_VENV)); then
  [[ -d "$root/opt/venv" ]] || { echo "No /opt/venv in image" >&2; exit 3; }
  venv_store="$(nix store add-path "$root/opt/venv")"
fi

mkdir -p "$OUT"
# Source labels and transfer metadata are evidence, not an automatic provenance
# endorsement. A future validator must compare recorded source labels and pins.
skopeo inspect --override-os linux --override-arch amd64 \
  "docker://$IMAGE" > "$OUT/oci-inspect.json"

OCI_IMAGE="$IMAGE" SCHAKA_SOURCE_REV="$SOURCE_REV" \
  ROCM_STORE="$rocm_store" VENV_STORE="$venv_store" ROCM_VERSION="$rocm_version" \
  OUT_MANIFEST="$OUT/candidate.json" python3 - <<'PY'
import json
import os
from pathlib import Path

store_paths = {"rocm": os.environ["ROCM_STORE"]}
if os.environ["VENV_STORE"]:
    store_paths["venv"] = os.environ["VENV_STORE"]
manifest = {
    "schema_version": 1,
    "upstream_revision": os.environ["SCHAKA_SOURCE_REV"],
    "rocm_version": os.environ["ROCM_VERSION"],
    "image_ref": os.environ["OCI_IMAGE"],
    "store_paths": store_paths,
    "state": "candidate",
    "provenance": {
        "origin": "Schaka OCI binary import",
        "native_nix_build": False,
        "upstream_commit_correspondence": "unverified",
        "runtime_relocation": "unverified",
    },
    "evidence": {},
    "hardware": {},
}
Path(os.environ["OUT_MANIFEST"]).write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

echo "Imported into Nix store: $rocm_store"
[[ -z "$venv_store" ]] || echo "Python environment: $venv_store"
echo "Candidate manifest: $OUT/candidate.json"
echo "NOT PROMOTED. Imported /opt paths may need ELF/venv relocation."
