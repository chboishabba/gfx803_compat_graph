#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

CONTROL_LIBDIR="${CONTROL_LIBDIR:-$REPO_ROOT/lib-compat}"
LATEST_LIBDIR="${LATEST_LIBDIR:-$REPO_ROOT/artifacts/rocm-latest/lib-compat}"
OUT_ROOT="${OUT_ROOT:-$REPO_ROOT/artifacts/rocm-runtime-hybrids}"

if [[ ! -d "$CONTROL_LIBDIR" ]]; then
  echo "ERROR: control lib directory not found: $CONTROL_LIBDIR" >&2
  exit 1
fi

if [[ ! -d "$LATEST_LIBDIR" ]]; then
  echo "ERROR: latest lib directory not found: $LATEST_LIBDIR" >&2
  exit 1
fi

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

prepare_lane() {
  local lane="$1"
  shift
  local lane_dir="$OUT_ROOT/$lane"
  rm -rf "$lane_dir"
  mkdir -p "$lane_dir/meta"
  cp -a "$LATEST_LIBDIR"/. "$lane_dir/"
  copy_matches "$CONTROL_LIBDIR" "$lane_dir" "$@"
  {
    echo "lane=$lane"
    echo "created_at=$(date -Iseconds)"
    echo "control_libdir=$CONTROL_LIBDIR"
    echo "latest_libdir=$LATEST_LIBDIR"
    echo "control_overlay_patterns=$*"
  } > "$lane_dir/meta/source.txt"
}

mkdir -p "$OUT_ROOT"

prepare_lane \
  oldhsa_oldaql \
  'libhsa-runtime64.so*' \
  'libhsa-amd-aqlprofile64.so*'

prepare_lane \
  oldhsa_oldprof \
  'libhsa-runtime64.so*' \
  'librocprofiler-register.so*' \
  'librocprofiler64*' \
  'librocprofiler64v2*' \
  'librocprofiler-sdk*' \
  'libroctracer64.so*' \
  'libroctx64.so*'

prepare_lane \
  oldhsa_fullcluster \
  'libhsa-runtime64.so*' \
  'libhsa-amd-aqlprofile64.so*' \
  'librocprofiler-register.so*' \
  'librocprofiler64*' \
  'librocprofiler64v2*' \
  'librocprofiler-sdk*' \
  'libroctracer64.so*' \
  'libroctx64.so*'

echo "Created hybrid runtime lanes under $OUT_ROOT"
find "$OUT_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '  %f\n' | sort
