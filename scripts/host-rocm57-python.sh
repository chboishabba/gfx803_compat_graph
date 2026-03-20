#!/usr/bin/env bash
# host-rocm57-python.sh
# Wrapper to run the extracted ROCm 5.7 Python environment on the host system.
# Unlike host-docker-python.sh, this keeps solver selection external so comparison
# profiles can override it cleanly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ARTIFACT_DIR="${ROCM57_OUTDIR:-$REPO_ROOT/artifacts/rocm57}"
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
    echo "ERROR: ROCm 5.7 compatibility libraries or python environment not extracted." >&2
    echo "Run scripts/extract-rocm57-artifacts.sh first." >&2
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
export PATH="$VENV_DIR/venv/bin:$VENV_DIR/conda-python/bin:$VENV_DIR/conda-python/envs/py_3.10/bin:$PATH"
if [ -n "$PYTHON_HOME_CANDIDATE" ] && [ -d "$PYTHON_HOME_CANDIDATE" ]; then
  export PYTHONHOME="$PYTHON_HOME_CANDIDATE"
fi
export VIRTUAL_ENV="$VENV_DIR/venv"

exec "$PYTHON_BIN" "$@"
