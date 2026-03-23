#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SRC_COMPAT_DIR="${SRC_COMPAT_DIR:-$REPO_ROOT/lib-compat}"
SRC_VENV_DIR="${SRC_VENV_DIR:-$REPO_ROOT/docker-venv}"
OUTDIR="${1:-${ROCM64_UPGRADE_OUTDIR:-$REPO_ROOT/artifacts/rocm64-upgrade}}"

if [ ! -d "$SRC_COMPAT_DIR" ] || [ ! -d "$SRC_VENV_DIR" ]; then
  echo "ERROR: source 6.4 runtime not found." >&2
  echo "Expected: $SRC_COMPAT_DIR and $SRC_VENV_DIR" >&2
  echo "Run scripts/extract-docker-libs.sh first." >&2
  exit 1
fi

mkdir -p "$OUTDIR" "$OUTDIR/meta"

copy_tree() {
  local src="$1"
  local dst="$2"
  rm -rf "$dst"
  mkdir -p "$(dirname "$dst")"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$src/" "$dst/"
  else
    cp -a "$src" "$dst"
  fi
}

copy_tree "$SRC_COMPAT_DIR" "$OUTDIR/lib-compat"
copy_tree "$SRC_VENV_DIR" "$OUTDIR/docker-venv"

{
  echo "source_compat=$SRC_COMPAT_DIR"
  echo "source_venv=$SRC_VENV_DIR"
  echo "created_at=$(date -Iseconds)"
  echo "note=clone of extracted 6.4 lane for incremental newer-component swaps"
} > "$OUTDIR/meta/source.txt"

echo "Cloned 6.4 runtime into $OUTDIR"
echo "Next step:"
echo "  bash scripts/host-rocm64-upgrade-python.sh -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'"
