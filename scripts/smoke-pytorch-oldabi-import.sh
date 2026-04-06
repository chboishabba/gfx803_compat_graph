#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

TORCH_TREE="${TORCH_TREE:-$REPO_ROOT/artifacts/pytorch-framework-rebuild-oldabi-kinetooff/work/pytorch/torch}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/artifacts/pytorch-framework-rebuild-oldabi-kinetooff/venv/bin/python}"
WRAP_ROOT="${WRAP_ROOT:-${TMPDIR:-/tmp}/gfx803_torch_import_wrap}"
CC_BIN="${CC:-cc}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: python not found: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -d "$TORCH_TREE" ]]; then
  echo "ERROR: torch tree not found: $TORCH_TREE" >&2
  exit 1
fi

rm -rf "$WRAP_ROOT"
mkdir -p "$WRAP_ROOT"
cp -a "$TORCH_TREE" "$WRAP_ROOT/torch"
ln -s "$REPO_ROOT/artifacts/pytorch-framework-rebuild-oldabi-kinetooff/work/pytorch/torchgen" "$WRAP_ROOT/torchgen"
rm -rf "$WRAP_ROOT/torch/_C"
EXT_SUFFIX="$("$PYTHON_BIN" - <<'PY'
import sysconfig
print(sysconfig.get_config_var("EXT_SUFFIX") or ".so", end="")
PY
)"
PYTHON_INCLUDE="$("$PYTHON_BIN" - <<'PY'
import sysconfig
print(sysconfig.get_paths()["include"], end="")
PY
)"
if [[ -z "${AMDGPU_ASIC_ID_TABLE_PATHS:-}" ]]; then
  if [[ -f /usr/share/libdrm/amdgpu.ids ]]; then
    export AMDGPU_ASIC_ID_TABLE_PATHS="/usr/share/libdrm/amdgpu.ids"
  elif [[ -f /opt/amdgpu/share/libdrm/amdgpu.ids ]]; then
    export AMDGPU_ASIC_ID_TABLE_PATHS="/opt/amdgpu/share/libdrm/amdgpu.ids"
  fi
fi

"$CC_BIN" -shared -fPIC -O2 -I"$PYTHON_INCLUDE" \
  -o "$WRAP_ROOT/torch/_C${EXT_SUFFIX}" \
  "$REPO_ROOT/artifacts/pytorch-framework-rebuild-oldabi-kinetooff/work/pytorch/torch/csrc/stub.c" \
  -L"$REPO_ROOT/artifacts/pytorch-framework-rebuild-oldabi-kinetooff/build/lib" -ltorch_python

export PYTHONPATH="$WRAP_ROOT"
export LD_LIBRARY_PATH="$REPO_ROOT/artifacts/pytorch-framework-rebuild-oldabi-kinetooff/work/pytorch/torch/lib:$REPO_ROOT/artifacts/rocm64-upgrade-oldabi/lib-compat:$REPO_ROOT/artifacts/rocm64-oldabi-sdk/opt-rocm/lib:/usr/lib:/usr/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

STDERR_LOG="$WRAP_ROOT/import.stderr"
if "$PYTHON_BIN" - <<'PY' 2>"$STDERR_LOG"; then
import torch
print(torch.__version__)
print(torch.cuda.is_available())
PY
  rm -f "$STDERR_LOG"
else
  cat "$STDERR_LOG" >&2
  exit 1
fi
