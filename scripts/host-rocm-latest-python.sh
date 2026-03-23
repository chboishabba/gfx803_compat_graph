#!/usr/bin/env bash
# Wrapper to run a separately extracted ROCm latest Python environment on the host.
# This keeps latest experiments isolated from the known-good 6.4 and 5.7 artifact sets.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ARTIFACT_DIR="${ROCM_LATEST_OUTDIR:-$REPO_ROOT/artifacts/rocm-latest}"
COMPAT_DIR="$ARTIFACT_DIR/lib-compat"
VENV_DIR="$ARTIFACT_DIR/docker-venv"
VENV_PYTHON="$VENV_DIR/venv/bin/python"
VENV_PYTHON3="$VENV_DIR/venv/bin/python3"
VENV_LIB="$VENV_DIR/venv/lib"
CONDA_ROOT_PYTHON="$VENV_DIR/conda-python/bin/python"
CONDA_ROOT_LIB="$VENV_DIR/conda-python/lib"

shopt -s nullglob
CONDA_ENV_PYTHONS=("$VENV_DIR"/conda-python/envs/*/bin/python)
CONDA_ENV_LIBS=("$VENV_DIR"/conda-python/envs/*/lib)
shopt -u nullglob

if [ -x "$VENV_PYTHON" ]; then
  PYTHON_BIN="$VENV_PYTHON"
  PYTHON_HOME_CANDIDATE=""
elif [ -x "$VENV_PYTHON3" ]; then
  PYTHON_BIN="$VENV_PYTHON3"
  PYTHON_HOME_CANDIDATE=""
elif [ "${#CONDA_ENV_PYTHONS[@]}" -gt 0 ] && [ -x "${CONDA_ENV_PYTHONS[0]}" ]; then
  PYTHON_BIN="${CONDA_ENV_PYTHONS[0]}"
  PYTHON_HOME_CANDIDATE="$(dirname "$(dirname "$PYTHON_BIN")")"
elif [ -x "$CONDA_ROOT_PYTHON" ]; then
  PYTHON_BIN="$CONDA_ROOT_PYTHON"
  PYTHON_HOME_CANDIDATE="$VENV_DIR/conda-python"
else
  PYTHON_BIN=""
  PYTHON_HOME_CANDIDATE=""
fi

if [ ! -d "$COMPAT_DIR" ] || [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: ROCm latest compatibility libraries or python environment not extracted." >&2
  echo "Run scripts/extract-rocm-latest-artifacts.sh first." >&2
  exit 1
fi

LD_PATH_PREFIX="$COMPAT_DIR"
if [ -d "$VENV_LIB" ]; then
  LD_PATH_PREFIX="$VENV_LIB:$LD_PATH_PREFIX"
fi
for env_lib in "${CONDA_ENV_LIBS[@]}"; do
  if [ -d "$env_lib" ]; then
    LD_PATH_PREFIX="$env_lib:$LD_PATH_PREFIX"
  fi
done

export LD_LIBRARY_PATH="$LD_PATH_PREFIX${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-8.0.3}"
export ROC_ENABLE_PRE_VEGA="${ROC_ENABLE_PRE_VEGA:-1}"
export PYTORCH_ROCM_ARCH="${PYTORCH_ROCM_ARCH:-gfx803}"
export ROCM_ARCH="${ROCM_ARCH:-gfx803}"
export TORCH_BLAS_PREFER_HIPBLASLT="${TORCH_BLAS_PREFER_HIPBLASLT:-0}"

PATH_PREFIX="$VENV_DIR/venv/bin:$VENV_DIR/conda-python/bin"
for env_python in "${CONDA_ENV_PYTHONS[@]}"; do
  PATH_PREFIX="$(dirname "$env_python"):$PATH_PREFIX"
done

export PATH="$PATH_PREFIX:$PATH"
if [ -n "$PYTHON_HOME_CANDIDATE" ] && [ -d "$PYTHON_HOME_CANDIDATE" ]; then
  export PYTHONHOME="$PYTHON_HOME_CANDIDATE"
fi
export VIRTUAL_ENV="$VENV_DIR/venv"

exec "$PYTHON_BIN" "$@"
