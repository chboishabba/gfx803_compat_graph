#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_ROOT="${OUT_ROOT:-$ROOT_DIR/out/whisperx-trace}"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
OUT_DIR="$OUT_ROOT/$STAMP"
WATCH_DIR="$OUT_DIR/devcoredump-watch"
TRACE_CSV="$OUT_DIR/rocprof-hip-trace.csv"
PROFILER_OUT_DIR="$OUT_DIR/profiler"
ENV_LOG="$OUT_DIR/env.txt"
CMD_LOG="$OUT_DIR/command.txt"
RUN_LOG="$OUT_DIR/run.log"
CPU_WATCH_LOG="$OUT_DIR/host-cpu.log"
OBSERVER_LOG="$OUT_DIR/observer.log"
HARNESS="$ROOT_DIR/scripts/whisperx_rca_harness.py"
STAGE="${STAGE:-full}"
MODEL="${WHISPERX_MODEL:-small}"
COMPUTE_TYPE="${WHISPERX_COMPUTE_TYPE:-float16}"
BATCH_SIZE="${WHISPERX_BATCH_SIZE:-4}"
SLEEP_BETWEEN_STAGES="${WHISPERX_SLEEP_BETWEEN_STAGES:-0.25}"
SEGMENT_WINDOW_S="${WHISPERX_SEGMENT_WINDOW_S:-}"
TRANSCRIBE_CHUNK_SIZE_S="${WHISPERX_TRANSCRIBE_CHUNK_SIZE_S:-}"
TRANSCRIBE_STRIDE_S="${WHISPERX_TRANSCRIBE_STRIDE_S:-}"
TRANSCRIBE_MAX_WORKERS="${WHISPERX_TRANSCRIBE_MAX_WORKERS:-}"
TRANSCRIBE_CONCURRENCY="${WHISPERX_TRANSCRIBE_CONCURRENCY:-}"
TRANSCRIBE_VAD_ONSET="${WHISPERX_TRANSCRIBE_VAD_ONSET:-}"
TRANSCRIBE_VAD_OFFSET="${WHISPERX_TRANSCRIBE_VAD_OFFSET:-}"
ROCPROF_ARGS_STRING="${ROCPROF_ARGS:---hip-trace --hsa-trace --timestamp on --basenames on}"
ROCPROFV3_ARGS_STRING="${ROCPROFV3_ARGS:---runtime-trace --marker-trace --kernel-trace --summary --output-format csv json}"
ROCPROFV3_CRASH_CAPTURE_ARGS_STRING="${ROCPROFV3_CRASH_CAPTURE_ARGS:---marker-trace --kernel-trace --output-format csv}"
ROCPROFV3_ENABLE_MEMORY_COPY_TRACE="${WHISPERX_ROCPROFV3_ENABLE_MEMORY_COPY_TRACE:-0}"
KEEP_SUCCESS_TRACE="${KEEP_SUCCESS_TRACE:-0}"
USE_ROCPROF="${USE_ROCPROF:-1}"
WATCH_HOST_CPU="${WATCH_HOST_CPU:-1}"
PROFILER_BACKEND="${WHISPERX_PROFILER_BACKEND:-auto}"
PROFILER_MODE="${WHISPERX_PROFILER_MODE:-standard}"
HEARTBEAT_INTERVAL="${WHISPERX_HEARTBEAT_INTERVAL:-5}"
OBSERVER_INTERVAL="${WHISPERX_OBSERVER_INTERVAL:-5}"
OBSERVER_EVENT_TAIL_LINES="${WHISPERX_OBSERVER_EVENT_TAIL_LINES:-10}"
OBSERVER_RUNLOG_TAIL_LINES="${WHISPERX_OBSERVER_RUNLOG_TAIL_LINES:-20}"
OBSERVER_KERNEL_TAIL_LINES="${WHISPERX_OBSERVER_KERNEL_TAIL_LINES:-20}"
ROCPROFV3_OUTPUT_MODE="${WHISPERX_ROCPROFV3_OUTPUT_MODE:-csv}"
ROCPROFV3_COLLECTION_PERIOD="${WHISPERX_ROCPROFV3_COLLECTION_PERIOD:-}"
ROCPROFV3_COLLECTION_PERIOD_UNIT="${WHISPERX_ROCPROFV3_COLLECTION_PERIOD_UNIT:-sec}"
PROFILE_SELECTED_STAGE="${WHISPERX_PROFILE_SELECTED_STAGE:-}"
PROFILE_STAGE_POLICY="${WHISPERX_PROFILE_STAGE_POLICY:-}"
SYSTEM_LIBSTDCXX="/usr/lib/libstdc++.so.6"
HARNESS_HELP_CACHE=""

