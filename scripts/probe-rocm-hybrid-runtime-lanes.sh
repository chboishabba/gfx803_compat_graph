#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

HYBRID_ROOT="${HYBRID_ROOT:-$REPO_ROOT/artifacts/rocm-runtime-hybrids}"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/artifacts/pytorch-framework-rebuild-latest/venv}"
OUT_ROOT="${OUT_ROOT:-$REPO_ROOT/out/rocm-hybrid-runtime-probes}"

usage() {
  cat <<'USAGE'
Usage: probe-rocm-hybrid-runtime-lanes.sh [lane...]

Runs two checks for each hybrid lane:
  1. rocminfo probe
  2. rebuilt-torch import / GPU-visibility probe

Logs are written under out/rocm-hybrid-runtime-probes/<timestamp>/<lane>/.
USAGE
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -d "$HYBRID_ROOT" ]]; then
  echo "ERROR: hybrid root not found: $HYBRID_ROOT" >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "ERROR: rebuild venv not found: $VENV_DIR" >&2
  exit 1
fi

STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
RUN_ROOT="$OUT_ROOT/$STAMP"
mkdir -p "$RUN_ROOT"

if [[ "$#" -eq 0 ]]; then
  mapfile -t LANES < <(find "$HYBRID_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
else
  LANES=("$@")
fi

GOMP="$(c++ -print-file-name=libgomp.so.1 2>/dev/null || true)"
GOMP_DIR=""
if [[ -n "$GOMP" && "$GOMP" != "libgomp.so.1" && -f "$GOMP" ]]; then
  GOMP_DIR="$(dirname "$GOMP")"
fi

for lane in "${LANES[@]}"; do
  lane_dir="$HYBRID_ROOT/$lane"
  if [[ ! -d "$lane_dir" ]]; then
    echo "ERROR: lane not found: $lane_dir" >&2
    exit 1
  fi

  out_dir="$RUN_ROOT/$lane"
  mkdir -p "$out_dir"

  (
    export LD_LIBRARY_PATH="$lane_dir"
    export HSA_OVERRIDE_GFX_VERSION=8.0.3
    export ROC_ENABLE_PRE_VEGA=1
    rocminfo
  ) > "$out_dir/rocminfo.txt" 2>&1 || true

  (
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
    export HSA_OVERRIDE_GFX_VERSION=8.0.3
    export ROC_ENABLE_PRE_VEGA=1
    export PYTORCH_ROCM_ARCH=gfx803
    export ROCM_ARCH=gfx803
    export TORCH_BLAS_PREFER_HIPBLASLT=0
    export LD_LIBRARY_PATH="$VENV_DIR/lib/python3.12/site-packages/torch/lib:$lane_dir:/opt/rocm/lib:/usr/lib${GOMP_DIR:+:$GOMP_DIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    python - <<'PY'
import torch
print(f"torch_version={torch.__version__}")
print(f"torch_cuda_available={torch.cuda.is_available()}")
print(f"torch_device_count={torch.cuda.device_count()}")
PY
  ) > "$out_dir/torch.txt" 2>&1 || true

  {
    echo "lane=$lane"
    echo "rocminfo_head:"
    sed -n '1,12p' "$out_dir/rocminfo.txt"
    echo
    echo "torch_probe:"
    cat "$out_dir/torch.txt"
  } > "$out_dir/summary.txt"

  echo "Wrote $out_dir/summary.txt"
done

echo "Wrote hybrid runtime probe logs under $RUN_ROOT"
