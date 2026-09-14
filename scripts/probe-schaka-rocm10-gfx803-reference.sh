#!/usr/bin/env bash
set -euo pipefail

IMAGE="${SCHAKA_GFX803_IMAGE:-ghcr.io/schaka/rocm-migraphx-ort-torch-builder:rocm10.0-gfx803}"
OUT_ROOT="${SCHAKA_GFX803_OUT_ROOT:-out/rocm10-gfx803-reference}"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
RUN_ROOT="$OUT_ROOT/$STAMP"
mkdir -p "$RUN_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required" >&2
  exit 1
fi

cat > "$RUN_ROOT/source.env" <<EOF
lane=rocm10-gfx803-reference
claim_scope=reference-only
image=$IMAGE
created_at=$(date -Iseconds)
EOF

# Pulling is deliberate: this lane tests the published community artifact rather
# than rebuilding it locally. The resolved image ID/digest is retained below.
docker pull "$IMAGE" | tee "$RUN_ROOT/pull.log"
IMAGE_ID="$(docker image inspect "$IMAGE" --format '{{.Id}}')"
IMAGE_DIGEST="$(docker image inspect "$IMAGE" --format '{{join .RepoDigests ","}}')"
cat >> "$RUN_ROOT/source.env" <<EOF
image_id=$IMAGE_ID
image_digest=$IMAGE_DIGEST
EOF

DOCKER_ARGS=(
  --rm
  --device=/dev/kfd
  --device=/dev/dri
  --group-add video
  -v "$PWD:/workspace/gfx803_compat_graph:ro"
  -v "$RUN_ROOT:/workspace/out"
  -w /workspace/gfx803_compat_graph
)

set +e
docker run "${DOCKER_ARGS[@]}" "$IMAGE" bash -lc '
  set -o pipefail
  echo "=== rocminfo ==="
  (command -v rocminfo || true)
  rocminfo 2>&1
' > "$RUN_ROOT/rocminfo.txt" 2>&1
ROCMINFO_RC=$?

docker run "${DOCKER_ARGS[@]}" "$IMAGE" bash -lc '
  python stack_inventory.py /opt/rocm --out /workspace/out/stack-inventory.json
' > "$RUN_ROOT/inventory.log" 2>&1
INVENTORY_RC=$?

docker run "${DOCKER_ARGS[@]}" "$IMAGE" bash -lc '
  python - <<"PY"
import json
import torch
r = {
    "torch_version": torch.__version__,
    "cuda_available": bool(torch.cuda.is_available()),
    "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
}
if r["device_count"]:
    r["device_name"] = torch.cuda.get_device_name(0)
    x = torch.arange(16, dtype=torch.float32, device="cuda")
    y = (x * x + 1).cpu()
    r["tiny_tensor_ok"] = bool(torch.equal(y, torch.arange(16, dtype=torch.float32) ** 2 + 1))
print(json.dumps(r, sort_keys=True))
PY
' > "$RUN_ROOT/torch-smoke.json" 2> "$RUN_ROOT/torch-smoke.err"
TORCH_RC=$?
set -e

cat > "$RUN_ROOT/promotion.env" <<EOF
claim_scope=reference-only
rocminfo_exit=$ROCMINFO_RC
inventory_exit=$INVENTORY_RC
torch_smoke_exit=$TORCH_RC
amd_build_passing=not-claimed
amd_sanity_tested=not-claimed
amd_release_ready=not-claimed
EOF

export IMAGE IMAGE_ID IMAGE_DIGEST ROCMINFO_RC INVENTORY_RC TORCH_RC RUN_ROOT
python - <<'PY'
import json
import os
from pathlib import Path

run_root = Path(os.environ["RUN_ROOT"])
try:
    inventory = json.loads((run_root / "stack-inventory.json").read_text(encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError):
    inventory = {
        "components": {},
        "targets": [],
        "topology": {"agents": []},
        "inventory_evidence": {
            "elf_inventory": "unpaid",
            "gpu_target_inventory": "unpaid",
            "topology": "unpaid",
        },
        "inventory_errors": ["inventory output unavailable"],
    }

try:
    torch_smoke = json.loads((run_root / "torch-smoke.json").read_text(encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError):
    torch_smoke = {}

def status(rc):
    return "pass" if rc == 0 else "fail"

evidence = dict(inventory.get("inventory_evidence") or {})
evidence.update({
    "enumeration": "paid" if int(os.environ["ROCMINFO_RC"]) == 0 else "unpaid",
    "tiny_tensor_correctness": (
        "paid" if int(os.environ["TORCH_RC"]) == 0 and torch_smoke.get("tiny_tensor_ok") is True else "unpaid"
    ),
    "amd_build_passing": "unpaid",
    "amd_sanity_tested": "unpaid",
    "amd_release_ready": "unpaid",
})

manifest = {
    "release_id": os.environ["IMAGE_DIGEST"] or os.environ["IMAGE_ID"],
    "stack_id": "schaka-rocm10-gfx803-reference",
    "reference_class": "community-reference",
    "source": {
        "image": os.environ["IMAGE"],
        "image_id": os.environ["IMAGE_ID"],
        "image_digest": os.environ["IMAGE_DIGEST"],
        "claim_scope": "reference-only",
    },
    "components": inventory.get("components", {}),
    "targets": inventory.get("targets", []),
    "topology": inventory.get("topology", {"agents": []}),
    "patch_set": [],
    "benchmark_summary": {
        "statuses": {
            "enumeration": status(int(os.environ["ROCMINFO_RC"])),
            "stack_inventory": status(int(os.environ["INVENTORY_RC"])),
            "tiny_tensor": status(int(os.environ["TORCH_RC"])),
        }
    },
    "evidence": evidence,
    "inventory_errors": inventory.get("inventory_errors", []),
    "probe": torch_smoke,
    "install_notes": [
        "Reference-only Schaka ROCm 10 gfx803 image; community success is not AMD Release Ready."
    ],
}
(run_root / "release-manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

cat <<EOF
ROCm 10 gfx803 community-reference probe finished.
  image:        $IMAGE
  image id:     $IMAGE_ID
  output:       $RUN_ROOT
  rocminfo rc:  $ROCMINFO_RC
  inventory rc: $INVENTORY_RC
  torch rc:     $TORCH_RC
  manifest:     $RUN_ROOT/release-manifest.json

This is a reference-only receipt. Community success != AMD Release Ready.
EOF

if [ "$ROCMINFO_RC" -ne 0 ] || [ "$TORCH_RC" -ne 0 ]; then
  exit 1
fi
