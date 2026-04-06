#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRACE_SCRIPT="$ROOT_DIR/scripts/trace-whisperx-rocprof.sh"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
OUT_ROOT="${OUT_ROOT:-$ROOT_DIR/out/whisperx-rca-matrix/$STAMP}"
SUMMARY_CSV="$OUT_ROOT/summary.csv"

if [ "$#" -lt 1 ]; then
  cat >&2 <<'EOF'
Usage:
  bash scripts/run-whisperx-rca-matrix.sh /path/to/audio [extra trace-whisperx args...]

Modes:
  RCA_MATRIX_MODE=lanes      (default) named RCA lanes
  RCA_MATRIX_MODE=cartesian  legacy stage x compute x blocking matrix

Lane defaults (RCA_MATRIX_MODE=lanes):
  baseline,blocking,per_segment_light,dma_light,backend_alt
  stage:                    align
  base compute type:        int8
  alt compute type:         float16
  profiler backend:         rocprofv3
  profiler mode:            crash-capture
  profiler output mode:     rocpd
  profile stage policy:     first_compute
  memory-copy trace:        on (except dma_light)

Key env overrides:
  RCA_LANES="baseline blocking per_segment_light dma_light backend_alt"
  RCA_STAGE=align
  RCA_BASE_COMPUTE_TYPE=int8
  RCA_ALT_COMPUTE_TYPE=float16
  WHISPERX_BATCH_SIZE=1
  RCA_PER_SEGMENT_BATCH_SIZE=1
  RCA_PER_SEGMENT_WINDOW_S=10
  RCA_PER_SEGMENT_CHUNK_SIZE_S=10
  RCA_PER_SEGMENT_CONCURRENCY=1

Cartesian env overrides:
  RCA_STAGES="align diarize"
  RCA_COMPUTE_TYPES="int8 float16"
  RCA_BLOCKING_VALUES="0 1"
EOF
  exit 2
fi

mkdir -p "$OUT_ROOT"

AUDIO_PATH="$1"
shift || true

RCA_MATRIX_MODE="${RCA_MATRIX_MODE:-lanes}"
KEEP_SUCCESS="${KEEP_SUCCESS_TRACE:-0}"
MODEL="${WHISPERX_MODEL:-small}"
DEFAULT_BATCH_SIZE="${WHISPERX_BATCH_SIZE:-4}"

RCA_PROFILER_BACKEND="${RCA_PROFILER_BACKEND:-rocprofv3}"
RCA_PROFILER_MODE="${RCA_PROFILER_MODE:-crash-capture}"
RCA_OUTPUT_MODE="${RCA_OUTPUT_MODE:-rocpd}"
RCA_PROFILE_STAGE_POLICY="${RCA_PROFILE_STAGE_POLICY:-first_compute}"
RCA_STAGE="${RCA_STAGE:-align}"
RCA_BASE_COMPUTE_TYPE="${RCA_BASE_COMPUTE_TYPE:-int8}"
RCA_ALT_COMPUTE_TYPE="${RCA_ALT_COMPUTE_TYPE:-float16}"
RCA_ALT_PROFILER_BACKEND="${RCA_ALT_PROFILER_BACKEND:-$RCA_PROFILER_BACKEND}"
RCA_ENABLE_MEMORY_COPY_TRACE="${RCA_ENABLE_MEMORY_COPY_TRACE:-1}"

RCA_LANES_STRING="${RCA_LANES:-baseline blocking per_segment_light dma_light backend_alt}"
read -r -a RCA_LANES_ARRAY <<<"$RCA_LANES_STRING"

RCA_PER_SEGMENT_BATCH_SIZE="${RCA_PER_SEGMENT_BATCH_SIZE:-1}"
RCA_PER_SEGMENT_WINDOW_S="${RCA_PER_SEGMENT_WINDOW_S:-10}"
RCA_PER_SEGMENT_CHUNK_SIZE_S="${RCA_PER_SEGMENT_CHUNK_SIZE_S:-10}"
RCA_PER_SEGMENT_CONCURRENCY="${RCA_PER_SEGMENT_CONCURRENCY:-1}"

RCA_STAGES_STRING="${RCA_STAGES:-align diarize}"
RCA_COMPUTE_TYPES_STRING="${RCA_COMPUTE_TYPES:-int8 float16}"
RCA_BLOCKING_VALUES_STRING="${RCA_BLOCKING_VALUES:-0 1}"
read -r -a RCA_STAGES_ARRAY <<<"$RCA_STAGES_STRING"
read -r -a RCA_COMPUTE_TYPES_ARRAY <<<"$RCA_COMPUTE_TYPES_STRING"
read -r -a RCA_BLOCKING_VALUES_ARRAY <<<"$RCA_BLOCKING_VALUES_STRING"

