#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
RUNNER="$REPO_ROOT/scripts/host-docker-python.sh"
LABEL="rocm64"
CHECKPOINT="${LEECH_CHECKPOINT:-/home/c/Documents/code/DASHIg/LeechTransformer/data/best_model.pt}"
PROMPT_IDS="${LEECH_PROMPT_IDS:-353,656,602,262,678,357,440,1988}"
VOCAB_SIZE="${LEECH_VOCAB_SIZE:-2048}"
OUT_ROOT="${LEECH_MIN_REPRO_OUTDIR:-$REPO_ROOT/out/leech-min-repros}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --runner)
      RUNNER="$2"
      shift 2
      ;;
    --label)
      LABEL="$2"
      shift 2
      ;;
    --checkpoint)
      CHECKPOINT="$2"
      shift 2
      ;;
    --prompt-ids)
      PROMPT_IDS="$2"
      shift 2
      ;;
    --vocab-size)
      VOCAB_SIZE="$2"
      shift 2
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
OUTDIR="$OUT_ROOT/$LABEL/$STAMP"
mkdir -p "$OUTDIR"

run_case() {
  local name="$1"
  shift
  echo "Running $name"
  {
    echo "runner=$RUNNER"
    echo "name=$name"
    echo "started_at=$(date -Iseconds)"
    echo "command=$*"
    echo
    "$@"
  } > "$OUTDIR/$name.log" 2>&1
}

run_case live_layout \
  bash "$RUNNER" "$REPO_ROOT/scripts/debug-leech-attn-layout-repeat.py" \
  --checkpoint "$CHECKPOINT" \
  --prompt-ids "$PROMPT_IDS" \
  --vocab-size "$VOCAB_SIZE" \
  --repeats 5

run_case live_layout_blocking \
  env HIP_LAUNCH_BLOCKING=1 bash "$RUNNER" "$REPO_ROOT/scripts/debug-leech-attn-layout-repeat.py" \
  --checkpoint "$CHECKPOINT" \
  --prompt-ids "$PROMPT_IDS" \
  --vocab-size "$VOCAB_SIZE" \
  --repeats 5

TENSOR_PATH="$OUTDIR/attn_weighted.pt"
run_case dump_tensor \
  bash "$RUNNER" "$REPO_ROOT/scripts/dump-leech-attn-weighted.py" \
  --checkpoint "$CHECKPOINT" \
  --prompt-ids "$PROMPT_IDS" \
  --vocab-size "$VOCAB_SIZE" \
  --output "$TENSOR_PATH"

run_case saved_tensor \
  bash "$RUNNER" "$REPO_ROOT/scripts/debug-attn-layout-from-tensor.py" \
  --tensor "$TENSOR_PATH" \
  --device cuda \
  --repeats 5

run_case first_step \
  bash "$RUNNER" "$REPO_ROOT/scripts/debug-leech-first-step-from-ids.py" \
  --checkpoint "$CHECKPOINT" \
  --prompt-ids "$PROMPT_IDS" \
  --vocab-size "$VOCAB_SIZE" \
  --repeats 3

{
  echo "label=$LABEL"
  echo "runner=$RUNNER"
  echo "checkpoint=$CHECKPOINT"
  echo "prompt_ids=$PROMPT_IDS"
  echo "vocab_size=$VOCAB_SIZE"
  echo "created_at=$(date -Iseconds)"
  echo "output_dir=$OUTDIR"
} > "$OUTDIR/meta.txt"

echo "$OUTDIR"
