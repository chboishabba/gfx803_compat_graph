#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
  cat <<'USAGE'
Usage: run-gfx803-pytorch-framework-rebuild.sh [--prepare-only] [--torch-smoke-only]

Build driver for the first Nix-owned gfx803 framework rebuild lane.

Default behavior:
- uses the preserved old-ABI upgrade lane at artifacts/rocm64-upgrade-oldabi/lib-compat
- uses the preserved old-ABI ROCm SDK root at artifacts/rocm64-oldabi-sdk/opt-rocm
- creates a clean venv under artifacts/pytorch-framework-rebuild-latest/venv
- clones/updates:
  - ROCm/pytorch release/2.6
  - pytorch/vision release/0.21
  - pytorch/audio v2.6.0
- builds:
  - torch wheel
  - torchvision wheel
  - torchaudio wheel

Important:
- this is the first Nix-owned churn driver, not a proven good build yet
- logs and wheels are written under artifacts/pytorch-framework-rebuild-latest/
- the driver now carries conservative PyTorch build flags copied from later Docker attempts because the raw first build failed in `fbgemm` on `-Werror=maybe-uninitialized`

Environment overrides:
- FRAMEWORK_REBUILD_ROOT
- FRAMEWORK_REBUILD_RUNTIME_LIBDIR
- FRAMEWORK_REBUILD_ROCM_ROOT
- PYTORCH_GIT_VERSION
- TORCHVISION_GIT_VERSION
- TORCHAUDIO_GIT_VERSION
- MAX_JOBS
- FRAMEWORK_REBUILD_REQUIRE_CUDA
- FRAMEWORK_REBUILD_FORCE_TORCH_REBUILD
USAGE
}

PREPARE_ONLY=0
TORCH_SMOKE_ONLY=0
if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ "${1:-}" == "--prepare-only" ]]; then
  PREPARE_ONLY=1
fi
if [[ "${1:-}" == "--torch-smoke-only" ]]; then
  TORCH_SMOKE_ONLY=1
fi

BUILD_ROOT="${FRAMEWORK_REBUILD_ROOT:-$REPO_ROOT/artifacts/pytorch-framework-rebuild-latest}"
RUNTIME_LIBDIR="${FRAMEWORK_REBUILD_RUNTIME_LIBDIR:-$REPO_ROOT/artifacts/rocm64-upgrade-oldabi/lib-compat}"
ROCM_ROOT="${FRAMEWORK_REBUILD_ROCM_ROOT:-$REPO_ROOT/artifacts/rocm64-oldabi-sdk/opt-rocm}"
WORKDIR="$BUILD_ROOT/work"
DISTDIR="$BUILD_ROOT/dist"
LOGDIR="$BUILD_ROOT/logs"
VENV_DIR="$BUILD_ROOT/venv"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"

PYTORCH_GIT_VERSION="${PYTORCH_GIT_VERSION:-release/2.6}"
TORCHVISION_GIT_VERSION="${TORCHVISION_GIT_VERSION:-release/0.21}"
TORCHAUDIO_GIT_VERSION="${TORCHAUDIO_GIT_VERSION:-v2.6.0}"
MAX_JOBS="${MAX_JOBS:-$(nproc)}"
FRAMEWORK_REBUILD_REQUIRE_CUDA="${FRAMEWORK_REBUILD_REQUIRE_CUDA:-1}"
FRAMEWORK_REBUILD_FORCE_TORCH_REBUILD="${FRAMEWORK_REBUILD_FORCE_TORCH_REBUILD:-0}"

mkdir -p "$WORKDIR" "$DISTDIR" "$LOGDIR"

if [ ! -d "$RUNTIME_LIBDIR" ]; then
  echo "ERROR: runtime lib dir not found: $RUNTIME_LIBDIR" >&2
  echo "Run scripts/create-rocm64-upgrade-oldabi-lane.sh first." >&2
  exit 1
fi
if [ ! -d "$ROCM_ROOT" ]; then
  echo "ERROR: ROCm root not found: $ROCM_ROOT" >&2
  echo "Run scripts/extract-rocm64-oldabi-sdk.sh first." >&2
  exit 1
fi

export HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-8.0.3}"
export ROC_ENABLE_PRE_VEGA="${ROC_ENABLE_PRE_VEGA:-1}"
export PYTORCH_ROCM_ARCH="${PYTORCH_ROCM_ARCH:-gfx803}"
export ROCM_ARCH="${ROCM_ARCH:-gfx803}"
export TORCH_BLAS_PREFER_HIPBLASLT="${TORCH_BLAS_PREFER_HIPBLASLT:-0}"
export USE_CUDA="${USE_CUDA:-0}"
export USE_ROCM="${USE_ROCM:-1}"
export USE_NINJA="${USE_NINJA:-1}"
export FORCE_CUDA="${FORCE_CUDA:-1}"
export USE_KINETO="${USE_KINETO:-0}"
export BUILD_TEST="${BUILD_TEST:-0}"
export USE_NNPACK="${USE_NNPACK:-0}"
export USE_TENSORPIPE="${USE_TENSORPIPE:-0}"
export USE_DISTRIBUTED="${USE_DISTRIBUTED:-0}"
export USE_RPC="${USE_RPC:-0}"
export USE_SYSTEM_PROTOBUF="${USE_SYSTEM_PROTOBUF:-1}"
export BUILD_CUSTOM_PROTOBUF="${BUILD_CUSTOM_PROTOBUF:-OFF}"
export CXXFLAGS="${CXXFLAGS:--Wno-error=maybe-uninitialized} -U_GLIBCXX_ASSERTIONS -D_GLIBCXX_ASSERTIONS=0"
export HIPFLAGS="${HIPFLAGS:-} -U_GLIBCXX_ASSERTIONS -D_GLIBCXX_ASSERTIONS=0"
export CMAKE_ARGS="${CMAKE_ARGS:-} -DCMAKE_HIP_FLAGS:STRING=-U_GLIBCXX_ASSERTIONS\\ -D_GLIBCXX_ASSERTIONS=0"
export MAX_JOBS
export PYTHONNOUSERSITE=1
export PYTHONPATH=
export PATH="$ROCM_ROOT/bin${PATH:+:$PATH}"
export HIP_PATH="$ROCM_ROOT"
export ROCM_PATH="$ROCM_ROOT"
export CMAKE_PREFIX_PATH="$ROCM_ROOT${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
export LIBRARY_PATH="$ROCM_ROOT/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
export CMAKE_LIBRARY_PATH="$ROCM_ROOT/lib${CMAKE_LIBRARY_PATH:+:$CMAKE_LIBRARY_PATH}"
export CMAKE_INCLUDE_PATH="$ROCM_ROOT/include${CMAKE_INCLUDE_PATH:+:$CMAKE_INCLUDE_PATH}"
export CPATH="$ROCM_ROOT/include${CPATH:+:$CPATH}"
export CPLUS_INCLUDE_PATH="$ROCM_ROOT/include${CPLUS_INCLUDE_PATH:+:$CPLUS_INCLUDE_PATH}"
export PKG_CONFIG_PATH="$ROCM_ROOT/lib/pkgconfig:$ROCM_ROOT/share/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export LD_LIBRARY_PATH="$RUNTIME_LIBDIR:$ROCM_ROOT/lib"

prepend_ld_dir() {
  local candidate="$1"
  if [ -n "$candidate" ] && [ -d "$candidate" ]; then
    case ":${LD_LIBRARY_PATH:-}:" in
      *":$candidate:"*) ;;
      *) export LD_LIBRARY_PATH="$candidate${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ;;
    esac
  fi
}

discover_missing_lib_dirs() {
  local log_path="$1"
  shift
  local -a targets=("$@")
  local -a search_roots=()
  local -a missing_libs=()
  local -a resolved_dirs=()
  local changed=1

  search_roots+=("$RUNTIME_LIBDIR" "$ROCM_ROOT/lib")
  for extra in /usr/lib /usr/lib64 /lib /lib64; do
    if [ -d "$extra" ]; then
      search_roots+=("$extra")
    fi
  done

  : > "$log_path"
  while [ "$changed" -eq 1 ]; do
    changed=0
    mapfile -t resolved_dirs < <(
      ldd "${targets[@]}" 2>/dev/null \
        | awk '/=> \// {print $3}' \
        | xargs -r -n1 dirname \
        | sort -u
    )
    for resolved_dir in "${resolved_dirs[@]}"; do
      prepend_ld_dir "$resolved_dir"
    done

    mapfile -t missing_libs < <(
      ldd "${targets[@]}" 2>/dev/null \
        | awk '/=> not found/ {print $1}' \
        | sort -u
    )

    if [ "${#missing_libs[@]}" -eq 0 ]; then
      break
    fi

    {
      echo "missing libs:"
      printf '  %s\n' "${missing_libs[@]}"
    } >> "$log_path"

    for libname in "${missing_libs[@]}"; do
      local found=""
      for root in "${search_roots[@]}"; do
        if [ -f "$root/$libname" ]; then
          found="$root/$libname"
          break
        fi
      done
      if [ -n "$found" ]; then
        prepend_ld_dir "$(dirname "$found")"
        echo "resolved $libname -> $found" >> "$log_path"
        changed=1
      else
        echo "unresolved $libname" >> "$log_path"
      fi
    done
  done

  {
    echo "final_ld_library_path=$LD_LIBRARY_PATH"
    echo "final_ldd:"
    ldd "${targets[@]}" 2>/dev/null || true
  } >> "$log_path"
}