echo "matrix_root,$OUT_ROOT" >"$SUMMARY_CSV"
echo "audio,$AUDIO_PATH" >>"$SUMMARY_CSV"
echo "mode,$RCA_MATRIX_MODE" >>"$SUMMARY_CSV"
echo "lane,stage,compute_type,hip_launch_blocking,memory_copy_trace,profiler_backend,profiler_mode,output_mode,profile_stage_policy,batch_size,segment_window_s,transcribe_chunk_size_s,transcribe_concurrency_hint,exit_code,kept_bundle,last_trace_dir" >>"$SUMMARY_CSV"

echo "Matrix output root: $OUT_ROOT"
echo "Audio: $AUDIO_PATH"
echo "Mode: $RCA_MATRIX_MODE"

collect_trace_args() {
  local -a input_args=("$@")
  local -a output_args=()
  local skip_next=0
  local arg
  for arg in "${input_args[@]}"; do
    if [ "$skip_next" -eq 1 ]; then
      skip_next=0
      continue
    fi
    case "$arg" in
      --int8|--float16|--float32)
        continue
        ;;
      --compute-type|--batch-size|--stage)
        skip_next=1
        continue
        ;;
      --compute-type=*|--batch-size=*|--stage=*)
        continue
        ;;
      *)
        output_args+=("$arg")
        ;;
    esac
  done
  printf '%s\n' "${output_args[@]}"
}

run_case() {
  local lane="$1"
  local stage="$2"
  local compute_type="$3"
  local hip_blocking="$4"
  local memory_copy_trace="$5"
  local profiler_backend="$6"
  local profiler_mode="$7"
  local output_mode="$8"
  local profile_stage_policy="$9"
  local batch_size="${10}"
  local segment_window_s="${11}"
  local transcribe_chunk_size_s="${12}"
  local transcribe_concurrency_hint="${13}"
  shift 13

  local case_root="$OUT_ROOT/lane=${lane}__stage=${stage}__compute=${compute_type}__blocking=${hip_blocking}"
  local trace_root="$case_root/traces"
  local before_list="$case_root/before.txt"
  local after_list="$case_root/after.txt"
  local exit_code=0
  local kept_bundle=0
  local last_trace_dir=""
  local -a raw_trace_args=("$@")
  local -a trace_args=()
  local line

  while IFS= read -r line; do
    if [ -n "$line" ]; then
      trace_args+=("$line")
    fi
  done < <(collect_trace_args "${raw_trace_args[@]}")

  mkdir -p "$case_root" "$trace_root"
  find "$trace_root" -mindepth 1 -maxdepth 1 -type d | sort >"$before_list" || true

  echo
  echo "== Case =="
  echo "lane=$lane stage=$stage compute_type=$compute_type HIP_LAUNCH_BLOCKING=$hip_blocking memcopy=$memory_copy_trace"

  set +e
  OUT_ROOT="$trace_root" \
  STAGE="$stage" \
  WHISPERX_COMPUTE_TYPE="$compute_type" \
  WHISPERX_MODEL="$MODEL" \
  WHISPERX_BATCH_SIZE="$batch_size" \
  HIP_LAUNCH_BLOCKING="$hip_blocking" \
  KEEP_SUCCESS_TRACE="$KEEP_SUCCESS" \
  USE_ROCPROF=1 \
  WHISPERX_PROFILER_BACKEND="$profiler_backend" \
  WHISPERX_PROFILER_MODE="$profiler_mode" \
  WHISPERX_ROCPROFV3_OUTPUT_MODE="$output_mode" \
  WHISPERX_PROFILE_STAGE_POLICY="$profile_stage_policy" \
  WHISPERX_ROCPROFV3_ENABLE_MEMORY_COPY_TRACE="$memory_copy_trace" \
  WHISPERX_SEGMENT_WINDOW_S="$segment_window_s" \
  WHISPERX_TRANSCRIBE_CHUNK_SIZE_S="$transcribe_chunk_size_s" \
  WHISPERX_TRANSCRIBE_CONCURRENCY="$transcribe_concurrency_hint" \
    bash "$TRACE_SCRIPT" "$AUDIO_PATH" "${trace_args[@]}"
  exit_code=$?
  set -e

  find "$trace_root" -mindepth 1 -maxdepth 1 -type d | sort >"$after_list" || true

  if ! diff -u "$before_list" "$after_list" >/dev/null 2>&1; then
    kept_bundle=1
    last_trace_dir="$(comm -13 "$before_list" "$after_list" | tail -n 1)"
  fi

  echo "$lane,$stage,$compute_type,$hip_blocking,$memory_copy_trace,$profiler_backend,$profiler_mode,$output_mode,$profile_stage_policy,$batch_size,$segment_window_s,$transcribe_chunk_size_s,$transcribe_concurrency_hint,$exit_code,$kept_bundle,$last_trace_dir" >>"$SUMMARY_CSV"
}

