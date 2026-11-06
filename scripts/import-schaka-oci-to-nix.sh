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
repo_root="${GFX803_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
scripts_dir="${GFX803_SCRIPTS_DIR:-$repo_root/scripts}"
lock_path="${GFX803_SOURCE_LOCK:-$repo_root/nix/gfx803/upstream.json}"
export PYTHONPATH="$repo_root:$scripts_dir${PYTHONPATH:+:$PYTHONPATH}"
[[ -f "$lock_path" ]] || { echo "Missing checked-in Schaka source lock" >&2; exit 2; }
read -r locked_sha rocm_version locked_digest < <(python3 - "$lock_path" <<'PY'
import json,sys
lock=json.load(open(sys.argv[1]))
print(lock["source_revision"], lock["rocm_version"], lock.get("image_digest") or "unlocked")
PY
)
[[ "$SOURCE_REV" == "$locked_sha" ]] || {
  echo "Selected Schaka commit differs from checked-in source lock." >&2
  exit 2
}
if [[ "$locked_digest" != "unlocked" && "$IMAGE" != "ghcr.io/schaka/rocm-migraphx-ort-torch-builder@$locked_digest" ]]; then
  echo "Image digest differs from the committed upstream lock." >&2
  exit 2
fi
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

# The original container layers may be large.  The OCI layout may be kept on
# NAS (GFX803_OCI_LAYOUT_DIR) for retry/reuse, but umoci itself must unpack on
# a local xattr-capable filesystem: NFS rejects its OCI xattr cleanup.  Only
# selected extracted subtrees enter Nix's store; no OCI archive is a consumer
# runtime dependency.
local_scratch_root="${GFX803_LOCAL_SCRATCH:-/var/tmp}"
[[ -d "$local_scratch_root" && -w "$local_scratch_root" ]] || {
  echo "GFX803_LOCAL_SCRATCH must be a writable local filesystem directory" >&2
  exit 2
}
scratch="$(mktemp -d "$local_scratch_root/gfx803-schaka-oci.XXXXXX")"
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$OUT"
oci_layout="${GFX803_OCI_LAYOUT_DIR:-$OUT/oci-layout}"
# Schaka stamps the final image with build-line, component, upstream revision
# and resolved upstream dependency pins. Check them BEFORE pulling the layers.
skopeo inspect --override-os linux --override-arch amd64 \
  "docker://$IMAGE" > "$OUT/oci-inspect.json"
PYTHONPATH="$repo_root" python3 - "$OUT/oci-inspect.json" "$SOURCE_REV" "$rocm_version" "$IMAGE" <<'PY'
import json
import sys
try:
    from scripts.gfx803_component_graph import parse_pins
except ModuleNotFoundError:
    from gfx803_component_graph import parse_pins
try:
    from scripts.gfx803_oci_runtime_contract import inspect_runtime
except ModuleNotFoundError:
    from gfx803_oci_runtime_contract import inspect_runtime

payload = json.load(open(sys.argv[1]))
labels = payload.get("Labels") or {}
rev = sys.argv[2]
mm = ".".join(sys.argv[3].split(".")[:2])
requested = sys.argv[4].split("@", 1)[1]
if payload.get("Digest") != requested:
    raise SystemExit("OCI DIGEST MISMATCH: inspected digest differs from requested immutable ref")
expected = {
    "io.rocm.gfx803.source-rev": rev,
    "io.rocm.gfx803.line": "rocm" + mm,
    "io.rocm.gfx803.stage": "final",
}
for name, value in expected.items():
    if labels.get(name) != value:
        raise SystemExit("OCI LABEL MISMATCH: " + name + ": " + repr(labels.get(name)))
try:
    parse_pins(labels.get("io.rocm.gfx803.pins"))
except ValueError as exc:
    raise SystemExit("OCI LABEL MISMATCH: incomplete source pin graph: " + str(exc))
try:
    inspect_runtime(payload)
except ValueError as exc:
    raise SystemExit("OCI RUNTIME ENV MISMATCH: " + str(exc))
print("Source, release, final-stage, eight source pins and SGEMM shim runtime contract match")
PY

echo "Fetching immutable, matching OCI image digest: $IMAGE"
# The host need not have a containers/image policy.json.  Content integrity is
# still fail-closed here: IMAGE is an already re-inspected sha256 reference and
# the earlier manifest check requires that exact digest.  This bypasses only a
# missing local signature-policy configuration, not the immutable content pin.
if [[ -e "$oci_layout/index.json" ]]; then
  cached_digest="$(skopeo inspect --override-os linux --override-arch amd64 \
    "oci:$oci_layout:locked" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("Digest", ""))')"
  [[ "$cached_digest" == "${IMAGE#*@}" ]] || {
    echo "Existing OCI layout does not match the requested immutable digest: $oci_layout" >&2
    exit 2
  }
  echo "Reusing verified OCI layout: $oci_layout"