mkdir -p "$OUT_DIR"

if [ "$#" -lt 1 ]; then
  echo "Usage: bash scripts/trace-whisperx-rocprof.sh /path/to/audio [extra harness args...]" >&2
  exit 2
fi

AUDIO_PATH="$1"
shift || true

resolve_profiler_backend() {
  if [ "$USE_ROCPROF" -ne 1 ]; then
    echo "none"
    return 0
  fi

  case "$PROFILER_BACKEND" in
    auto)
      if command -v rocprofv3 >/dev/null 2>&1; then
        echo "rocprofv3"
        return 0
      fi
      if command -v rocprof >/dev/null 2>&1; then
        echo "rocprof"
        return 0
      fi
      ;;
    rocprofv3|rocprof)
      if command -v "$PROFILER_BACKEND" >/dev/null 2>&1; then
        echo "$PROFILER_BACKEND"
        return 0
      fi
      ;;
    none)
      echo "none"
      return 0
      ;;
  esac

  echo "ERROR: requested profiler backend '$PROFILER_BACKEND' is not available" >&2
  exit 1
}

ACTIVE_PROFILER_BACKEND="$(resolve_profiler_backend)"

resolve_profile_stage_policy() {
  if [ -n "$PROFILE_STAGE_POLICY" ]; then
    echo "$PROFILE_STAGE_POLICY"
    return 0
  fi
  if [ -n "$PROFILE_SELECTED_STAGE" ]; then
    echo "exact"
    return 0
  fi
  echo "none"
}

ACTIVE_PROFILE_STAGE_POLICY="$(resolve_profile_stage_policy)"

cache_harness_help() {
  if [ -n "$HARNESS_HELP_CACHE" ]; then
    return 0
  fi
  HARNESS_HELP_CACHE="$("$ROOT_DIR/scripts/host-docker-python.sh" "$HARNESS" --help 2>&1 || true)"
}

harness_supports_arg() {
  local arg="$1"
  cache_harness_help
  printf '%s\n' "$HARNESS_HELP_CACHE" | rg -q -- "$arg"
}

resolve_rocprofv3_args() {
  local base_args=""
  case "$PROFILER_MODE" in
    standard)
      base_args="$ROCPROFV3_ARGS_STRING"
      ;;
    crash-capture)
      base_args="$ROCPROFV3_CRASH_CAPTURE_ARGS_STRING"
      ;;
    *)
      echo "ERROR: unknown profiler mode '$PROFILER_MODE'" >&2
      exit 1
      ;;
  esac

  if [ "$ROCPROFV3_OUTPUT_MODE" = "rocpd" ]; then
    base_args="${base_args/ --output-format csv/}"
    base_args="${base_args/ --output-format csv json/}"
    base_args="${base_args/ --output-format json csv/}"
  elif [ "$ROCPROFV3_OUTPUT_MODE" != "csv" ]; then
    echo "ERROR: unknown rocprofv3 output mode '$ROCPROFV3_OUTPUT_MODE'" >&2
    exit 1
  fi

  if [ "$ROCPROFV3_ENABLE_MEMORY_COPY_TRACE" = "1" ] && [[ " $base_args " != *" --memory-copy-trace "* ]]; then
    base_args="$base_args --memory-copy-trace"
  fi

  if [ -n "$ROCPROFV3_COLLECTION_PERIOD" ]; then
    base_args="$base_args --collection-period $ROCPROFV3_COLLECTION_PERIOD --collection-period-unit $ROCPROFV3_COLLECTION_PERIOD_UNIT"
  fi

  if [ "$ACTIVE_PROFILE_STAGE_POLICY" != "none" ]; then
    base_args="$base_args --selected-regions"
  fi

  echo "$base_args"
}

ACTIVE_ROCPROFV3_ARGS_STRING="$(resolve_rocprofv3_args)"

HARNESS_OPTIONAL_ARGS=()
append_optional_harness_arg() {
  local arg_name="$1"
  local arg_value="$2"
  if [ -z "$arg_value" ]; then
    return 0
  fi
  if harness_supports_arg "$arg_name"; then
    HARNESS_OPTIONAL_ARGS+=("$arg_name" "$arg_value")
  fi
}

