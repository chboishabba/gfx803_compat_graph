#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

CONTROL_ROOT="${CONTROL_ROOT:-$REPO_ROOT}"
HOST_WRAPPER="${HOST_WRAPPER:-$REPO_ROOT/scripts/host-docker-python.sh}"
RUNTIME_ROOT="${RUNTIME_ROOT:-$REPO_ROOT/out/patcher-runtime/gfx803-patcher-v1}"
ROCMINFO_BIN="${ROCMINFO_BIN:-rocminfo}"

VALIDATE=1
RUN_AFTER_VALIDATE=1
PRINT_RULE=0

usage() {
  cat <<'EOF'
Usage:
  scripts/apply-gfx803-patcher-v1.sh [options] [-- command...]

Purpose:
  Assemble and enforce PATCHER_RULE_V1 for gfx803 by staging the known-good
  extracted control runtime island:
    - lib-compat/
    - docker-venv/

  Validation is explicit:
    1. rocminfo must pass under the staged lib-compat island
    2. torch.cuda.is_available() must be true under host-docker-python.sh

Options:
  --runtime-root PATH   Override the staged runtime root.
  --control-root PATH   Override the source root that provides lib-compat/
                        and docker-venv/.
  --host-wrapper PATH   Override the Python wrapper. Default:
                        scripts/host-docker-python.sh
  --rocminfo-bin PATH   Override the rocminfo binary name/path.
  --skip-validate       Stage the runtime root but skip validation.
  --validate-only       Stage and validate, then exit without running a command.
  --print-rule          Print PATCHER_RULE_V1 and exit.
  -h, --help            Show this help.

Examples:
  scripts/apply-gfx803-patcher-v1.sh --validate-only
  scripts/apply-gfx803-patcher-v1.sh -- -c 'import torch; print(torch.cuda.device_count())'
  scripts/apply-gfx803-patcher-v1.sh -- -m whisperx /path/to/audio --model small --compute_type int8 --language en
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

print_rule() {
  cat <<'EOF'
PATCHER_RULE_V1
OLD_CORE = full lib-compat/
SAFE_NEW = none by default
ENV_RULES = use host-docker-python.sh with the extracted control runtime island
VALIDATION = rocminfo pass + torch.cuda.is_available() == True
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --runtime-root)
      RUNTIME_ROOT="$2"
      shift 2
      ;;
    --control-root)
      CONTROL_ROOT="$2"
      shift 2
      ;;
    --host-wrapper)
      HOST_WRAPPER="$2"
      shift 2
      ;;
    --rocminfo-bin)
      ROCMINFO_BIN="$2"
      shift 2
      ;;
    --skip-validate)
      VALIDATE=0
      shift
      ;;
    --validate-only)
      RUN_AFTER_VALIDATE=0
      shift
      ;;
    --print-rule)
      PRINT_RULE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

if [[ "$PRINT_RULE" -eq 1 ]]; then
  print_rule
  exit 0
fi

COMMAND=("$@")

COMPAT_DIR="$CONTROL_ROOT/lib-compat"
VENV_DIR="$CONTROL_ROOT/docker-venv"

[[ -d "$COMPAT_DIR" ]] || die "missing control lib-compat: $COMPAT_DIR"
[[ -d "$VENV_DIR" ]] || die "missing control docker-venv: $VENV_DIR"
[[ -x "$HOST_WRAPPER" ]] || die "missing host wrapper: $HOST_WRAPPER"

mkdir -p "$RUNTIME_ROOT"
ln -sfn "$(realpath "$COMPAT_DIR")" "$RUNTIME_ROOT/lib-compat"
ln -sfn "$(realpath "$VENV_DIR")" "$RUNTIME_ROOT/docker-venv"

cat > "$RUNTIME_ROOT/PATCHER_RULE_V1.txt" <<EOF
rule=PATCHER_RULE_V1
old_core=$(realpath "$COMPAT_DIR")
safe_new=none_by_default
host_wrapper=$(realpath "$HOST_WRAPPER")
validation=rocminfo_pass_and_torch_cuda_available_true
EOF

if [[ "$VALIDATE" -eq 1 ]]; then
  LOG_DIR="$RUNTIME_ROOT/validation/$(date +%Y-%m-%dT%H-%M-%S)"
  mkdir -p "$LOG_DIR"

  if [[ ! -e /dev/kfd ]]; then
    die "/dev/kfd is not present; run this from the real host runtime"
  fi

  if ! command -v "$ROCMINFO_BIN" >/dev/null 2>&1; then
    die "rocminfo not found: $ROCMINFO_BIN"
  fi

  echo "Running rocminfo validation..."
  env \
    LD_LIBRARY_PATH="$RUNTIME_ROOT/lib-compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-8.0.3}" \
    ROC_ENABLE_PRE_VEGA="${ROC_ENABLE_PRE_VEGA:-1}" \
    PYTORCH_ROCM_ARCH="${PYTORCH_ROCM_ARCH:-gfx803}" \
    ROCM_ARCH="${ROCM_ARCH:-gfx803}" \
    TORCH_BLAS_PREFER_HIPBLASLT="${TORCH_BLAS_PREFER_HIPBLASLT:-0}" \
    "$ROCMINFO_BIN" >"$LOG_DIR/rocminfo.txt" 2>&1 || {
      echo "rocminfo validation failed; see $LOG_DIR/rocminfo.txt" >&2
      exit 1
    }

  echo "Running torch GPU visibility validation..."
  EXTRACTED_OUTDIR="$RUNTIME_ROOT" \
    bash "$HOST_WRAPPER" -c 'import torch; print("torch_cuda_available", torch.cuda.is_available()); print("torch_device_count", torch.cuda.device_count()); raise SystemExit(0 if torch.cuda.is_available() else 2)' \
    >"$LOG_DIR/torch.txt" 2>&1 || {
      echo "torch validation failed; see $LOG_DIR/torch.txt" >&2
      exit 1
    }

  {
    echo "runtime_root=$RUNTIME_ROOT"
    echo "control_root=$(realpath "$CONTROL_ROOT")"
    echo "rocminfo_status=pass"
    echo "torch_status=pass"
    echo "host_wrapper=$(realpath "$HOST_WRAPPER")"
  } > "$LOG_DIR/summary.txt"

  echo "Validation passed."
  echo "Logs: $LOG_DIR"
fi

if [[ "$RUN_AFTER_VALIDATE" -eq 0 || "${#COMMAND[@]}" -eq 0 ]]; then
  echo "Runtime root ready: $RUNTIME_ROOT"
  exit 0
fi

echo "Executing command through PATCHER_RULE_V1 runtime..."
exec env EXTRACTED_OUTDIR="$RUNTIME_ROOT" bash "$HOST_WRAPPER" "${COMMAND[@]}"