if [ -f /usr/lib/libgomp.so.1 ]; then
  prepend_ld_dir /usr/lib
fi
if command -v c++ >/dev/null 2>&1; then
  LIBGOMP_PATH="$(c++ -print-file-name=libgomp.so.1 2>/dev/null || true)"
  if [ -n "$LIBGOMP_PATH" ] && [ "$LIBGOMP_PATH" != "libgomp.so.1" ] && [ -f "$LIBGOMP_PATH" ]; then
    prepend_ld_dir "$(dirname "$LIBGOMP_PATH")"
  fi
fi

find_and_prepend_runtime_lib() {
  local libname="$1"
  local found=""
  while IFS= read -r candidate; do
    found="$candidate"
    break
  done < <(find /usr/lib /usr/lib64 /lib /lib64 /nix/store -maxdepth 3 -name "$libname" 2>/dev/null)
  if [ -n "$found" ]; then
    prepend_ld_dir "$(dirname "$found")"
  fi
}

# ROCm's bundled LLVM tools depend on host libs like libxml2 that are not part of
# the extracted SDK closure on this machine.
find_and_prepend_runtime_lib "libxml2.so.2"

assert_rocm_resolution() {
  local log_path="$1"
  local bad=0
  local -a allowed_rocm_dirs=("$RUNTIME_LIBDIR" "$ROCM_ROOT/lib" "$TORCH_SITE_ROOT/lib")
  local pattern='^(libamdhip64|libhsa-runtime64|libhiprtc|libhiprtc-builtins|libMIOpen|librocblas|libamd_comgr|librocm-core|libhipblas|libhipblaslt|libhipsparse|libhipsolver|librocsolver|librocsparse|libroctx64|libhipfft|libhiprand|librccl|libmagma|librocfft|librocrand|libroctracer64|librocm_smi64|librocprofiler-register)'

  while IFS= read -r line; do
    [[ "$line" == *"=>"* ]] || continue
    local libname resolved_path ok=0
    libname="$(awk '{print $1}' <<<"$line")"
    resolved_path="$(awk '/=> \// {print $3}' <<<"$line")"
    [[ -n "$resolved_path" ]] || continue
    if ! grep -Eq "$pattern" <<<"$libname"; then
      continue
    fi
    for allowed in "${allowed_rocm_dirs[@]}"; do
      if [[ "$resolved_path" == "$allowed/"* ]]; then
        ok=1
        break
      fi
    done
    if [ "$ok" -ne 1 ]; then
      echo "bad_rocm_resolution $libname -> $resolved_path" >> "$log_path"
      bad=1
    fi
  done < <(ldd "${TORCH_DEP_TARGETS[@]}" 2>/dev/null || true)

  if [ "$bad" -ne 0 ]; then
    echo "ERROR: old-ABI rebuild leaked ROCm dependencies outside the intended roots." >&2
    echo "See $log_path" >&2
    exit 1
  fi
}

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel ninja

ensure_repo() {
  local url="$1"
  local ref="$2"
  local dir="$3"
  if [ ! -d "$dir/.git" ]; then
    git clone --recursive -b "$ref" "$url" "$dir"
  else
    git -C "$dir" fetch --tags origin
    git -C "$dir" checkout "$ref"
    git -C "$dir" submodule update --init --recursive
  fi
}

ensure_repo "https://github.com/ROCm/pytorch.git" "$PYTORCH_GIT_VERSION" "$WORKDIR/pytorch"
ensure_repo "https://github.com/pytorch/vision.git" "$TORCHVISION_GIT_VERSION" "$WORKDIR/vision"
ensure_repo "https://github.com/pytorch/audio.git" "$TORCHAUDIO_GIT_VERSION" "$WORKDIR/audio"