TRANSCRIBE_CHUNK_SIZE_EFFECTIVE="$TRANSCRIBE_CHUNK_SIZE_S"
if [ -z "$TRANSCRIBE_CHUNK_SIZE_EFFECTIVE" ]; then
  TRANSCRIBE_CHUNK_SIZE_EFFECTIVE="$SEGMENT_WINDOW_S"
fi

TRANSCRIBE_NUM_WORKERS_EFFECTIVE="$TRANSCRIBE_MAX_WORKERS"
if [ -z "$TRANSCRIBE_NUM_WORKERS_EFFECTIVE" ]; then
  TRANSCRIBE_NUM_WORKERS_EFFECTIVE="$TRANSCRIBE_CONCURRENCY"
fi

append_optional_harness_arg "--transcribe-chunk-size" "$TRANSCRIBE_CHUNK_SIZE_EFFECTIVE"
append_optional_harness_arg "--transcribe-num-workers" "$TRANSCRIBE_NUM_WORKERS_EFFECTIVE"
append_optional_harness_arg "--load-model-threads" "${WHISPERX_LOAD_MODEL_THREADS:-}"
append_optional_harness_arg "--vad-method" "${WHISPERX_VAD_METHOD:-}"

if [ -n "$TRANSCRIBE_VAD_ONSET$TRANSCRIBE_VAD_OFFSET" ] && harness_supports_arg "--vad-options-json"; then
  vad_json='{'
  sep=''
  if [ -n "$TRANSCRIBE_VAD_ONSET" ]; then
    vad_json="${vad_json}${sep}\"vad_onset\": ${TRANSCRIBE_VAD_ONSET}"
    sep=', '
  fi
  if [ -n "$TRANSCRIBE_VAD_OFFSET" ]; then
    vad_json="${vad_json}${sep}\"vad_offset\": ${TRANSCRIBE_VAD_OFFSET}"
  fi
  vad_json="${vad_json}}"
  HARNESS_OPTIONAL_ARGS+=("--vad-options-json" "$vad_json")
fi

export HSA_ENABLE_SDMA="${HSA_ENABLE_SDMA:-0}"
export AMD_LOG_LEVEL="${AMD_LOG_LEVEL:-3}"
export ROCBLAS_LAYER="${ROCBLAS_LAYER:-3}"
export HIP_TRACE_API="${HIP_TRACE_API:-1}"
export JOBLIB_MULTIPROCESSING="${JOBLIB_MULTIPROCESSING:-0}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
export WATCH_AMDGPU_DEVCOREDUMP=1
export CRASH_OUTDIR_ROOT="$WATCH_DIR"

cat >"$ENV_LOG" <<EOF
STAMP=$STAMP
OUT_DIR=$OUT_DIR
AUDIO_PATH=$AUDIO_PATH
STAGE=$STAGE
WHISPERX_MODEL=$MODEL
WHISPERX_COMPUTE_TYPE=$COMPUTE_TYPE
WHISPERX_BATCH_SIZE=$BATCH_SIZE
WHISPERX_SLEEP_BETWEEN_STAGES=$SLEEP_BETWEEN_STAGES
WHISPERX_SEGMENT_WINDOW_S=$SEGMENT_WINDOW_S
WHISPERX_TRANSCRIBE_CHUNK_SIZE_S=$TRANSCRIBE_CHUNK_SIZE_S
WHISPERX_TRANSCRIBE_STRIDE_S=$TRANSCRIBE_STRIDE_S
WHISPERX_TRANSCRIBE_MAX_WORKERS=$TRANSCRIBE_MAX_WORKERS
WHISPERX_TRANSCRIBE_CONCURRENCY=$TRANSCRIBE_CONCURRENCY
WHISPERX_TRANSCRIBE_VAD_ONSET=$TRANSCRIBE_VAD_ONSET
WHISPERX_TRANSCRIBE_VAD_OFFSET=$TRANSCRIBE_VAD_OFFSET
HSA_ENABLE_SDMA=$HSA_ENABLE_SDMA
AMD_LOG_LEVEL=$AMD_LOG_LEVEL
ROCBLAS_LAYER=$ROCBLAS_LAYER
HIP_TRACE_API=$HIP_TRACE_API
JOBLIB_MULTIPROCESSING=$JOBLIB_MULTIPROCESSING
TOKENIZERS_PARALLELISM=$TOKENIZERS_PARALLELISM
ROCPROF_ARGS=$ROCPROF_ARGS_STRING
ROCPROFV3_ARGS=$ROCPROFV3_ARGS_STRING
ROCPROFV3_CRASH_CAPTURE_ARGS=$ROCPROFV3_CRASH_CAPTURE_ARGS_STRING
USE_ROCPROF=$USE_ROCPROF
WATCH_HOST_CPU=$WATCH_HOST_CPU
WHISPERX_PROFILER_BACKEND=$PROFILER_BACKEND
ACTIVE_PROFILER_BACKEND=$ACTIVE_PROFILER_BACKEND
WHISPERX_PROFILER_MODE=$PROFILER_MODE
ACTIVE_ROCPROFV3_ARGS=$ACTIVE_ROCPROFV3_ARGS_STRING
WHISPERX_HEARTBEAT_INTERVAL=$HEARTBEAT_INTERVAL
WHISPERX_OBSERVER_INTERVAL=$OBSERVER_INTERVAL
WHISPERX_ROCPROFV3_OUTPUT_MODE=$ROCPROFV3_OUTPUT_MODE
WHISPERX_ROCPROFV3_ENABLE_MEMORY_COPY_TRACE=$ROCPROFV3_ENABLE_MEMORY_COPY_TRACE
WHISPERX_ROCPROFV3_COLLECTION_PERIOD=$ROCPROFV3_COLLECTION_PERIOD
WHISPERX_ROCPROFV3_COLLECTION_PERIOD_UNIT=$ROCPROFV3_COLLECTION_PERIOD_UNIT
WHISPERX_PROFILE_SELECTED_STAGE=$PROFILE_SELECTED_STAGE
WHISPERX_PROFILE_STAGE_POLICY=$PROFILE_STAGE_POLICY
ACTIVE_PROFILE_STAGE_POLICY=$ACTIVE_PROFILE_STAGE_POLICY
EOF

