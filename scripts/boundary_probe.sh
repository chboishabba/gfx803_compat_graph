#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

OLD_LIB_ROOT="${OLD_LIB_ROOT:-$REPO_ROOT/lib-compat}"
NEW_LIB_ROOT="${NEW_LIB_ROOT:-$REPO_ROOT/artifacts/rocm-latest/lib-compat}"
HOST_PYTHON_WRAPPER="${HOST_PYTHON_WRAPPER:-$REPO_ROOT/scripts/host-docker-python.sh}"
VENV_PYTHON="${VENV_PYTHON:-$REPO_ROOT/docker-venv/venv/bin/python}"
OUT_ROOT="${OUT_ROOT:-$REPO_ROOT/out/boundary-probes}"
RESULTS_TEMPLATE="${RESULTS_TEMPLATE:-$REPO_ROOT/docs/BOUNDARY_PROBE_RESULTS_TEMPLATE.tsv}"
ROCMINFO_TIMEOUT="${ROCMINFO_TIMEOUT:-20s}"
TORCH_TIMEOUT="${TORCH_TIMEOUT:-45s}"
WHISPERX_TIMEOUT="${WHISPERX_TIMEOUT:-180s}"

usage() {
  cat <<'USAGE'
Usage:
  boundary_probe.sh init [run_name]
  boundary_probe.sh make-overlay <run_dir> <overlay_name> <source_dir> <lib_glob...>
  boundary_probe.sh show-overlay <run_dir> <overlay_name>
  boundary_probe.sh run-probe <run_dir> <probe_name> <overlay_name|none> [--base old-first|new-first] [--whisperx-cmd '...']

Purpose:
  Build isolated overlay directories and run short, bounded runtime probes
  without broad LD_LIBRARY_PATH swaps.

Defaults:
  OLD_LIB_ROOT      = repo lib-compat/
  NEW_LIB_ROOT      = artifacts/rocm-latest/lib-compat/
  HOST_PYTHON_WRAPPER = scripts/host-docker-python.sh
  VENV_PYTHON       = docker-venv/venv/bin/python
  ROCMINFO_TIMEOUT  = 20s
  TORCH_TIMEOUT     = 45s
  WHISPERX_TIMEOUT  = 180s

Examples:
  scripts/boundary_probe.sh init
  scripts/boundary_probe.sh make-overlay out/boundary-probes/2026-04-29T10-00-00 overlay-hsa-only \
    artifacts/rocm-latest/lib-compat 'libhsa-runtime64.so*' 'libamd_comgr.so*'
  scripts/boundary_probe.sh run-probe out/boundary-probes/2026-04-29T10-00-00 exp1-hsa-only overlay-hsa-only
  scripts/boundary_probe.sh run-probe out/boundary-probes/2026-04-29T10-00-00 exp5-whisperx overlay-hsa-only \
    --whisperx-cmd '$VENV_PYTHON scripts/whisperx_rca_harness.py /path/to/audio.wav --stage transcribe'
USAGE
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_dir() {
  [[ -d "$1" ]] || die "directory not found: $1"
}

require_file() {
  [[ -f "$1" ]] || die "file not found: $1"
}

find_rocminfo_bin() {
  if [[ -n "${ROCMINFO_BIN:-}" ]]; then
    echo "$ROCMINFO_BIN"
    return
  fi
  if command -v rocminfo >/dev/null 2>&1; then
    command -v rocminfo
    return
  fi
  if [[ -x /opt/rocm/bin/rocminfo ]]; then
    echo /opt/rocm/bin/rocminfo
    return
  fi
  die "rocminfo not found; set ROCMINFO_BIN"
}

status_from_exit() {
  local code="$1"
  if [[ "$code" -eq 0 ]]; then
    echo "pass"
  elif [[ "$code" -eq 124 ]]; then
    echo "timeout"
  else
    echo "fail"
  fi
}

append_result() {
  local results_file="$1"
  shift
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$@" >> "$results_file"
}

infer_first_failure_signature() {
  local probe_dir="$1"
  local rocminfo_status="$2"
  local torch_visible="$3"
  local whisperx_status="$4"

  if [[ -f "$probe_dir/preflight.txt" ]]; then
    if rg -q '^host_gpu_unavailable$' "$probe_dir/preflight.txt"; then
      echo "host_gpu_unavailable"
      return
    fi
    if rg -q '^python_env_broken$' "$probe_dir/preflight.txt"; then
      echo "python_env_broken"
      return
    fi
  fi

  if [[ "$rocminfo_status" == "timeout" ]]; then
    echo "rocminfo_timeout"
    return
  fi
  if [[ "$rocminfo_status" == "fail" ]]; then
    if rg -qi 'HSA_STATUS_ERROR|hsa_init' "$probe_dir/rocminfo.txt"; then
      echo "hsa_init_error"
      return
    fi
    echo "rocminfo_failure"
    return
  fi

  if [[ "$torch_visible" == "timeout" ]]; then
    echo "torch_timeout"
    return
  fi
  if [[ "$torch_visible" == "error" ]]; then
    if rg -qi 'undefined symbol|version `[^`]+` not found|cannot open shared object file' "$probe_dir/torch.txt"; then
      echo "abi_or_loader_error"
      return
    fi
    echo "torch_probe_error"
    return
  fi
  if [[ "$torch_visible" == "false" ]]; then
    echo "gpu_not_visible"
    return
  fi

  if [[ "$whisperx_status" == "timeout" ]]; then
    echo "whisperx_timeout"
    return
  fi
  if [[ "$whisperx_status" == "fail" ]]; then
    if [[ -f "$probe_dir/whisperx.txt" ]] && rg -qi 'reset|amdgpu|kfd|ring timeout|GPU fault' "$probe_dir/whisperx.txt"; then
      echo "reset_after_transcribe"
      return
    fi
    echo "whisperx_failure"
    return
  fi

  echo "none"
}

init_run() {
  local run_name="${1:-$(date +%Y-%m-%dT%H-%M-%S)}"
  local run_dir="$OUT_ROOT/$run_name"
  mkdir -p "$run_dir/overlays" "$run_dir/logs"
  if [[ -f "$RESULTS_TEMPLATE" ]]; then
    cp "$RESULTS_TEMPLATE" "$run_dir/results.tsv"
  else
    printf 'probe\toverlay\tbase_order\trocminfo_status\ttorch_visible\twhisperx_status\tfirst_failure_signature\tresult\tnotes\n' > "$run_dir/results.tsv"
  fi
  cat > "$run_dir/README.txt" <<EOF
Boundary probe run: $run_name
OLD_LIB_ROOT=$OLD_LIB_ROOT
NEW_LIB_ROOT=$NEW_LIB_ROOT
VENV_PYTHON=$VENV_PYTHON
ROCMINFO_TIMEOUT=$ROCMINFO_TIMEOUT
TORCH_TIMEOUT=$TORCH_TIMEOUT
WHISPERX_TIMEOUT=$WHISPERX_TIMEOUT
EOF
  echo "$run_dir"
}

make_overlay() {
  local run_dir="$1"
  local overlay_name="$2"
  local source_dir="$3"
  shift 3
  require_dir "$run_dir"
  require_dir "$source_dir"
  [[ "$#" -gt 0 ]] || die "make-overlay requires at least one lib_glob"

  local overlay_dir="$run_dir/overlays/$overlay_name"
  local manifest="$overlay_dir/MANIFEST.txt"
  mkdir -p "$overlay_dir"
  : > "$manifest"

  local pattern matched base
  local found_any=0
  for pattern in "$@"; do
    matched=0
    while IFS= read -r -d '' file_path; do
      matched=1
      found_any=1
      base="$(basename "$file_path")"
      ln -sfn "$(realpath "$file_path")" "$overlay_dir/$base"
      printf '%s\t%s\n' "$base" "$(realpath "$file_path")" >> "$manifest"
    done < <(find "$source_dir" -maxdepth 1 -name "$pattern" -print0 | sort -z)
    if [[ "$matched" -eq 0 ]]; then
      die "pattern did not match in $source_dir: $pattern"
    fi
  done

  [[ "$found_any" -eq 1 ]] || die "overlay is empty: $overlay_name"
  echo "$overlay_dir"
}

show_overlay() {
  local run_dir="$1"
  local overlay_name="$2"
  local manifest="$run_dir/overlays/$overlay_name/MANIFEST.txt"
  require_file "$manifest"
  cat "$manifest"
}

torch_probe_snippet() {
  cat <<'PY'
import torch
print(f"torch_version={torch.__version__}")
print(f"torch_cuda_available={torch.cuda.is_available()}")
print(f"torch_device_count={torch.cuda.device_count()}")
PY
}

link_runtime_entries() {
  local source_dir="$1"
  local target_dir="$2"
  [[ -d "$source_dir" ]] || return 0

  while IFS= read -r -d '' entry_path; do
    local base
    base="$(basename "$entry_path")"
    ln -sfn "$(realpath "$entry_path")" "$target_dir/$base"
  done < <(find "$source_dir" -mindepth 1 -maxdepth 1 -print0 | sort -z)
}

build_runtime_root() {
  local runtime_root="$1"
  local overlay_dir="$2"
  local base_order="$3"
  local compat_dir="$runtime_root/lib-compat"

  mkdir -p "$compat_dir"
  ln -sfn "$REPO_ROOT/docker-venv" "$runtime_root/docker-venv"

  case "$base_order" in
    old-first)
      link_runtime_entries "$NEW_LIB_ROOT" "$compat_dir"
      link_runtime_entries "$OLD_LIB_ROOT" "$compat_dir"
      ;;
    new-first)
      link_runtime_entries "$OLD_LIB_ROOT" "$compat_dir"
      link_runtime_entries "$NEW_LIB_ROOT" "$compat_dir"
      ;;
    *)
      die "unsupported base order for runtime root: $base_order"
      ;;
  esac

  if [[ -n "$overlay_dir" ]]; then
    link_runtime_entries "$overlay_dir" "$compat_dir"
  fi
}

