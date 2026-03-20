#!/usr/bin/env bash
# host-docker-python.sh
# Wrapper to run the Docker-extracted Python venv on the host system.
# This ensures PyTorch runs with the ROCm 6.4 compatibility layer.

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
export HSA_OVERRIDE_GFX_VERSION=8.0.3
export ROC_ENABLE_PRE_VEGA=1
export PYTORCH_ROCM_ARCH=gfx803
export ROCM_ARCH=gfx803
export TORCH_BLAS_PREFER_HIPBLASLT=0
export MIOPEN_DEBUG_CONV_WINOGRAD=0
export MIOPEN_DEBUG_CONV_FFT=0
export MIOPEN_DEBUG_CONV_DIRECT=1
export MIOPEN_DEBUG_CONV_GEMM=0
export MIOPEN_DEBUG_CONV_DET=1
export MIOPEN_DEBUG_DISABLE_FIND_DB=1
export MIOPEN_FIND_ENFORCE=3
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export PATH="$VENV_DIR/venv/bin:$VENV_DIR/conda-python/bin:$VENV_DIR/conda-python/envs/py_3.10/bin:$PATH"
if [ -n "$PYTHON_HOME_CANDIDATE" ] && [ -d "$PYTHON_HOME_CANDIDATE" ]; then
  export PYTHONHOME="$PYTHON_HOME_CANDIDATE"
fi
export VIRTUAL_ENV="$VENV_DIR/venv"

exec "$PYTHON_BIN" "$@"
