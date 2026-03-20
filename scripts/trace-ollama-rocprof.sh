#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_ROOT="${OUT_ROOT:-$ROOT_DIR/out/ollama-trace}"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
OUT_DIR="$OUT_ROOT/$STAMP"
WATCH_DIR="$OUT_DIR/devcoredump-watch"
TRACE_CSV="$OUT_DIR/rocprof-hip-trace.csv"
ENV_LOG="$OUT_DIR/env.txt"
CMD_LOG="$OUT_DIR/command.txt"
OLLAMA_BIN="${OLLAMA_BIN:-$ROOT_DIR/artifacts/ollama_reference/ollama-bin/ollama}"

mkdir -p "$OUT_DIR"

MODEL="${1:-mistral}"
shift || true
PROMPT_ARGS=("$@")

if ! command -v rocprof >/dev/null 2>&1; then
  echo "ERROR: rocprof not found in PATH" >&2
  exit 1
fi

if [ -x "$OLLAMA_BIN" ]; then
  OLLAMA_CMD=(bash "$ROOT_DIR/scripts/run-ollama-reference-host.sh")
elif command -v ollama >/dev/null 2>&1; then
  OLLAMA_CMD=(ollama)
else
  echo "ERROR: ollama not found in PATH and extracted reference binary not found at $OLLAMA_BIN" >&2
  exit 1
fi

export HSA_ENABLE_SDMA="${HSA_ENABLE_SDMA:-0}"
export AMD_LOG_LEVEL="${AMD_LOG_LEVEL:-2}"
export ROCBLAS_LAYER="${ROCBLAS_LAYER:-3}"
export HIP_TRACE_API="${HIP_TRACE_API:-1}"

cat >"$ENV_LOG" <<EOF
STAMP=$STAMP
OUT_DIR=$OUT_DIR
MODEL=$MODEL
HSA_ENABLE_SDMA=$HSA_ENABLE_SDMA
AMD_LOG_LEVEL=$AMD_LOG_LEVEL
ROCBLAS_LAYER=$ROCBLAS_LAYER
HIP_TRACE_API=$HIP_TRACE_API
EOF

{
  printf 'rocprof --hip-trace --timestamp on --basenames on -o %q ollama run %q' "$TRACE_CSV" "$MODEL"
  for arg in "${PROMPT_ARGS[@]}"; do
    printf ' %q' "$arg"
  done
  printf '\n'
} >"$CMD_LOG"
printf 'ollama command source: %s\n' "${OLLAMA_CMD[*]}" >>"$CMD_LOG"

WATCH_PID=""
cleanup() {
  if [[ -n "$WATCH_PID" ]] && kill -0 "$WATCH_PID" 2>/dev/null; then
    kill "$WATCH_PID" 2>/dev/null || true
    wait "$WATCH_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Output directory: $OUT_DIR"
echo "Starting devcoredump watcher..."
OUT_ROOT="$WATCH_DIR" POLL_INTERVAL="${POLL_INTERVAL:-0.05}" \
  bash "$ROOT_DIR/scripts/watch-amdgpu-devcoredump.sh" >"$OUT_DIR/devcoredump-watch.log" 2>&1 &
WATCH_PID="$!"

sleep 0.2

echo "Running Ollama under rocprof..."
exec rocprof --hip-trace --timestamp on --basenames on -o "$TRACE_CSV" \
  "${OLLAMA_CMD[@]}" run "$MODEL" "${PROMPT_ARGS[@]}"
