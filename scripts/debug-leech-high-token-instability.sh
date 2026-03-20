#!/usr/bin/env bash
# debug-leech-high-token-instability.sh
# Deterministic harness for reproducing LeechTransformer higher-token GPU instability.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CHECKPOINT_PATH="${LEECH_DEBUG_CHECKPOINT:-/home/c/Documents/code/DASHIg/LeechTransformer/data/best_model.pt}"
PROMPT_TEXT="${LEECH_DEBUG_PROMPT:-Once upon a time Lila}"
TOKENS_CSV="${LEECH_DEBUG_TOKENS:-8,16,24,32,40,48,64}"
KVCACHE_CSV="${LEECH_DEBUG_KVCACHE:-off,on}"
PROFILES_CSV="${LEECH_DEBUG_PROFILES:-baseline,direct_only,gemm_only}"
REPEATS="${LEECH_DEBUG_REPEATS:-2}"
RUN_SCRIPT="${LEECH_DEBUG_SCRIPT:-/home/c/Documents/code/DASHIg/LeechTransformer/scripts/run_inference.py}"
OUT_ROOT="${LEECH_DEBUG_OUT_ROOT:-$REPO_ROOT/out/leech-debug-high-tokens}"
QUIET="${LEECH_DEBUG_QUIET:-1}"
DRY_RUN="${LEECH_DEBUG_DRY_RUN:-0}"

if [[ ! -f "$RUN_SCRIPT" ]]; then
  echo "ERROR: Leech inference script not found: $RUN_SCRIPT" >&2
  exit 1
fi

if [[ ! -f "$CHECKPOINT_PATH" ]]; then
  echo "ERROR: checkpoint not found: $CHECKPOINT_PATH" >&2
  exit 1
fi

show_help() {
  cat <<USAGE
Usage: debug-leech-high-token-instability.sh [options]

Options:
  --checkpoint <path>        Override checkpoint path.
  --prompt <text>            Prompt to feed into run_inference.py.
  --tokens <csv>             Comma list for max_tokens sweep (default: ${TOKENS_CSV}).
  --kv-cache <csv>           Comma list 'off,on' or just one mode.
  --profiles <csv>           Profile list: baseline,direct_only,gemm_only.
  --repeats <n>              Repeated runs per case (default: ${REPEATS}).
  --script <path>            Path to run_inference.py.
  --out <dir>                Output root (default: ${OUT_ROOT}).
  --quiet|--no-quiet          Add/remove --quiet to run_inference command.
  --dry-run                  Print commands only.
  --help                     Show this help.

Environment variables:
  LEECH_DEBUG_* can set all defaults if preferred.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --checkpoint)
      CHECKPOINT_PATH="$2"
      shift 2
      ;;
    --prompt)
      PROMPT_TEXT="$2"
      shift 2
      ;;
    --tokens)
      TOKENS_CSV="$2"
      shift 2
      ;;
    --kv-cache)
      KVCACHE_CSV="$2"
      shift 2
      ;;
    --profiles)
      PROFILES_CSV="$2"
      shift 2
      ;;
    --repeats)
      REPEATS="$2"
      shift 2
      ;;
    --script)
      RUN_SCRIPT="$2"
      shift 2
      ;;
    --out)
      OUT_ROOT="$2"
      shift 2
      ;;
    --quiet)
      QUIET=1
      shift
      ;;
    --no-quiet)
      QUIET=0
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --help|-h)
      show_help
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument '$1'" >&2
      show_help
      exit 1
      ;;
  esac
done

if [[ ! "$REPEATS" =~ ^[0-9]+$ ]] || [[ "$REPEATS" -lt 1 ]]; then
  echo "ERROR: --repeats must be a positive integer" >&2
  exit 1
fi

OUT_ROOT="${OUT_ROOT%/}"
RUN_ID="$(date +%Y-%m-%dT%H-%M-%S)"
OUT_DIR="$OUT_ROOT/$RUN_ID"
mkdir -p "$OUT_DIR"

parse_csv() {
  local csv="$1"
  local -a parsed
  IFS=',' read -r -a parsed <<< "$csv"
  local item
  for item in "${parsed[@]}"; do
    item="$(echo "$item" | tr -d '[:space:]')"
    if [[ -n "$item" ]]; then
      printf '%s\n' "$item"
    fi
  done
}

normalize_list() {
  local item="$1"
  case "$item" in
    baseline|direct_only|gemm_only) ;;
    *) echo "ERROR: unknown profile '$item' (expected baseline,direct_only,gemm_only)" >&2; exit 1;;
  esac
}

