#!/usr/bin/env bash
set -euo pipefail

IMAGE="${ROCM64_OLDABI_IMAGE:-robertrosenbusch/rocm6_gfx803_ollama}"
TAG="${ROCM64_OLDABI_TAG:-6.4.3_0.11.5}"
OUTDIR="${1:-${ROCM64_OLDABI_SDK_OUTDIR:-artifacts/rocm64-oldabi-sdk}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

if [[ "$OUTDIR" = /* ]]; then
  OUTDIR_ABS="$OUTDIR"
else
  OUTDIR_ABS="$REPO_ROOT/$OUTDIR"
fi

mkdir -p "$OUTDIR_ABS"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker binary not found in PATH." >&2
  exit 1
fi

if ! docker image inspect "$IMAGE:$TAG" >/dev/null 2>&1; then
  echo "ERROR: image $IMAGE:$TAG not present locally." >&2
  echo "Pull it first or set ROCM64_OLDABI_IMAGE/ROCM64_OLDABI_TAG." >&2
  exit 1
fi

echo "Preparing old-ABI ROCm SDK extraction"
echo "  image: $IMAGE:$TAG"
echo "  outdir: $OUTDIR_ABS"

cleanup_host_dir_contents() {
  local host_dir="$1"
  mkdir -p "$host_dir"
  if rm -rf "${host_dir:?}/"* 2>/dev/null; then
    return 0
  fi
  docker run --rm \
    -v "$host_dir:/work" \
    --entrypoint "" \
    "$IMAGE:$TAG" \
    bash -lc 'rm -rf /work/*'
}

extract_dir_from_container() {
  local image_path="$1"
  local host_dir="$2"

  if ! docker run --rm --entrypoint "" "$IMAGE:$TAG" sh -lc "[ -d '$image_path' ]" >/dev/null 2>&1; then
    return 0
  fi

  mkdir -p "$host_dir"
  cleanup_host_dir_contents "$host_dir"

  docker run --rm --entrypoint "" "$IMAGE:$TAG" sh -lc "cd '$image_path' && tar -cf - ." \
    | tar --no-same-owner --no-same-permissions -C "$host_dir" -xpf -
}

extract_file_from_container() {
  local image_path="$1"
  local host_path="$2"
  local host_dir
  host_dir="$(dirname "$host_path")"
  mkdir -p "$host_dir"
  docker run --rm --entrypoint "" "$IMAGE:$TAG" sh -lc "[ -f '$image_path' ]" >/dev/null 2>&1 || return 0
  docker run --rm --entrypoint "" "$IMAGE:$TAG" sh -lc "cat '$image_path'" > "$host_path"
}

extract_dir_from_container "/opt/rocm" "$OUTDIR_ABS/opt-rocm"
extract_dir_from_container "/opt/amdgpu" "$OUTDIR_ABS/opt-amdgpu"
extract_file_from_container "/etc/os-release" "$OUTDIR_ABS/meta/os-release"

cat > "$OUTDIR_ABS/meta/source.txt" <<EOF
lane=rocm64-oldabi-sdk
source_image=$IMAGE:$TAG
extracted_at=$(date -Iseconds)
contents=/opt/rocm plus optional /opt/amdgpu payload from working 6.4 lineage
purpose=coherent old-HSA/HIP ABI SDK root for framework rebuilds
EOF

echo "Old-ABI ROCm SDK extracted to $OUTDIR_ABS"
echo "Use with:"
echo "  FRAMEWORK_REBUILD_ROCM_ROOT=$OUTDIR_ABS/opt-rocm"