run_probe() {
  local run_dir="$1"
  local probe_name="$2"
  local overlay_name="$3"
  shift 3

  require_dir "$run_dir"
  require_dir "$OLD_LIB_ROOT"
  require_dir "$NEW_LIB_ROOT"
  require_file "$HOST_PYTHON_WRAPPER"
  require_file "$VENV_PYTHON"

  local base_order="old-first"
  local whisperx_cmd=""
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --base)
        [[ "$#" -ge 2 ]] || die "--base requires a value"
        base_order="$2"
        shift 2
        ;;
      --whisperx-cmd)
        [[ "$#" -ge 2 ]] || die "--whisperx-cmd requires a value"
        whisperx_cmd="$2"
        shift 2
        ;;
      *)
        die "unknown argument to run-probe: $1"
        ;;
    esac
  done

  local overlay_dir=""
  if [[ "$overlay_name" != "none" ]]; then
    overlay_dir="$run_dir/overlays/$overlay_name"
    require_dir "$overlay_dir"
  fi

  local rocminfo_bin
  rocminfo_bin="$(find_rocminfo_bin)"
  local probe_dir="$run_dir/logs/$probe_name"
  local results_file="$run_dir/results.tsv"
  local runtime_root="$probe_dir/runtime-root"
  mkdir -p "$probe_dir"
  require_file "$results_file"

  local ld_path=""
  case "$base_order" in
    old-first)
      ld_path="${overlay_dir:+$overlay_dir:}$OLD_LIB_ROOT:$NEW_LIB_ROOT"
      ;;
    new-first)
      ld_path="${overlay_dir:+$overlay_dir:}$NEW_LIB_ROOT:$OLD_LIB_ROOT"
      ;;
    *)
      die "unsupported base order: $base_order"
      ;;
  esac

  build_runtime_root "$runtime_root" "$overlay_dir" "$base_order"

  local rocminfo_code torch_code whisperx_code
  local rocminfo_status torch_status whisperx_status torch_visible notes first_failure_signature
  local preflight_status="ok"

  if [[ ! -e /dev/kfd ]]; then
    printf '%s\n' 'host_gpu_unavailable' > "$probe_dir/preflight.txt"
    preflight_status="host_gpu_unavailable"
  else
    set +e
    env \
      EXTRACTED_OUTDIR="$runtime_root" \
      timeout 15s "$HOST_PYTHON_WRAPPER" -c 'import sys; print(sys.executable)' \
      > "$probe_dir/python-preflight.txt" 2>&1
    torch_code=$?
    set -e
    if [[ "$torch_code" -ne 0 ]]; then
      printf '%s\n' 'python_env_broken' > "$probe_dir/preflight.txt"
      preflight_status="python_env_broken"
    fi
  fi

  if [[ "$preflight_status" != "ok" ]]; then
    rocminfo_status="skipped"
    torch_status="skipped"
    torch_visible="skipped"
    whisperx_status="skipped"
    first_failure_signature="$(infer_first_failure_signature "$probe_dir" "$rocminfo_status" "$torch_visible" "$whisperx_status")"
    notes="logs=$probe_dir preflight=$preflight_status"
    append_result \
      "$results_file" \
      "$probe_name" \
      "$overlay_name" \
      "$base_order" \
      "$rocminfo_status" \
      "$torch_visible" \
      "$whisperx_status" \
      "$first_failure_signature" \
      "" \
      "$notes"

    {
      echo "probe=$probe_name"
      echo "overlay=$overlay_name"
      echo "base_order=$base_order"
      echo "ld_library_path=$ld_path"
      echo "preflight_status=$preflight_status"
      echo "rocminfo_status=$rocminfo_status"
      echo "torch_status=$torch_status"
      echo "torch_visible=$torch_visible"
      echo "whisperx_status=$whisperx_status"
      echo "first_failure_signature=$first_failure_signature"
    } > "$probe_dir/summary.txt"

    echo "$probe_dir"
    return
  fi

  set +e
  env \
    LD_LIBRARY_PATH="$ld_path" \
    HSA_OVERRIDE_GFX_VERSION=8.0.3 \
    ROC_ENABLE_PRE_VEGA=1 \
    timeout "$ROCMINFO_TIMEOUT" "$rocminfo_bin" \
    > "$probe_dir/rocminfo.txt" 2>&1
  rocminfo_code=$?
  set -e
  rocminfo_status="$(status_from_exit "$rocminfo_code")"

  set +e
  env \
    EXTRACTED_OUTDIR="$runtime_root" \
    timeout "$TORCH_TIMEOUT" "$HOST_PYTHON_WRAPPER" - <<'PY' > "$probe_dir/torch.txt" 2>&1
