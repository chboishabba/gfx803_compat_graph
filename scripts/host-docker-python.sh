#!/usr/bin/env bash
# host-docker-python.sh
# Wrapper to run the Docker-extracted Python venv on the host system.
# This ensures PyTorch runs with the ROCm 6.4 compatibility layer.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ARTIFACT_DIR="${EXTRACTED_OUTDIR:-$REPO_ROOT}"
COMPAT_DIR="$ARTIFACT_DIR/lib-compat"
VENV_DIR="$ARTIFACT_DIR/docker-venv"
VENV_PYTHON="$VENV_DIR/venv/bin/python"
CONDA_ENV_PYTHON="$VENV_DIR/conda-python/envs/py_3.10/bin/python"
CONDA_ROOT_PYTHON="$VENV_DIR/conda-python/bin/python"
CONDA_PYTHONHOME="$VENV_DIR/conda-python"
CONDA_ENV_LIB="$VENV_DIR/conda-python/envs/py_3.10/lib"

if [ -x "$VENV_PYTHON" ]; then
    PYTHON_BIN="$VENV_PYTHON"
    PYTHON_HOME_CANDIDATE="$CONDA_PYTHONHOME"
elif [ -x "$CONDA_ENV_PYTHON" ]; then
    PYTHON_BIN="$CONDA_ENV_PYTHON"
    PYTHON_HOME_CANDIDATE="$VENV_DIR/conda-python/envs/py_3.10"
elif [ -x "$CONDA_ROOT_PYTHON" ]; then
    PYTHON_BIN="$CONDA_ROOT_PYTHON"
    PYTHON_HOME_CANDIDATE="$CONDA_PYTHONHOME"
else
    PYTHON_BIN=""
    PYTHON_HOME_CANDIDATE=""
fi

if [ ! -d "$COMPAT_DIR" ] || [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: Compatibility libraries or venv not extracted." >&2
    echo "Run scripts/extract-docker-libs.sh and ensure docker-venv is present." >&2
    exit 1
fi

LD_PATH_PREFIX="$COMPAT_DIR"
if [ -d "$CONDA_ENV_LIB" ]; then
  LD_PATH_PREFIX="$CONDA_ENV_LIB:$LD_PATH_PREFIX"
fi

export LD_LIBRARY_PATH="$LD_PATH_PREFIX${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-8.0.3}"
export ROC_ENABLE_PRE_VEGA="${ROC_ENABLE_PRE_VEGA:-1}"
export PYTORCH_ROCM_ARCH=gfx803
export ROCM_ARCH="${ROCM_ARCH:-gfx803}"
export TORCH_BLAS_PREFER_HIPBLASLT="${TORCH_BLAS_PREFER_HIPBLASLT:-0}"
if [ -z "${AMDGPU_ASIC_ID_TABLE_PATHS:-}" ]; then
  if [ -f /opt/amdgpu/share/libdrm/amdgpu.ids ]; then
    export AMDGPU_ASIC_ID_TABLE_PATHS="/opt/amdgpu/share/libdrm/amdgpu.ids"
  elif [ -f /usr/share/libdrm/amdgpu.ids ]; then
    export AMDGPU_ASIC_ID_TABLE_PATHS="/usr/share/libdrm/amdgpu.ids"
  fi
fi
export MIOPEN_DEBUG_CONV_WINOGRAD="${MIOPEN_DEBUG_CONV_WINOGRAD:-0}"
export MIOPEN_DEBUG_CONV_FFT="${MIOPEN_DEBUG_CONV_FFT:-0}"
export MIOPEN_DEBUG_CONV_DIRECT="${MIOPEN_DEBUG_CONV_DIRECT:-1}"
export MIOPEN_DEBUG_CONV_GEMM="${MIOPEN_DEBUG_CONV_GEMM:-0}"
export MIOPEN_DEBUG_CONV_DET="${MIOPEN_DEBUG_CONV_DET:-1}"
export MIOPEN_DEBUG_DISABLE_FIND_DB="${MIOPEN_DEBUG_DISABLE_FIND_DB:-1}"
export MIOPEN_FIND_ENFORCE="${MIOPEN_FIND_ENFORCE:-3}"
export CUBLAS_WORKSPACE_CONFIG="${CUBLAS_WORKSPACE_CONFIG:-:4096:8}"
export PATH="$VENV_DIR/venv/bin:$VENV_DIR/conda-python/bin:$VENV_DIR/conda-python/envs/py_3.10/bin:$PATH"
if [ -n "$PYTHON_HOME_CANDIDATE" ] && [ -d "$PYTHON_HOME_CANDIDATE" ]; then
  export PYTHONHOME="$PYTHON_HOME_CANDIDATE"
fi
export VIRTUAL_ENV="$VENV_DIR/venv"

if [ ! -e /dev/kfd ]; then
  echo "WARNING: /dev/kfd not present. HIP GPU devices may not be visible from this shell."
  echo "This wrapper can still run CPU-only PyTorch checks, but GPU checks will likely return false."
fi

if [ "${HOST_DOCKER_PYTHON_GPU_PRECHECK:-0}" = "1" ]; then
  echo "Running quick torch GPU precheck via $PYTHON_BIN"
  "${PYTHON_BIN}" -c 'import torch; print("is_available", torch.cuda.is_available()); print("device_count", torch.cuda.device_count())'
fi

WATCH_PID=""
if [ "${WATCH_AMDGPU_DEVCOREDUMP:-0}" = "1" ]; then
  if [ -f "$SCRIPT_DIR/watch-amdgpu-devcoredump.sh" ]; then
    CRASH_ROOT="${CRASH_OUTDIR_ROOT:-$SCRIPT_DIR/../out/crashlogs/live-watch}"
    mkdir -p "$CRASH_ROOT"
    CRASH_OUTDIR_ROOT="$CRASH_ROOT" POLL_INTERVAL="${POLL_INTERVAL:-0.05}" \
      bash "$SCRIPT_DIR/watch-amdgpu-devcoredump.sh" >"$CRASH_ROOT/host-docker-python-watch.log" 2>&1 &
    WATCH_PID="$!"
    echo "Started devcoredump watcher (pid=$WATCH_PID), writing to: $CRASH_ROOT"

    cleanup_watch() {
      if [[ -n "$WATCH_PID" ]] && kill -0 "$WATCH_PID" 2>/dev/null; then
        kill "$WATCH_PID" 2>/dev/null || true
        wait "$WATCH_PID" 2>/dev/null || true
      fi
    }
    trap cleanup_watch EXIT INT TERM
  else
    echo "Warning: watch-amdgpu-devcoredump.sh not found; skipping devcoredump capture."
  fi
fi

exec "$PYTHON_BIN" "$@"
