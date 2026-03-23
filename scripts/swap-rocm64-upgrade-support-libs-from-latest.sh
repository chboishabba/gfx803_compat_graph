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

copy_matches() {
  local pattern="$1"
  shopt -s nullglob
  local matches=("$SOURCE_LIB_DIR"/$pattern)
  shopt -u nullglob
  for src in "${matches[@]}"; do
    cp -a "$src" "$TARGET_LIB_DIR/"
  done
}

echo "Swapping non-math ROCm support libs into $UPGRADE_DIR"
echo "  source: $SOURCE_LIB_DIR"
echo "  target: $TARGET_LIB_DIR"

for pattern in \
  'libhsa-runtime64.so*' \
  'libamdhip64.so*' \
  'libhiprtc.so*' \
  'libhiprtc-builtins.so*' \
  'libamd_comgr.so*' \
  'librocm-core.so*' \
  'libdrm.so*' \
  'libdrm_amdgpu.so*' \
  'libdrm_radeon.so*' \
  'libelf.so*' \
  'libnuma.so*'
do
  copy_matches "$pattern"
done

cat > "$UPGRADE_DIR/meta/support-libs-source.txt" <<EOF
timestamp=$(date -Iseconds)
source_lane=$LATEST_DIR
source_component=lib-compat
target_lane=$UPGRADE_DIR
swap_group=non-math-support-libs
EOF

echo ""
echo "Non-math ROCm support libs copied from latest source into the 6.4-upgrade lane."
echo "Next step:"
echo "  bash scripts/host-rocm64-upgrade-python.sh -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'"