cat > "$BUILD_ROOT/meta.env" <<EOF
created_at=$STAMP
runtime_libdir=$RUNTIME_LIBDIR
rocm_root=$ROCM_ROOT
pytorch_ref=$PYTORCH_GIT_VERSION
torchvision_ref=$TORCHVISION_GIT_VERSION
torchaudio_ref=$TORCHAUDIO_GIT_VERSION
max_jobs=$MAX_JOBS
build_test=$BUILD_TEST
use_nnpack=$USE_NNPACK
use_tensorpipe=$USE_TENSORPIPE
use_distributed=$USE_DISTRIBUTED
use_rpc=$USE_RPC
use_system_protobuf=$USE_SYSTEM_PROTOBUF
build_custom_protobuf=$BUILD_CUSTOM_PROTOBUF
cxxflags=$CXXFLAGS
framework_rebuild_require_cuda=$FRAMEWORK_REBUILD_REQUIRE_CUDA
framework_rebuild_force_torch_rebuild=$FRAMEWORK_REBUILD_FORCE_TORCH_REBUILD
torch_smoke_only=$TORCH_SMOKE_ONLY
EOF

if [ "$PREPARE_ONLY" = "1" ]; then
  echo "Prepared framework rebuild workspace at $BUILD_ROOT"
  exit 0
fi

find_latest_torch_wheel() {
  find "$DISTDIR" -maxdepth 1 -type f -name 'torch-*.whl' | sort | tail -n1
}

TORCH_WHEEL_PATH="$(find_latest_torch_wheel || true)"

if [ "$FRAMEWORK_REBUILD_FORCE_TORCH_REBUILD" = "1" ] || [ -z "$TORCH_WHEEL_PATH" ]; then
  (
    cd "$WORKDIR/pytorch"
    python -m pip install -r requirements.txt
    python tools/amd_build/build_amd.py
    python setup.py clean
    python setup.py bdist_wheel
    cp -v dist/torch*.whl "$DISTDIR/"
  ) 2>&1 | tee "$LOGDIR/${STAMP}-torch.log"
  TORCH_WHEEL_PATH="$(find_latest_torch_wheel)"
else
  {
    echo "Reusing existing torch wheel:"
    echo "  $TORCH_WHEEL_PATH"
  } | tee "$LOGDIR/${STAMP}-torch.log"
fi

python -m pip uninstall -y torch torchvision torchaudio || true
python -m pip install "$TORCH_WHEEL_PATH"

TORCH_SITE_ROOT="$VENV_DIR/lib/python3.12/site-packages/torch"
prepend_ld_dir "$TORCH_SITE_ROOT/lib"
TORCH_DEP_TARGETS=(
  "$TORCH_SITE_ROOT/lib/libtorch_global_deps.so"
  "$TORCH_SITE_ROOT/lib/libtorch_hip.so"
  "$TORCH_SITE_ROOT/_C.cpython-312-x86_64-linux-gnu.so"
)
discover_missing_lib_dirs "$LOGDIR/${STAMP}-torch-ldd.log" "${TORCH_DEP_TARGETS[@]}"
assert_rocm_resolution "$LOGDIR/${STAMP}-torch-ldd.log"

python - <<'PY' 2>&1 | tee "$LOGDIR/${STAMP}-torch-smoke.log"
import os
import sys
import torch

cuda_ok = torch.cuda.is_available()
print(f"torch_version={torch.__version__}")
print(f"torch_cuda_available={cuda_ok}")

if os.environ.get("FRAMEWORK_REBUILD_REQUIRE_CUDA", "1") == "1" and not cuda_ok:
    sys.exit("torch smoke gate failed: torch.cuda.is_available() == False")
PY

if [ "$TORCH_SMOKE_ONLY" = "1" ]; then
  echo "Torch smoke-only mode finished."
  exit 0
fi

(
  cd "$WORKDIR/vision"
  export PYTHONNOUSERSITE=1
  export PYTHONPATH=
  python setup.py bdist_wheel
  cp -v dist/torchvision-*.whl "$DISTDIR/"
) 2>&1 | tee "$LOGDIR/${STAMP}-torchvision.log"

python -m pip install "$DISTDIR"/torchvision-*.whl

(
  cd "$WORKDIR/audio"
  python setup.py bdist_wheel
  cp -v dist/torchaudio-*.whl "$DISTDIR/"
) 2>&1 | tee "$LOGDIR/${STAMP}-torchaudio.log"

echo "Framework rebuild finished. Outputs:"
echo "  wheels: $DISTDIR"
echo "  logs:   $LOGDIR"
