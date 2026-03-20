#!/usr/bin/env bash
set -euo pipefail

IMAGE="${ROCM_LATEST_IMAGE:-rocm/pytorch}"
TAG="${ROCM_LATEST_TAG:-latest}"
OUTDIR="${1:-${ROCM_LATEST_OUTDIR:-artifacts/rocm-latest}}"

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

if ! docker run --help >/dev/null 2>&1; then
  echo "ERROR: docker command is not working." >&2
  exit 1
fi

echo "Preparing ROCm latest artifact extraction"
echo "  image: $IMAGE:$TAG"
echo "  outdir: $OUTDIR_ABS"
echo ""

if [[ -d "$OUTDIR_ABS/docker-venv" ]]; then
  echo "Clearing previous latest venv payload at $OUTDIR/docker-venv to avoid stale ownership/perms"
  if ! rm -rf "$OUTDIR_ABS/docker-venv" 2>/dev/null; then
    echo "Host cleanup blocked; retrying via container helper..."
    docker run --rm \
      -v "$OUTDIR_ABS:/work" \
      --entrypoint "" \
      "$IMAGE:$TAG" \
      bash -lc 'rm -rf /work/docker-venv'
  fi
fi

if ! docker image inspect "$IMAGE:$TAG" >/dev/null 2>&1; then
  echo "Local image $IMAGE:$TAG not found. Pulling it now..."
  docker pull "$IMAGE:$TAG"
fi

bash "$SCRIPT_DIR/extract_artifacts.sh" "$IMAGE" "$TAG" "$OUTDIR_ABS"

echo ""
echo "Latest ROCm artifacts are ready under $OUTDIR_ABS"
echo "Next step:"
echo "  bash scripts/host-rocm-latest-python.sh -c 'import torch; print(torch.cuda.is_available())'"
