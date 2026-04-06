#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

CONTROL_LIBDIR="${CONTROL_LIBDIR:-$REPO_ROOT/lib-compat}"
LATEST_LIBDIR="${LATEST_LIBDIR:-$REPO_ROOT/artifacts/rocm-latest/lib-compat}"
OUT_ROOT="${OUT_ROOT:-$REPO_ROOT/artifacts/rocm64-upgrade-oldabi}"

if [[ ! -d "$CONTROL_LIBDIR" ]]; then
  echo "ERROR: control lib directory not found: $CONTROL_LIBDIR" >&2
  exit 1
fi

if [[ ! -d "$LATEST_LIBDIR" ]]; then
  echo "ERROR: latest lib directory not found: $LATEST_LIBDIR" >&2
  exit 1
fi

TARGET_LIBDIR="$OUT_ROOT/lib-compat"
mkdir -p "$OUT_ROOT/meta"
rm -rf "$TARGET_LIBDIR"
mkdir -p "$TARGET_LIBDIR"
cp -a "$CONTROL_LIBDIR"/. "$TARGET_LIBDIR"/

copy_matches() {
  local src_root="$1"
  local dst_root="$2"
  shift 2
  local pattern
  for pattern in "$@"; do
    shopt -s nullglob
    local matches=("$src_root"/$pattern)
    shopt -u nullglob
    for src in "${matches[@]}"; do
      cp -a "$src" "$dst_root/"
    done
  done
}

# Preserve the working old HSA/HIP ABI from the control lane.
# Overlay only low-risk support components from the latest extraction.
copy_matches "$LATEST_LIBDIR" "$TARGET_LIBDIR" \
  'libamd_comgr.so*' \
  'librocm-core.so*' \
  'libelf.so*' \
  'libnuma.so*' \
  'libdrm.so*' \
  'libdrm_amdgpu.so*' \
  'libdrm_radeon.so*'

create_compat_symlink() {
  local link_name="$1"
  local target_name="$2"
  ln -sfn "$target_name" "$TARGET_LIBDIR/$link_name"
}

# The preserved old-ABI lane already carries the older sonames that the rebuilt
# torch tree expects. Add explicit compatibility aliases for the newer sonames
# that appeared during direct runtime smoke so the lane stays reproducible.
create_compat_symlink libamdhip64.so.7 libamdhip64.so.6
create_compat_symlink libhipblas.so.3 libhipblas.so.2
create_compat_symlink libhipsparse.so.4 libhipsparse.so.1
create_compat_symlink librocblas.so.5 librocblas.so.4
create_compat_symlink libhipblaslt.so.1 libhipblaslt.so.0
create_compat_symlink libhipsolver.so.1 libhipsolver.so.0

cat > "$OUT_ROOT/meta/source.txt" <<EOF
lane=rocm64-upgrade-oldabi
created_at=$(date -Iseconds)
base=control-6.4-lib-compat
preserved_abi=hsa/hip
latest_overlay=libamd_comgr librocm-core libelf libnuma libdrm libdrm_amdgpu libdrm_radeon
compat_shims=libamdhip64.so.7->libamdhip64.so.6 libhipblas.so.3->libhipblas.so.2 libhipsparse.so.4->libhipsparse.so.1 librocblas.so.5->librocblas.so.4 libhipblaslt.so.1->libhipblaslt.so.0 libhipsolver.so.1->libhipsolver.so.0
notes=primary short-term upgrade lane; preserves old HSA/HIP ABI, upgrades around it deliberately, and carries explicit newer-soname aliases for torch runtime loading
EOF

echo "Created old-ABI preserved upgrade lane at $OUT_ROOT"
echo "Primary runtime ABI remains from control 6.4."
