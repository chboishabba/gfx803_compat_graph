#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
TORCH_HOME_DIR="${TORCH_HOME:-$REPO_ROOT/.cache/torch}"
HUB_DIR="$TORCH_HOME_DIR/hub"
REPO_MAIN_DIR="$HUB_DIR/snakers4_silero-vad_main"
REPO_MASTER_DIR="$HUB_DIR/snakers4_silero-vad_master"
TRUSTED_LIST="$HUB_DIR/trusted_list"

mkdir -p "$HUB_DIR"

if [ -d "$REPO_MAIN_DIR/.git" ]; then
  echo "Updating existing Silero VAD cache at $REPO_MAIN_DIR"
  git -C "$REPO_MAIN_DIR" pull --ff-only
elif [ -d "$REPO_MAIN_DIR" ]; then
  echo "ERROR: $REPO_MAIN_DIR exists but is not a git checkout" >&2
  exit 1
else
  echo "Cloning Silero VAD into $REPO_MAIN_DIR"
  git clone https://github.com/snakers4/silero-vad "$REPO_MAIN_DIR"
fi

ln -sfn "$REPO_MAIN_DIR" "$REPO_MASTER_DIR"

touch "$TRUSTED_LIST"
if ! grep -qx 'snakers4_silero-vad' "$TRUSTED_LIST"; then
  printf 'snakers4_silero-vad\n' >>"$TRUSTED_LIST"
fi

echo "Silero VAD torch.hub cache ready:"
echo "  TORCH_HOME=$TORCH_HOME_DIR"
echo "  main=$REPO_MAIN_DIR"
echo "  master=$REPO_MASTER_DIR"