{
  if [ "$ACTIVE_PROFILER_BACKEND" = "rocprof" ]; then
    printf 'rocprof %s -o %q ' "$ROCPROF_ARGS_STRING" "$TRACE_CSV"
  elif [ "$ACTIVE_PROFILER_BACKEND" = "rocprofv3" ]; then
    printf 'rocprofv3 %s -d %q -o %q -- ' "$ACTIVE_ROCPROFV3_ARGS_STRING" "$PROFILER_OUT_DIR" "whisperx"
  fi
  printf '%q %q ' "$ROOT_DIR/scripts/host-docker-python.sh" "$HARNESS"
  printf -- '--audio %q --outdir %q --stage %q --model %q --compute-type %q --batch-size %q --sleep-between-stages %q' \
    "$AUDIO_PATH" "$OUT_DIR/harness" "$STAGE" "$MODEL" "$COMPUTE_TYPE" "$BATCH_SIZE" "$SLEEP_BETWEEN_STAGES"
  if [ -n "$PROFILE_SELECTED_STAGE" ]; then
    printf ' --profile-selected-stage %q' "$PROFILE_SELECTED_STAGE"
  fi
  if [ -n "$PROFILE_STAGE_POLICY" ]; then
    printf ' --profile-stage-policy %q' "$PROFILE_STAGE_POLICY"
  fi
  for ((i = 0; i < ${#HARNESS_OPTIONAL_ARGS[@]}; i++)); do
    printf ' %q' "${HARNESS_OPTIONAL_ARGS[$i]}"
  done
  for arg in "$@"; do
    printf ' %q' "$arg"
  done
  printf '\n'
} >"$CMD_LOG"

WATCH_PID=""
CPU_WATCH_PID=""
HEARTBEAT_PID=""
OBSERVER_PID=""
cleanup() {
  if [[ -n "$WATCH_PID" ]] && kill -0 "$WATCH_PID" 2>/dev/null; then
    kill "$WATCH_PID" 2>/dev/null || true
    wait "$WATCH_PID" 2>/dev/null || true
  fi
  if [[ -n "$CPU_WATCH_PID" ]] && kill -0 "$CPU_WATCH_PID" 2>/dev/null; then
    kill "$CPU_WATCH_PID" 2>/dev/null || true
    wait "$CPU_WATCH_PID" 2>/dev/null || true
  fi
  if [[ -n "$HEARTBEAT_PID" ]] && kill -0 "$HEARTBEAT_PID" 2>/dev/null; then
    kill "$HEARTBEAT_PID" 2>/dev/null || true
    wait "$HEARTBEAT_PID" 2>/dev/null || true
  fi
  if [[ -n "$OBSERVER_PID" ]] && kill -0 "$OBSERVER_PID" 2>/dev/null; then
    kill "$OBSERVER_PID" 2>/dev/null || true
    wait "$OBSERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

start_heartbeat() {
  local heartbeat_log="$OUT_DIR/heartbeat.log"
  (
    while true; do
      {
        printf 'ts=%s backend=%s mode=%s\n' \
          "$(date --iso-8601=seconds)" "$ACTIVE_PROFILER_BACKEND" "$PROFILER_MODE"
        if [ -f "$OUT_DIR/harness/events.jsonl" ]; then
          tail -n 3 "$OUT_DIR/harness/events.jsonl" 2>/dev/null || true
        else
          printf 'events=missing\n'
        fi
        if [ -d "$PROFILER_OUT_DIR" ]; then
          find "$PROFILER_OUT_DIR" -maxdepth 1 -type f -printf 'profiler_file=%f size=%s\n' 2>/dev/null | sort || true
        fi
        printf '\n'
      } >>"$heartbeat_log"
      sleep "$HEARTBEAT_INTERVAL"
    done
  ) &
  HEARTBEAT_PID="$!"
}

start_observer() {
  (
    while true; do
      {
        printf 'ts=%s backend=%s mode=%s output=%s collection_period=%s unit=%s\n' \
          "$(date --iso-8601=seconds)" "$ACTIVE_PROFILER_BACKEND" "$PROFILER_MODE" \
          "$ROCPROFV3_OUTPUT_MODE" "${ROCPROFV3_COLLECTION_PERIOD:-none}" "$ROCPROFV3_COLLECTION_PERIOD_UNIT"
        printf '[run.log tail]\n'
        if [ -f "$RUN_LOG" ]; then
          tail -n "$OBSERVER_RUNLOG_TAIL_LINES" "$RUN_LOG" 2>/dev/null || true
        else
          printf 'missing\n'
        fi
        printf '[events tail]\n'
        if [ -f "$OUT_DIR/harness/events.jsonl" ]; then
          tail -n "$OBSERVER_EVENT_TAIL_LINES" "$OUT_DIR/harness/events.jsonl" 2>/dev/null || true
        else
          printf 'missing\n'
        fi
        printf '[profiler files]\n'
        if [ -d "$PROFILER_OUT_DIR" ]; then
          find "$PROFILER_OUT_DIR" -maxdepth 1 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %f size=%s\n' 2>/dev/null | sort || true
        else
          printf 'missing\n'
        fi
        printf '[kernel tail]\n'
        journalctl -k -b 0 -n "$OBSERVER_KERNEL_TAIL_LINES" --no-pager 2>/dev/null || true
        printf '\n'
      } >>"$OBSERVER_LOG"
      sleep "$OBSERVER_INTERVAL"
    done
  ) &
  OBSERVER_PID="$!"
}

should_keep_trace() {
  if is_profile_tool_dependency_error; then
    return 1
  fi

  if [ "$KEEP_SUCCESS_TRACE" = "1" ]; then
    return 0
  fi

  if [ "${RUN_STATUS:-0}" -ne 0 ]; then
    return 0
  fi

  if [ ! -f "$OUT_DIR/harness/events.jsonl" ]; then
    return 0
  fi

  if rg -q '"kind": "(stage_error|import_error)"' "$OUT_DIR/harness/events.jsonl"; then
    return 0
  fi

  if ! rg -q '"kind": "run_end".*"status": "ok"' "$OUT_DIR/harness/events.jsonl"; then
    return 0
  fi

  if find "$WATCH_DIR" -mindepth 2 -type f | rg -q .; then
    return 0
  fi

  return 1
}

is_profile_tool_dependency_error() {
  if [ ! -f "$RUN_LOG" ]; then
    return 1
  fi

  rg -q "CXXABI_1.3.15.*not found|version \`CXXABI_1.3.15'" "$RUN_LOG" || return 1
  return 0
}

echo "Output directory: $OUT_DIR"
echo "Starting devcoredump watcher..."
OUT_ROOT="$WATCH_DIR" POLL_INTERVAL="${POLL_INTERVAL:-0.05}" \
  bash "$ROOT_DIR/scripts/watch-amdgpu-devcoredump.sh" >"$OUT_DIR/devcoredump-watch.log" 2>&1 &
WATCH_PID="$!"

if [ "$WATCH_HOST_CPU" = "1" ]; then
  echo "Starting host CPU hotspot watcher..."
  POLL_INTERVAL="${CPU_WATCH_INTERVAL:-1}" TOP_N="${CPU_WATCH_TOP_N:-12}" \
    bash "$ROOT_DIR/scripts/watch-host-cpu-hotspots.sh" "$CPU_WATCH_LOG" &
  CPU_WATCH_PID="$!"
fi

echo "Starting lightweight heartbeat..."
start_heartbeat
echo "Starting external observer..."
start_observer

sleep 0.2

if [ "$ACTIVE_PROFILER_BACKEND" = "rocprof" ]; then
  echo "Running WhisperX harness under rocprof..."
  read -r -a ROCPROF_ARGS_ARRAY <<<"$ROCPROF_ARGS_STRING"
  set +e
  LD_PRELOAD="$SYSTEM_LIBSTDCXX${LD_PRELOAD:+:$LD_PRELOAD}" \
  rocprof "${ROCPROF_ARGS_ARRAY[@]}" -o "$TRACE_CSV" \
    "$ROOT_DIR/scripts/host-docker-python.sh" "$HARNESS" \
    --audio "$AUDIO_PATH" \
    --outdir "$OUT_DIR/harness" \
    --stage "$STAGE" \
    --model "$MODEL" \
    --compute-type "$COMPUTE_TYPE" \
    --batch-size "$BATCH_SIZE" \
    --sleep-between-stages "$SLEEP_BETWEEN_STAGES" \
    ${PROFILE_SELECTED_STAGE:+--profile-selected-stage "$PROFILE_SELECTED_STAGE"} \
    ${PROFILE_STAGE_POLICY:+--profile-stage-policy "$PROFILE_STAGE_POLICY"} \
    "${HARNESS_OPTIONAL_ARGS[@]}" \
    "$@" 2>&1 | tee "$RUN_LOG"
  RUN_STATUS="${PIPESTATUS[0]}"
  set -e
elif [ "$ACTIVE_PROFILER_BACKEND" = "rocprofv3" ]; then
  echo "Running WhisperX harness under rocprofv3..."
  mkdir -p "$PROFILER_OUT_DIR"
  read -r -a ROCPROFV3_ARGS_ARRAY <<<"$ACTIVE_ROCPROFV3_ARGS_STRING"
  set +e
  stdbuf -oL -eL rocprofv3 "${ROCPROFV3_ARGS_ARRAY[@]}" -d "$PROFILER_OUT_DIR" -o "whisperx" -- \
    "$ROOT_DIR/scripts/host-docker-python.sh" "$HARNESS" \
    --audio "$AUDIO_PATH" \
    --outdir "$OUT_DIR/harness" \
    --stage "$STAGE" \
    --model "$MODEL" \
    --compute-type "$COMPUTE_TYPE" \
    --batch-size "$BATCH_SIZE" \
    --sleep-between-stages "$SLEEP_BETWEEN_STAGES" \
    ${PROFILE_SELECTED_STAGE:+--profile-selected-stage "$PROFILE_SELECTED_STAGE"} \
    ${PROFILE_STAGE_POLICY:+--profile-stage-policy "$PROFILE_STAGE_POLICY"} \
    "${HARNESS_OPTIONAL_ARGS[@]}" \
    "$@" 2>&1 | tee "$RUN_LOG"
  RUN_STATUS="${PIPESTATUS[0]}"
  set -e
else
  echo "Running WhisperX harness without rocprof (profiling disabled)."
  set +e
  "$ROOT_DIR/scripts/host-docker-python.sh" "$HARNESS" \
    --audio "$AUDIO_PATH" \
    --outdir "$OUT_DIR/harness" \
    --stage "$STAGE" \
    --model "$MODEL" \
    --compute-type "$COMPUTE_TYPE" \
    --batch-size "$BATCH_SIZE" \
    --sleep-between-stages "$SLEEP_BETWEEN_STAGES" \
    ${PROFILE_SELECTED_STAGE:+--profile-selected-stage "$PROFILE_SELECTED_STAGE"} \
    ${PROFILE_STAGE_POLICY:+--profile-stage-policy "$PROFILE_STAGE_POLICY"} \
    "${HARNESS_OPTIONAL_ARGS[@]}" \
    "$@" 2>&1 | tee "$RUN_LOG"
  RUN_STATUS="${PIPESTATUS[0]}"
  set -e
fi

if should_keep_trace; then
  echo "Keeping trace bundle: $OUT_DIR"
else
  echo "No wedge or stage failure detected; discarding trace bundle: $OUT_DIR"
  rm -rf "$OUT_DIR"
fi

exit "$RUN_STATUS"
