#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

UPGRADE_DIR="${ROCM64_UPGRADE_OUTDIR:-$REPO_ROOT/artifacts/rocm64-upgrade}"
LATEST_DIR="${ROCM_LATEST_OUTDIR:-$REPO_ROOT/artifacts/rocm-latest}"
TARGET_LIB_DIR="$UPGRADE_DIR/lib-compat"
SOURCE_LIB_DIR="$LATEST_DIR/lib-compat"

if [[ ! -d "$TARGET_LIB_DIR" ]]; then
  echo "ERROR: upgrade lane libs not found at $TARGET_LIB_DIR" >&2
  echo "Run scripts/clone-rocm64-upgrade-lane.sh first." >&2
  exit 1
fi

if [[ ! -d "$SOURCE_LIB_DIR" ]]; then
  echo "ERROR: latest compat libs not found at $SOURCE_LIB_DIR" >&2
  echo "Finish scripts/extract-rocm-latest-artifacts.sh first." >&2
  exit 1
fi

mkdir -p "$UPGRADE_DIR/meta"

echo "Syncing full lib-compat from latest into $UPGRADE_DIR"
echo "  source: $SOURCE_LIB_DIR"
echo "  target: $TARGET_LIB_DIR"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "$SOURCE_LIB_DIR"/ "$TARGET_LIB_DIR"/
else
  rm -rf "$TARGET_LIB_DIR"
  mkdir -p "$TARGET_LIB_DIR"
  cp -a "$SOURCE_LIB_DIR"/. "$TARGET_LIB_DIR"/
fi

cat > "$UPGRADE_DIR/meta/full-lib-compat-source.txt" <<EOF
timestamp=$(date -Iseconds)
source_lane=$LATEST_DIR
source_component=lib-compat
target_lane=$UPGRADE_DIR
swap_group=full-lib-compat
EOF

echo ""
echo "Full lib-compat synced from latest source into the 6.4-upgrade lane."
echo "Next step:"
echo "  bash scripts/host-rocm64-upgrade-python.sh -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'"
