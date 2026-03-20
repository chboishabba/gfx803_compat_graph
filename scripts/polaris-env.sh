#!/usr/bin/env bash
# polaris-env.sh
# Source this script to activate the Polaris (gfx803) ROCm 6.4 compat environment
# on a host that has a newer ROCm in Nix (which doesn't support gfx803).
#
# Prerequisites: Run scripts/extract-docker-libs.sh first.
#
# Usage: source scripts/polaris-env.sh
#        # Then run probes, drift matrix, etc.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
COMPAT_DIR="$REPO_ROOT/lib-compat"

if [ ! -f "$COMPAT_DIR/libhsa-runtime64.so.1" ]; then
  echo "ERROR: lib-compat/ not populated. Run: bash scripts/extract-docker-libs.sh"
  return 1 2>/dev/null || exit 1
fi

# ── ROCm 6.4 compat (gfx803 HSA unlock) ─────────────────────────────────────
export LD_LIBRARY_PATH="$COMPAT_DIR:$LD_LIBRARY_PATH"

# ── Polaris GPU identity ──────────────────────────────────────────────────────
export HSA_OVERRIDE_GFX_VERSION=8.0.3
export ROC_ENABLE_PRE_VEGA=1

# ── Architecture targeting ────────────────────────────────────────────────────
export PYTORCH_ROCM_ARCH=gfx803
export ROCM_ARCH=gfx803
export TORCH_BLAS_PREFER_HIPBLASLT=0

# ── MIOpen stability (Polaris zero-drift baseline) ────────────────────────────
export MIOPEN_DEBUG_CONV_WINOGRAD=0    # Prevent GPU ring timeouts/hangs
export MIOPEN_DEBUG_CONV_FFT=0         # Extra safety margin
export MIOPEN_DEBUG_CONV_DIRECT=1      # Force the known zero-drift solver family
export MIOPEN_DEBUG_CONV_GEMM=0        # Disable GemmFwdRest (the ~0.15 drift culprit)
export MIOPEN_DEBUG_CONV_DET=1         # Force deterministic solver selection
export MIOPEN_DEBUG_DISABLE_FIND_DB=1  # Bypass stale/poisoned solver cache
export MIOPEN_FIND_ENFORCE=3           # Speed up startup with stable selection

# ── Determinism ───────────────────────────────────────────────────────────────
export CUBLAS_WORKSPACE_CONFIG=:4096:8

# ── Output directory ──────────────────────────────────────────────────────────
export DRIFT_RESULTS_DIR="$REPO_ROOT/out"
mkdir -p "$DRIFT_RESULTS_DIR"

echo "✓ Polaris (gfx803) ROCm 6.4 compat environment active"
echo "  LD_LIBRARY_PATH includes: $COMPAT_DIR"
echo "  HSA_OVERRIDE_GFX_VERSION=8.0.3"
echo "  Direct-only zero-drift baseline enabled (MIOPEN_DEBUG_CONV_DIRECT=1)"
echo "  GemmFwdRest disabled (MIOPEN_DEBUG_CONV_GEMM=0)"
echo ""
echo "Quick check: rocminfo | grep -E 'gfx|Marketing Name'"
