#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

UPGRADE_DIR="${ROCM64_UPGRADE_OUTDIR:-$REPO_ROOT/artifacts/rocm64-upgrade}"
LATEST_DIR="${ROCM_LATEST_OUTDIR:-$REPO_ROOT/artifacts/rocm-latest}"

if [[ ! -d "$UPGRADE_DIR" ]]; then
  echo "ERROR: upgrade lane not found at $UPGRADE_DIR" >&2
  echo "Run scripts/clone-rocm64-upgrade-lane.sh first." >&2
  exit 1
fi

if [[ ! -d "$LATEST_DIR/docker-venv" ]]; then
  echo "ERROR: latest Python artifacts not found at $LATEST_DIR/docker-venv" >&2
  echo "Finish scripts/extract-rocm-latest-artifacts.sh first." >&2
  exit 1
fi

mkdir -p "$UPGRADE_DIR/meta"

copy_tree() {
  local src="$1"
  local dest="$2"
  if command -v rsync >/dev/null 2>&1; then
    mkdir -p "$dest"
    rsync -a --delete "$src"/ "$dest"/
  else
    rm -rf "$dest"
    mkdir -p "$(dirname "$dest")"
    cp -a "$src" "$dest"
  fi
}

echo "Swapping Python/PyTorch layer into $UPGRADE_DIR"
echo "  source: $LATEST_DIR/docker-venv"
echo "  target: $UPGRADE_DIR/docker-venv"

copy_tree "$LATEST_DIR/docker-venv" "$UPGRADE_DIR/docker-venv"

cat > "$UPGRADE_DIR/meta/python-layer-source.txt" <<EOF
timestamp=$(date -Iseconds)
source_lane=$LATEST_DIR
source_component=docker-venv
target_lane=$UPGRADE_DIR
swap_group=python-pytorch
EOF

echo ""
echo "Python/PyTorch layer copied from latest source into the 6.4-upgrade lane."
echo "Next steps:"
echo "  bash scripts/host-rocm64-upgrade-python.sh -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'"
echo "  bash scripts/capture-leech-minimal-repros.sh --runner scripts/host-rocm64-upgrade-python.sh --label rocm64-upgrade"
