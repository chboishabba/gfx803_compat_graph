#!/usr/bin/env bash
set -euo pipefail

ROCM_ROOT="${NATIVE_ROCM_ROOT:-/opt/rocm}"
OUT_ROOT="${NATIVE_ROCM_OUT_ROOT:-out/native-rocm-control}"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
RUN_ROOT="$OUT_ROOT/$STAMP"
mkdir -p "$RUN_ROOT"

if [ ! -d "$ROCM_ROOT" ]; then
  echo "ERROR: ROCm root not found: $ROCM_ROOT" >&2
  exit 1
fi

PACMAN_PACKAGES=()
if command -v pacman >/dev/null 2>&1; then
  mapfile -t PACMAN_PACKAGES < <(
    pacman -Q 2>/dev/null | grep -E '^(rocm|hsa|hip|roc)' || true
  )
  printf '%s\n' "${PACMAN_PACKAGES[@]}" > "$RUN_ROOT/pacman-rocm-packages.txt"
else
  : > "$RUN_ROOT/pacman-rocm-packages.txt"
fi

set +e
python stack_inventory.py "$ROCM_ROOT" --out "$RUN_ROOT/stack-inventory.json" \
  > "$RUN_ROOT/inventory.log" 2>&1
INVENTORY_RC=$?

if command -v rocminfo >/dev/null 2>&1; then
  rocminfo > "$RUN_ROOT/rocminfo.txt" 2>&1
  ROCMINFO_RC=$?
else
  ROCMINFO_RC=127
  echo "rocminfo not found" > "$RUN_ROOT/rocminfo.txt"
fi

python - <<'PY' > "$RUN_ROOT/torch-smoke.json" 2> "$RUN_ROOT/torch-smoke.err"
import json
try:
    import torch
except Exception as exc:
    print(json.dumps({"torch_import_ok": False, "error": repr(exc)}, sort_keys=True))
    raise SystemExit(2)

result = {
    "torch_import_ok": True,
    "torch_version": torch.__version__,
    "cuda_available": bool(torch.cuda.is_available()),
    "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
}
if result["device_count"]:
    result["device_name"] = torch.cuda.get_device_name(0)
    x = torch.arange(16, dtype=torch.float32, device="cuda")
    y = (x * x + 1).cpu()
    result["tiny_tensor_ok"] = bool(torch.equal(y, torch.arange(16, dtype=torch.float32) ** 2 + 1))
print(json.dumps(result, sort_keys=True))
PY
TORCH_RC=$?
set -e

PACKAGE_FINGERPRINT="$(sha256sum "$RUN_ROOT/pacman-rocm-packages.txt" | awk '{print $1}')"
cat > "$RUN_ROOT/source.env" <<EOF
lane=native-distro-control
claim_scope=local-machine-control
rocm_root=$ROCM_ROOT
package_fingerprint=$PACKAGE_FINGERPRINT
created_at=$(date -Iseconds)
EOF

export RUN_ROOT ROCM_ROOT PACKAGE_FINGERPRINT ROCMINFO_RC INVENTORY_RC TORCH_RC
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

packages = [
    line.strip()
    for line in (run_root / "pacman-rocm-packages.txt").read_text(encoding="utf-8").splitlines()
    if line.strip()
]

def status(rc):
    return "pass" if rc == 0 else "fail"

evidence = dict(inventory.get("inventory_evidence") or {})
evidence.update({
    "enumeration": "paid" if int(os.environ["ROCMINFO_RC"]) == 0 else "unpaid",
    "tiny_tensor_correctness": (
        "paid" if int(os.environ["TORCH_RC"]) == 0 and torch_smoke.get("tiny_tensor_ok") is True else "unpaid"
    ),
    "amd_release_ready": "unpaid",
})

manifest = {
    "release_id": "native-pacman:" + os.environ["PACKAGE_FINGERPRINT"],
    "stack_id": "native-distro-control",
    "reference_class": "local-machine-control",
    "source": {
        "rocm_root": os.environ["ROCM_ROOT"],
        "pacman_packages": packages,
        "package_fingerprint": os.environ["PACKAGE_FINGERPRINT"],
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
    "install_notes": ["Native distro ROCm control captured without mutating the installed stack."],
}
(run_root / "release-manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

cat <<EOF
Native ROCm control captured.
  ROCm root:     $ROCM_ROOT
  output:        $RUN_ROOT
  rocminfo rc:   $ROCMINFO_RC
  inventory rc:  $INVENTORY_RC
  torch rc:      $TORCH_RC
  manifest:      $RUN_ROOT/release-manifest.json

This capture does not modify /opt/rocm or installed packages.
EOF
