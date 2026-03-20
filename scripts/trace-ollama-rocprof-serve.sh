#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_ROOT="${OUT_ROOT:-$ROOT_DIR/out/ollama-trace-serve}"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
OUT_DIR="$OUT_ROOT/$STAMP"
WATCH_DIR="$OUT_DIR/devcoredump-watch"
TRACE_CSV="$OUT_DIR/rocprof-hip-trace.csv"
ENV_LOG="$OUT_DIR/env.txt"
CMD_LOG="$OUT_DIR/command.txt"
OLLAMA_BIN="${OLLAMA_BIN:-$ROOT_DIR/artifacts/ollama_reference/ollama-bin/ollama}"
TRACE_OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"

TRACE_OLLAMA_PORT="${TRACE_OLLAMA_HOST##*:}"
if ! [[ "$TRACE_OLLAMA_PORT" =~ ^[0-9]+$ ]]; then
  TRACE_OLLAMA_PORT=11434
fi

if command -v ss >/dev/null 2>&1 && ss -ltnH 2>/dev/null | awk '{print $4}' | rg -q ":${TRACE_OLLAMA_PORT}$"; then
  echo "WARNING: TCP port $TRACE_OLLAMA_PORT appears in use."
  echo "If this is another Ollama server, stop it first or set OLLAMA_HOST to an alternate port before tracing."
  echo "Example: OLLAMA_HOST=127.0.0.1:11435 bash scripts/trace-ollama-rocprof-serve.sh"
fi

mkdir -p "$OUT_DIR"

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

# Polaris overrides (gfx803 / RX 580)
source "$ROOT_DIR/scripts/polaris-env.sh"

export HSA_ENABLE_SDMA="${HSA_ENABLE_SDMA:-0}"
export AMD_LOG_LEVEL="${AMD_LOG_LEVEL:-3}"
export ROCBLAS_LAYER="${ROCBLAS_LAYER:-3}"
export HIP_TRACE_API="${HIP_TRACE_API:-1}"

cat >"$ENV_LOG" <<EOF
STAMP=$STAMP
OUT_DIR=$OUT_DIR
OLLAMA_HOST=$TRACE_OLLAMA_HOST
HSA_ENABLE_SDMA=$HSA_ENABLE_SDMA
AMD_LOG_LEVEL=$AMD_LOG_LEVEL
ROCBLAS_LAYER=$ROCBLAS_LAYER
HIP_TRACE_API=$HIP_TRACE_API
EOF

printf -v OLLAMA_CMD_STR '%q ' "${OLLAMA_CMD[@]}"
echo "rocprof --hip-trace --timestamp on --basenames on -o $TRACE_CSV ${OLLAMA_CMD_STR} serve" >"$CMD_LOG"
echo "ollama command source: ${OLLAMA_CMD[*]}" >>"$CMD_LOG"

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

echo "Running Ollama serve under rocprof..."
echo "Press Ctrl+C to stop normally after your run."
for item in "${OLLAMA_CMD[@]}" "$@"; do
  printf '%q ' "$item"
done
echo
export OLLAMA_HOST="$TRACE_OLLAMA_HOST"
exec rocprof --hip-trace --timestamp on --basenames on -o "$TRACE_CSV" \
  "${OLLAMA_CMD[@]}" serve "$@"