run_lane_mode() {
  echo "Lanes: ${RCA_LANES_ARRAY[*]}"
  local lane
  for lane in "${RCA_LANES_ARRAY[@]}"; do
    case "$lane" in
      baseline)
        run_case "baseline" "$RCA_STAGE" "$RCA_BASE_COMPUTE_TYPE" "0" "$RCA_ENABLE_MEMORY_COPY_TRACE" \
          "$RCA_PROFILER_BACKEND" "$RCA_PROFILER_MODE" "$RCA_OUTPUT_MODE" "$RCA_PROFILE_STAGE_POLICY" \
          "$DEFAULT_BATCH_SIZE" "" "" "" "$@"
        ;;
      blocking)
        run_case "blocking" "$RCA_STAGE" "$RCA_BASE_COMPUTE_TYPE" "1" "$RCA_ENABLE_MEMORY_COPY_TRACE" \
          "$RCA_PROFILER_BACKEND" "$RCA_PROFILER_MODE" "$RCA_OUTPUT_MODE" "$RCA_PROFILE_STAGE_POLICY" \
          "$DEFAULT_BATCH_SIZE" "" "" "" "$@"
        ;;
      per_segment_light)
        run_case "per_segment_light" "$RCA_STAGE" "$RCA_BASE_COMPUTE_TYPE" "0" "$RCA_ENABLE_MEMORY_COPY_TRACE" \
          "$RCA_PROFILER_BACKEND" "$RCA_PROFILER_MODE" "$RCA_OUTPUT_MODE" "$RCA_PROFILE_STAGE_POLICY" \
          "$RCA_PER_SEGMENT_BATCH_SIZE" "$RCA_PER_SEGMENT_WINDOW_S" "$RCA_PER_SEGMENT_CHUNK_SIZE_S" "$RCA_PER_SEGMENT_CONCURRENCY" "$@"
        ;;
      dma_light)
        run_case "dma_light" "$RCA_STAGE" "$RCA_BASE_COMPUTE_TYPE" "0" "0" \
          "$RCA_PROFILER_BACKEND" "$RCA_PROFILER_MODE" "$RCA_OUTPUT_MODE" "$RCA_PROFILE_STAGE_POLICY" \
          "$DEFAULT_BATCH_SIZE" "" "" "" "$@"
        ;;
      backend_alt)
        run_case "backend_alt" "$RCA_STAGE" "$RCA_ALT_COMPUTE_TYPE" "0" "$RCA_ENABLE_MEMORY_COPY_TRACE" \
          "$RCA_ALT_PROFILER_BACKEND" "$RCA_PROFILER_MODE" "$RCA_OUTPUT_MODE" "$RCA_PROFILE_STAGE_POLICY" \
          "$DEFAULT_BATCH_SIZE" "" "" "" "$@"
        ;;
      *)
        echo "ERROR: unknown RCA lane '$lane'" >&2
        exit 1
        ;;
    esac
  done
}

run_cartesian_mode() {
  echo "Stages: ${RCA_STAGES_ARRAY[*]}"
  echo "Compute types: ${RCA_COMPUTE_TYPES_ARRAY[*]}"
  echo "HIP_LAUNCH_BLOCKING: ${RCA_BLOCKING_VALUES_ARRAY[*]}"

  local stage compute_type hip_blocking
  for stage in "${RCA_STAGES_ARRAY[@]}"; do
    for compute_type in "${RCA_COMPUTE_TYPES_ARRAY[@]}"; do
      for hip_blocking in "${RCA_BLOCKING_VALUES_ARRAY[@]}"; do
        run_case "cartesian" "$stage" "$compute_type" "$hip_blocking" "$RCA_ENABLE_MEMORY_COPY_TRACE" \
          "$RCA_PROFILER_BACKEND" "$RCA_PROFILER_MODE" "$RCA_OUTPUT_MODE" "$RCA_PROFILE_STAGE_POLICY" \
          "$DEFAULT_BATCH_SIZE" "" "" "" "$@"
      done
    done
  done
}

case "$RCA_MATRIX_MODE" in
  lanes)
    run_lane_mode "$@"
    ;;
  cartesian)
    run_cartesian_mode "$@"
    ;;
  *)
    echo "ERROR: unknown RCA_MATRIX_MODE '$RCA_MATRIX_MODE' (use 'lanes' or 'cartesian')" >&2
    exit 1
    ;;
esac

echo
echo "Summary: $SUMMARY_CSV"
