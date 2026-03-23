#!/usr/bin/env bash
# Wrapper to run the frozen control Python/framework layer against the
# 6.4-upgrade compatibility libraries. This keeps the control Python set
# untouched while swapping only the ROCm/runtime side underneath it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

PYTHON_ROOT="${ROCM64_CONTROL_PYTHON_ROOT:-$REPO_ROOT}"
COMPAT_ROOT="${ROCM64_UPGRADE_LIB_ROOT:-$REPO_ROOT/artifacts/rocm64-upgrade}"

COMPAT_DIR="$COMPAT_ROOT/lib-compat"
VENV_DIR="$PYTHON_ROOT/docker-venv"
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
  echo "ERROR: Frozen control Python/framework or upgrade compatibility libs not present." >&2
  echo "Expected python root: $PYTHON_ROOT" >&2
  echo "Expected compat root: $COMPAT_ROOT" >&2
  exit 1
fi

LD_PATH_PREFIX="$COMPAT_DIR"
if [ -d "$CONDA_ENV_LIB" ]; then
  LD_PATH_PREFIX="$CONDA_ENV_LIB:$LD_PATH_PREFIX"
fi

export LD_LIBRARY_PATH="$LD_PATH_PREFIX${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-8.0.3}"
export ROC_ENABLE_PRE_VEGA="${ROC_ENABLE_PRE_VEGA:-1}"
export PYTORCH_ROCM_ARCH="${PYTORCH_ROCM_ARCH:-gfx803}"
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
fi

exec "$PYTHON_BIN" "$@"