readarray -t TOKENS_LIST < <(parse_csv "$TOKENS_CSV")
readarray -t KVCACHE_LIST < <(parse_csv "$KVCACHE_CSV")
readarray -t PROFILES_LIST < <(parse_csv "$PROFILES_CSV")

SUMMARY_CSV="$OUT_DIR/summary.csv"
echo "run_id,profile,kv_cache,max_tokens,attempt,status,exit_code,fault_signals,device,run_log,capture_dir" > "$SUMMARY_CSV"

classify_faults() {
  local file="$1"
  local sigs=""
  if grep -Eq "Memory access fault|GPU core dump failed|GPU reset|kfd|amdgpu:.*coredump|ring .*timeout|VRAM is lost|init_user_pages|devcoredump" "$file"; then
    sigs="gpu_memory_fault"
  elif grep -Eq "Segmentation fault|SIGABRT|Traceback|RuntimeError" "$file"; then
    sigs="application_error"
  else
    sigs="none"
  fi
  echo "$sigs"
}

device_from_log() {
  local file="$1"
  if grep -q "selected=cuda" "$file"; then
    echo "cuda"
  elif grep -q "selected=cpu" "$file"; then
    echo "cpu"
  else
    echo "unknown"
  fi
}

for profile in "${PROFILES_LIST[@]}"; do
  normalize_list "$profile"
  for kv_mode in "${KVCACHE_LIST[@]}"; do
    if [[ "$kv_mode" != "off" && "$kv_mode" != "on" ]]; then
      echo "ERROR: unknown kv-cache mode '$kv_mode' (expected off,on)" >&2
      exit 1
    fi

    for tokens in "${TOKENS_LIST[@]}"; do
      if [[ -z "$tokens" ]]; then
        continue
      fi
      if ! [[ "$tokens" =~ ^[0-9]+$ ]]; then
        echo "ERROR: non-numeric token value '$tokens'" >&2
        exit 1
      fi

      for attempt in $(seq 1 "$REPEATS"); do
        CASE_DIR="$OUT_DIR/${profile}-kv${kv_mode}-t${tokens}-r${attempt}"
        mkdir -p "$CASE_DIR/watch"

        RUN_LOG="$CASE_DIR/run.log"
        WATCH_ROOT="$CASE_DIR/watch"
        COMMAND_LOG="$CASE_DIR/command.txt"

        PROFILE_ENV=(MIOPEN_DEBUG_DISABLE_FIND_DB=1 MIOPEN_FIND_ENFORCE=3 CUBLAS_WORKSPACE_CONFIG=':4096:8')
        if [[ "$profile" == "baseline" ]]; then
          PROFILE_ENV+=(MIOPEN_DEBUG_CONV_DIRECT=1 MIOPEN_DEBUG_CONV_GEMM=0 MIOPEN_DEBUG_CONV_WINOGRAD=0 MIOPEN_DEBUG_CONV_FFT=0 MIOPEN_DEBUG_CONV_DET=1)
        elif [[ "$profile" == "direct_only" ]]; then
          PROFILE_ENV+=(MIOPEN_DEBUG_CONV_DIRECT=1 MIOPEN_DEBUG_CONV_GEMM=0 MIOPEN_DEBUG_CONV_WINOGRAD=0 MIOPEN_DEBUG_CONV_FFT=0 MIOPEN_DEBUG_CONV_DET=1)
        elif [[ "$profile" == "gemm_only" ]]; then
          PROFILE_ENV+=(MIOPEN_DEBUG_CONV_DIRECT=0 MIOPEN_DEBUG_CONV_GEMM=1 MIOPEN_DEBUG_CONV_WINOGRAD=0 MIOPEN_DEBUG_CONV_FFT=0 MIOPEN_DEBUG_CONV_DET=1)
        fi

        RUN_ARGS=(--checkpoint "$CHECKPOINT_PATH" --prompt "$PROMPT_TEXT" --max_tokens "$tokens")
        if [[ "$kv_mode" == "on" ]]; then
          RUN_ARGS+=(--kv_cache)
        fi
        if [[ "$QUIET" == "1" ]]; then
          RUN_ARGS+=(--quiet)
        fi

        {
          printf 'run_id=%s\n' "$RUN_ID"
          printf 'profile=%s\n' "$profile"
          printf 'kv_cache=%s\n' "$kv_mode"
          printf 'tokens=%s\n' "$tokens"
          printf 'attempt=%s\n' "$attempt"
          printf 'script=%s\n' "$RUN_SCRIPT"
          printf 'checkpoint=%s\n' "$CHECKPOINT_PATH"
          printf 'prompt=%s\n' "$PROMPT_TEXT"
          printf 'HSA_OVERRIDE_GFX_VERSION=%s\n' "${HSA_OVERRIDE_GFX_VERSION:-8.0.3}"
          printf 'MIOPEN_DEBUG_CONV_DIRECT=%s\n' "${MIOPEN_DEBUG_CONV_DIRECT:-}"
          printf 'MIOPEN_DEBUG_CONV_GEMM=%s\n' "${MIOPEN_DEBUG_CONV_GEMM:-}"
        } > "$COMMAND_LOG"
        printf '%q ' bash "$SCRIPT_DIR/host-docker-python.sh" "${RUN_ARGS[@]}" >> "$COMMAND_LOG"

        if [[ "$DRY_RUN" == "1" ]]; then
          echo "DRY RUN: case=$profile kv=$kv_mode tokens=$tokens attempt=$attempt" >> "$COMMAND_LOG"
          echo "$profile,$kv_mode,$tokens,$attempt,dry_run,0,none,unknown,$RUN_LOG,$CASE_DIR/capture" >> "$SUMMARY_CSV"
          continue
        fi

        START_TIME="$(date +'%Y-%m-%d %H:%M:%S')"
        set +e
        (
          export HOST_DOCKER_PYTHON_GPU_PRECHECK="${HOST_DOCKER_PYTHON_GPU_PRECHECK:-1}"
          export WATCH_AMDGPU_DEVCOREDUMP="${WATCH_AMDGPU_DEVCOREDUMP:-1}"
          export CRASH_OUTDIR_ROOT="$WATCH_ROOT"
          if [[ "$kv_mode" == "on" ]]; then
            export LEECH_ALLOW_KVCACHE_GPU=1
          else
            export LEECH_ALLOW_KVCACHE_GPU=0
          fi
          export HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-8.0.3}"
          export ROC_ENABLE_PRE_VEGA="${ROC_ENABLE_PRE_VEGA:-1}"
          export PYTORCH_ROCM_ARCH="${PYTORCH_ROCM_ARCH:-gfx803}"
          export ROCM_ARCH="${ROCM_ARCH:-gfx803}"
          for env_pair in "${PROFILE_ENV[@]}"; do
            export "$env_pair"
          done
          bash "$SCRIPT_DIR/host-docker-python.sh" "$RUN_SCRIPT" "${RUN_ARGS[@]}"
        ) > "$RUN_LOG" 2>&1
        run_exit=$?
        set -e

        journalctl -k -b --since "$START_TIME" --no-pager > "$CASE_DIR/kernel-journal.txt" || true
        status="pass"
        if [[ "$run_exit" -ne 0 ]]; then
          status="exit_${run_exit}"
          fault_signals="$(classify_faults "$RUN_LOG"; classify_faults "$CASE_DIR/kernel-journal.txt")"
        else
          fault_signals="$(classify_faults "$RUN_LOG")"
        fi
        fault_signals="$(echo "$fault_signals" | tr '\n' ';')"
        if [[ "$fault_signals" == *"gpu_memory_fault"* ]]; then
          status="gpu_fault"
        fi

        DEVICE="$(device_from_log "$RUN_LOG")"
        capture_dir=""
        if [[ "$status" == "gpu_fault" ]]; then
          CAPTURE_DIR="$CASE_DIR/capture"
          mkdir -p "$CAPTURE_DIR"
          bash "$SCRIPT_DIR/capture-amdgpu-crash-artifacts.sh" '5 minutes ago' > "$CAPTURE_DIR/path.txt" 2>&1 || true
          if [[ -s "$CAPTURE_DIR/path.txt" ]]; then
            capture_dir="$(cat "$CAPTURE_DIR/path.txt")"
          else
            capture_dir="$CAPTURE_DIR"
          fi
        fi

        printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,"%s","%s"\n' \
          "$RUN_ID" "$profile" "$kv_mode" "$tokens" "$attempt" "$status" "$run_exit" "$fault_signals" \
          "$DEVICE" "$RUN_LOG" "$capture_dir" >> "$SUMMARY_CSV"
      done
    done
  done
done

echo "Leech high-token debug matrix complete."
echo "Output: $OUT_DIR"
echo "Summary: $SUMMARY_CSV"
