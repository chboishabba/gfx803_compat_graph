#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SRC_BASE="${SRC_BASE:-$REPO_ROOT/lib-compat}"
LATEST_BASE="${LATEST_BASE:-$REPO_ROOT/artifacts/rocm-latest/lib-compat}"
OUTDIR="${1:-${ROCM64_SAFE_SUPPORT_OUTDIR:-$REPO_ROOT/artifacts/rocm64-upgrade-safe-support}}"

SAFE_PATTERNS=(
  "libamd_comgr.so*"
  "librocm-core.so*"
  "libelf.so*"
  "libnuma.so*"
  "libdrm.so*"
  "libdrm_amdgpu.so*"
  "libdrm_radeon.so*"
)

if [ ! -d "$SRC_BASE" ] || [ ! -d "$LATEST_BASE" ]; then
  echo "ERROR: expected source compat directories are missing." >&2
  echo "  SRC_BASE=$SRC_BASE" >&2
  echo "  LATEST_BASE=$LATEST_BASE" >&2
  echo "Run scripts/extract-docker-libs.sh and scripts/extract-rocm-latest-artifacts.sh first." >&2
  exit 1
fi

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

mkdir -p "$OUTDIR" "$OUTDIR/meta"
copy_tree "$SRC_BASE" "$OUTDIR/lib-compat"

for pattern in "${SAFE_PATTERNS[@]}"; do
  shopt -s nullglob
  matches=("$LATEST_BASE"/$pattern)
  shopt -u nullglob
  if [ "${#matches[@]}" -eq 0 ]; then
    echo "ERROR: no latest matches found for pattern: $pattern" >&2
    exit 1
  fi
  for match in "${matches[@]}"; do
    cp -a "$match" "$OUTDIR/lib-compat/"
  done
done

{
  echo "source_base=$SRC_BASE"
  echo "source_latest=$LATEST_BASE"
  echo "created_at=$(date -Iseconds)"
  echo "kind=rocm64-upgrade-safe-support"
  echo "note=control 6.4 compat base plus upgraded low-risk support libs only"
  echo "overlays=${SAFE_PATTERNS[*]}"
} > "$OUTDIR/meta/source.txt"

echo "Created safe-support upgrade lane at $OUTDIR"
echo "Next step:"
echo "  bash scripts/host-rocm64-upgrade-safe-support-python.sh -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'"