import torch
print(f"torch_version={torch.__version__}")
print(f"torch_cuda_available={torch.cuda.is_available()}")
print(f"torch_device_count={torch.cuda.device_count()}")
PY
  torch_code=$?
  set -e

  if [[ "$torch_code" -eq 124 ]]; then
    torch_status="timeout"
    torch_visible="timeout"
  elif [[ "$torch_code" -ne 0 ]]; then
    torch_status="fail"
    torch_visible="error"
  elif rg -q '^torch_cuda_available=True$' "$probe_dir/torch.txt"; then
    torch_status="pass"
    torch_visible="true"
  elif rg -q '^torch_cuda_available=False$' "$probe_dir/torch.txt"; then
    torch_status="pass"
    torch_visible="false"
  else
    torch_status="pass"
    torch_visible="unknown"
  fi

  if [[ -n "$whisperx_cmd" ]]; then
    set +e
    env \
      LD_LIBRARY_PATH="$ld_path" \
      HSA_OVERRIDE_GFX_VERSION=8.0.3 \
      ROC_ENABLE_PRE_VEGA=1 \
      PYTORCH_ROCM_ARCH=gfx803 \
      ROCM_ARCH=gfx803 \
      TORCH_BLAS_PREFER_HIPBLASLT=0 \
      timeout "$WHISPERX_TIMEOUT" bash -lc "$whisperx_cmd" \
      > "$probe_dir/whisperx.txt" 2>&1
    whisperx_code=$?
    set -e
    whisperx_status="$(status_from_exit "$whisperx_code")"
  else
    whisperx_status="skipped"
  fi

  first_failure_signature="$(infer_first_failure_signature "$probe_dir" "$rocminfo_status" "$torch_visible" "$whisperx_status")"

  notes="logs=$probe_dir"
  append_result \
    "$results_file" \
    "$probe_name" \
    "$overlay_name" \
    "$base_order" \
    "$rocminfo_status" \
    "$torch_visible" \
    "$whisperx_status" \
    "$first_failure_signature" \
    "" \
    "$notes"

  {
    echo "probe=$probe_name"
    echo "overlay=$overlay_name"
    echo "base_order=$base_order"
    echo "ld_library_path=$ld_path"
    echo "rocminfo_status=$rocminfo_status"
    echo "torch_status=$torch_status"
    echo "torch_visible=$torch_visible"
    echo "whisperx_status=$whisperx_status"
    echo "first_failure_signature=$first_failure_signature"
  } > "$probe_dir/summary.txt"

  echo "$probe_dir"
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    init)
      shift
      init_run "${1:-}"
      ;;
    make-overlay)
      shift
      [[ "$#" -ge 4 ]] || die "make-overlay requires <run_dir> <overlay_name> <source_dir> <lib_glob...>"
      make_overlay "$@"
      ;;
    show-overlay)
      shift
      [[ "$#" -eq 2 ]] || die "show-overlay requires <run_dir> <overlay_name>"
      show_overlay "$@"
      ;;
    run-probe)
      shift
      [[ "$#" -ge 3 ]] || die "run-probe requires <run_dir> <probe_name> <overlay_name|none>"
      run_probe "$@"
      ;;
    --help|-h|help)
      usage
      ;;
    *)
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