else
  [[ ! -e "$oci_layout" ]] || {
    echo "OCI layout directory exists without index.json; choose a fresh layout path" >&2
    exit 2
  }
  mkdir -p "$oci_layout"
  skopeo copy --insecure-policy --override-os linux --override-arch amd64 \
    "docker://$IMAGE" "oci:$oci_layout:locked"
fi
# OCI blobs are ordinary files, so copy the retained NAS layout into local
# scratch before umoci performs xattr-sensitive rootfs extraction.
mkdir -p "$scratch/layout"
cp -R "$oci_layout/." "$scratch/layout/"
umoci unpack --rootless --image "$scratch/layout:locked" "$scratch/unpacked"

root="$scratch/unpacked/rootfs"
[[ -d "$root/opt/rocm" ]] || { echo "No /opt/rocm in image" >&2; exit 3; }
# The published image uses /etc/alternatives/rocm-* symlinks to
# /opt/rocm/core-10.1; copying /opt/rocm verbatim breaks these links.
# Resolve ONLY aliases that terminate within the selected OCI tree.
# External links remain a reported, unverified candidate liability.
python3 "$scripts_dir/gfx803_oci_links.py" \
  --rootfs "$root" --tree /opt/rocm --out "$scratch/staged-rocm" \
  --report "$OUT/rocm-links.json"
rocm_store="$(nix store add-path "$scratch/staged-rocm")"
python3 "$scripts_dir/gfx803_oci_runtime_contract.py" \
  --inspect "$OUT/oci-inspect.json" --stage "$scratch/staged-rocm" \
  --store "$rocm_store" --out "$OUT/runtime-env.json"
venv_store=''
if ((WITH_VENV)); then
  [[ -d "$root/opt/venv" ]] || { echo "No /opt/venv in image" >&2; exit 3; }
  python3 "$scripts_dir/gfx803_oci_links.py" \
    --rootfs "$root" --tree /opt/venv --out "$scratch/staged-venv" \
    --report "$OUT/venv-links.json"
  venv_store="$(nix store add-path "$scratch/staged-venv")"
fi

OCI_IMAGE="$IMAGE" SCHAKA_SOURCE_REV="$SOURCE_REV" \
  ROCM_STORE="$rocm_store" VENV_STORE="$venv_store" ROCM_VERSION="$rocm_version" \
  OCI_INSPECT="$OUT/oci-inspect.json" OCI_LINKS="$OUT/rocm-links.json" \
  VENV_LINKS="$OUT/venv-links.json" \
  OUT_MANIFEST="$OUT/candidate.json" python3 - <<'PY'
import json
import os
from pathlib import Path

labels = json.loads(Path(os.environ["OCI_INSPECT"]).read_text())["Labels"]
link_report = json.loads(Path(os.environ["OCI_LINKS"]).read_text())
venv_report = (json.loads(Path(os.environ["VENV_LINKS"]).read_text())
               if Path(os.environ["VENV_LINKS"]).is_file() else None)
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
        "upstream_commit_correspondence": "publisher-oci-labels-matched",
        "publisher_image_labels": "oci-inspect.json",
        "published_source_revision": labels["io.rocm.gfx803.source-rev"],
        "published_release_line": labels["io.rocm.gfx803.line"],
        "published_component_pins": labels["io.rocm.gfx803.pins"],
        "runtime_relocation": "unverified",
        "original_runtime_env_contract": "runtime-env.json",
        "required_sgemm_shim_preload": os.environ["ROCM_STORE"] + "/lib/libgfx803_sgemm_shim.so",
        "sgemm_shim_loaded_and_correct": "unverified",
        "rocm_symlink_relocation_report": "rocm-links.json",
        "rocm_unresolved_symlinks": len(link_report["unresolved"]),
        "venv_symlink_relocation_report": ("venv-links.json" if venv_report else None),
        "venv_unresolved_symlinks": (len(venv_report["unresolved"]) if venv_report else None),
    },
    "evidence": {},
    "hardware": {},
}
Path(os.environ["OUT_MANIFEST"]).write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

python3 "$scripts_dir/gfx803_component_graph.py" \
  --candidate "$OUT/candidate.json" --out "$OUT/component-sources.json"
echo "Imported into Nix store: $rocm_store"
[[ -z "$venv_store" ]] || echo "Python environment: $venv_store"
echo "Candidate manifest: $OUT/candidate.json"
echo "NOT PROMOTED. Runtime shim captured structurally; ELF/venv relocation, preload execution, and GPU correctness remain unverified."
