#!/usr/bin/env bash
# run-ollama-reference-host.sh
# Run the extracted Robert Ollama reference payload on the host with the
# required ROCm 6.4 gfx803 compatibility runtime and environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
OUTDIR="${OLLAMA_OUTDIR:-$REPO_ROOT/artifacts/ollama_reference}"

OLLAMA_BIN="$OUTDIR/ollama-bin/ollama"
OLLAMA_LIB="$OUTDIR/ollama-bin/build/lib/ollama"
ROCM_LIBS="$OUTDIR/rocm-6.4.3/lib"
AMDGPU_LIBS="$OUTDIR/opt/amdgpu/lib/x86_64-linux-gnu"
PATCH_MARKER="$OUTDIR/ollama-bin/discover/gpu.go"

if [ ! -x "$OLLAMA_BIN" ]; then
  echo "ERROR: Ollama binary not found or not executable: $OLLAMA_BIN" >&2
  echo "Run: bash scripts/extract-ollama-reference-artifacts.sh" >&2
  exit 1
fi

if [ ! -f "$OLLAMA_LIB/libggml-hip.so" ] || [ ! -f "$PATCH_MARKER" ]; then
  echo "ERROR: Extracted Ollama GPU artifacts are incomplete." >&2
  echo "Run: bash scripts/extract-ollama-reference-artifacts.sh" >&2
  exit 1
fi

export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-8.0.3}"
export ROC_ENABLE_PRE_VEGA="${ROC_ENABLE_PRE_VEGA:-1}"
export HSA_ENABLE_SDMA="${HSA_ENABLE_SDMA:-0}"
export ROCM_PATH="$OUTDIR/rocm-6.4.3"
if [ -z "${AMDGPU_ASIC_ID_TABLE_PATHS:-}" ]; then
  if [ -f /opt/amdgpu/share/libdrm/amdgpu.ids ]; then
    export AMDGPU_ASIC_ID_TABLE_PATHS="/opt/amdgpu/share/libdrm/amdgpu.ids"
  elif [ -f /usr/share/libdrm/amdgpu.ids ]; then
    export AMDGPU_ASIC_ID_TABLE_PATHS="/usr/share/libdrm/amdgpu.ids"
  fi
fi

if [ -d "$OLLAMA_LIB" ] || [ -d "$ROCM_LIBS" ] || [ -d "$AMDGPU_LIBS" ]; then
  export LD_LIBRARY_PATH="$OLLAMA_LIB:$ROCM_LIBS:$AMDGPU_LIBS:${LD_LIBRARY_PATH:-}"
fi

exec "$OLLAMA_BIN" "$@"
