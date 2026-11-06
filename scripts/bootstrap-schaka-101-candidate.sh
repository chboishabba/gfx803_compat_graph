#!/usr/bin/env bash
# Resolve the published Schaka ROCm 10.1 gfx803 release to a verified immutable
# digest, then import a CANDIDATE Nix closure. No Docker daemon, compilation,
# local ROCm 6.4 mixing, training, publication or stable admission.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO"
TAG="rocm10.1-gfx803"
OUT=""
INSPECT_ONLY=0
while (($#)); do
  case "$1" in
    --out) OUT="${2:?missing output directory}"; shift 2;;
    --inspect-only) INSPECT_ONLY=1; shift;;
    --help|-h)
      cat <<'EOF'
Usage:
  nix develop .#gfx803-oci-build -c bash scripts/bootstrap-schaka-101-candidate.sh \
    --out out/schaka-oci/local-101
  ... --inspect-only --out out/schaka-oci/inspection-101

The fixed ROCm 10.1 gfx803 tag is inspected once, its manifest digest, full
publisher source revision, final-stage label, eight upstream pin graph and
SGEMM shim preload environment checked, and the digest used for import.
If the tag no longer matches nix/gfx803/upstream.json, this FAILS CLOSED
and tells the operator to update/review the source lock; it never changes it.
The physical runtime and LILA parity tests must run separately.
EOF
      exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done
[[ -n "$OUT" ]] || { echo "Required --out DIRECTORY" >&2; exit 2; }
OUT="$(realpath -m "$OUT")"
[[ ! -e "$OUT" ]] || { echo "Choose a fresh --out; existing evidence cannot be overwritten" >&2; exit 2; }
for program in skopeo python3; do
  command -v "$program" >/dev/null || {
    echo "Missing $program; launch inside nix develop .#gfx803-oci-build" >&2
    exit 2
  }
done
IMAGE=ghcr.io/schaka/rocm-migraphx-ort-torch-builder
mkdir -p "$OUT"
echo "Inspecting Schaka fixed tag $IMAGE:$TAG (metadata only)"
skopeo inspect --retry-times 3 --override-os linux --override-arch amd64 \
  "docker://$IMAGE:$TAG" >"$OUT/oci-inspect.json"

# Keep the digest and label check independent of image pull and importer;
# never use a floating tag after this point. No unreviewed source-lock edit.
PIN="$(python3 - "$OUT/oci-inspect.json" "$REPO/nix/gfx803/upstream.json" <<'PY'
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from scripts.gfx803_component_graph import parse_pins
from scripts.gfx803_oci_runtime_contract import inspect_runtime
image=json.loads(Path(sys.argv[1]).read_text())
lock=json.loads(Path(sys.argv[2]).read_text())
digest=image.get("Digest")
if not isinstance(digest,str) or not re.fullmatch(r"sha256:[0-9a-f]{64}",digest):
    raise SystemExit("INSPECTION FAILED: no immutable sha256 release image digest")
labels=image.get("Labels") or {}
expected={
    "io.rocm.gfx803.source-rev":lock["source_revision"],
    "io.rocm.gfx803.line":"rocm10.1",
    "io.rocm.gfx803.stage":"final",
}
for k,v in expected.items():
    if labels.get(k)!=v:
        raise SystemExit(
            f"PUBLISHED TAG DOES NOT MATCH PINNED SOURCE: {k} "
            f"actual={labels.get(k)!r}, locked={v!r}. "
            "Review upstream and change the source lock in a separate PR.")
parse_pins(labels.get("io.rocm.gfx803.pins"))
inspect_runtime(image)
if lock.get("image_digest") not in (None,digest):
    raise SystemExit("Inspected digest differs from checked-in image digest lock")
print(digest)
PY
)"
printf 'source=%s\ndigest=%s\ntag=%s\n' \
  "$(python3 -c 'import json;print(json.load(open("nix/gfx803/upstream.json"))["source_revision"])')" \
  "$PIN" "$TAG" >"$OUT/source-and-image.txt"
echo "Inspected and verified candidate immutable digest: $PIN"
if ((INSPECT_ONLY)); then
  echo "INSPECT-ONLY. No layers imported, no hardware or release admission."
  exit 0
fi
for program in nix umoci; do
  command -v "$program" >/dev/null || {
    echo "Missing $program; launch inside nix develop .#gfx803-oci-build" >&2
    exit 2
  }
done
# The importer re-fetches and verifies that SAME digest and all provenance;
# the staged environment is candidate-only until actual hardware checks.
SHA="$(python3 -c 'import json;print(json.load(open("nix/gfx803/upstream.json"))["source_revision"])')"
bash "$SCRIPT_DIR/import-schaka-oci-to-nix.sh" \
  --image "$IMAGE@$PIN" --source-revision "$SHA" \
  --out "$OUT/import" --with-venv

python3 - "$OUT/import/candidate.json" "$OUT/candidate-runtime-selector.json" <<'PY'
import json,sys
from pathlib import Path
data=json.loads(Path(sys.argv[1]).read_text())
rocm=Path(data["store_paths"]["rocm"])
venv=Path(data["store_paths"]["venv"])
if not str(rocm).startswith("/nix/store/") or not str(venv).startswith("/nix/store/"):
    raise SystemExit("Imported roots must be Nix store outputs")
shim=rocm/"lib/libgfx803_sgemm_shim.so"
if not shim.is_file():
    raise SystemExit("Imported Schaka image lacks exact SGEMM interposer")
candidates=[venv/"bin/python",venv/"bin/python3",venv/"venv/bin/python",
            venv/"venv/bin/python3"]
selection=[str(x) for x in candidates if x.is_file() and x.stat().st_mode & 0o111]
report={
    "state":"candidate-not-admitted",
    "immutable_image":data["image_ref"],
    "source_revision":data["upstream_revision"],
    "rocm_root":str(rocm),
    "venv_root":str(venv),
    "shim":str(shim),
    "python_candidates":selection,
    "chosen_python":selection[0] if len(selection)==1 else None,
    "runtime_execution_verified":False,
    "gpu_parity_verified":False,
    "note":"Select one real Python, run ABI and mapped-library probe before any LILA GPU work."
}
Path(sys.argv[2]).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print(json.dumps(report,indent=2,sort_keys=True))
PY
echo "CANDIDATE ONLY: inspect $OUT/candidate-runtime-selector.json"
