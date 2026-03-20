#!/usr/bin/env bash
# host-ollama-bundle.sh
# Run the extracted patched Ollama (6.4.3_0.11.5) on host with the bundled ROCm libs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

BUNDLE_DIR="${OLLAMA_BUNDLE_DIR:-$REPO_ROOT/artifacts/ollama_reference}"
OLLAMA_BIN="$BUNDLE_DIR/ollama-bin/ollama"
ROCM_LIB_DIR="$BUNDLE_DIR/rocm-6.4.3/lib"

if [ ! -x "$OLLAMA_BIN" ] || [ ! -d "$ROCM_LIB_DIR" ]; then
  echo "ERROR: Ollama bundle not found at $BUNDLE_DIR" >&2
  echo "Expected $OLLAMA_BIN and $ROCM_LIB_DIR" >&2
  exit 1
fi

# Polaris env
export HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-8.0.3}"
export ROC_ENABLE_PRE_VEGA="${ROC_ENABLE_PRE_VEGA:-1}"
export PYTORCH_ROCM_ARCH="${PYTORCH_ROCM_ARCH:-gfx803}"
export ROCM_ARCH="${ROCM_ARCH:-gfx803}"
export TORCH_BLAS_PREFER_HIPBLASLT="${TORCH_BLAS_PREFER_HIPBLASLT:-0}"

# Bundle runtime
export LD_LIBRARY_PATH="$ROCM_LIB_DIR:${LD_LIBRARY_PATH:-}"

exec "$OLLAMA_BIN" "$@"
