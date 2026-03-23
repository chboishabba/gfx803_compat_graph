#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
BASE_LANE="${BASE_LANE:-$REPO_ROOT/artifacts/rocm64-upgrade-safe-support}"
LATEST_LIBDIR="${LATEST_LIBDIR:-$REPO_ROOT/artifacts/rocm-latest/lib-compat}"
OUT_ROOT="${OUT_ROOT:-$REPO_ROOT/artifacts/rocm64-upgrade-math-profiles}"
RUNNER="${RUNNER:-$REPO_ROOT/scripts/host-rocm64-upgrade-frozen-python.sh}"

usage() {
  cat <<'USAGE'
Usage: probe-rocm64-oldhip-math-subsets.sh [--list] [profile...]

Creates per-profile compat overlays on top of the safe-support lane, then runs
a quick torch import / GPU visibility check using the frozen framework layer.

Profiles:
  rocblas_only
  hipblas_only
  hipblaslt_only
  hipsparse_only
  hipsolver_only
  rocsparse_only
  rocsolver_only
  miopen_only
  rocblas_bundle
USAGE
}

list_profiles() {
  cat <<'EOF'
rocblas_only
hipblas_only
hipblaslt_only
hipsparse_only
hipsolver_only
rocsparse_only
rocsolver_only
miopen_only
rocblas_bundle
EOF
}

profile_patterns() {
  case "$1" in
    rocblas_only) echo "librocblas.so*" ;;
    hipblas_only) echo "libhipblas.so*" ;;
    hipblaslt_only) echo "libhipblaslt.so*" ;;
    hipsparse_only) echo "libhipsparse.so*" ;;
    hipsolver_only) echo "libhipsolver.so*" ;;
    rocsparse_only) echo "librocsparse.so*" ;;
    rocsolver_only) echo "librocsolver.so*" ;;
    miopen_only) echo "libMIOpen.so*" ;;
    rocblas_bundle) echo "librocblas.so* libhipblas.so* libhipblaslt.so*" ;;
    *) return 1 ;;
  esac
}

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

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--list" ]]; then
  list_profiles
  exit 0
fi

if [ ! -d "$BASE_LANE/lib-compat" ] || [ ! -d "$LATEST_LIBDIR" ]; then
  echo "ERROR: expected lane/lib directories are missing." >&2
  echo "  BASE_LANE=$BASE_LANE" >&2
  echo "  LATEST_LIBDIR=$LATEST_LIBDIR" >&2
  exit 1
fi

if [ ! -x "$RUNNER" ]; then
  echo "ERROR: runner not executable: $RUNNER" >&2
  exit 1
fi

if [ "$#" -eq 0 ]; then
  mapfile -t PROFILES < <(list_profiles)
else
  PROFILES=("$@")
fi

mkdir -p "$OUT_ROOT"

for profile in "${PROFILES[@]}"; do
  if ! pattern_str="$(profile_patterns "$profile")"; then
    echo "ERROR: unknown profile: $profile" >&2
    exit 1
  fi

  lane_dir="$OUT_ROOT/$profile"
  copy_tree "$BASE_LANE/lib-compat" "$lane_dir/lib-compat"
  mkdir -p "$lane_dir/meta"

  read -r -a patterns <<<"$pattern_str"
  for pattern in "${patterns[@]}"; do
    shopt -s nullglob
    matches=("$LATEST_LIBDIR"/$pattern)
    shopt -u nullglob
    if [ "${#matches[@]}" -eq 0 ]; then
      echo "ERROR: no latest matches found for pattern $pattern in profile $profile" >&2
      exit 1
    fi
    for match in "${matches[@]}"; do
      cp -a "$match" "$lane_dir/lib-compat/"
    done
  done

  {
    echo "profile=$profile"
    echo "base_lane=$BASE_LANE"
    echo "latest_libdir=$LATEST_LIBDIR"
    echo "created_at=$(date -Iseconds)"
    echo "overlays=${patterns[*]}"
  } > "$lane_dir/meta/source.txt"

  {
    echo "== profile: $profile =="
    echo "== overlays: ${patterns[*]} =="
    ROCM64_UPGRADE_LIB_ROOT="$lane_dir" "$RUNNER" -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'
  } > "$lane_dir/meta/import-check.txt" 2>&1 || true

  echo "Wrote $lane_dir/meta/import-check.txt"
done
