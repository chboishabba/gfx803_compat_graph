#!/usr/bin/env bash
# Check that the narrowly-scoped gfx803 TensorTopK patch applies to the exact
# PyTorch source used by the imported Schaka ROCm 10.1 candidate.  This script
# deliberately does not alter a source checkout or build a wheel.
set -euo pipefail

readonly EXPECTED_REV="d70fd61bab718a3d49b053efa8058efc0566b2b0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly WARP_PATCH="$SCRIPT_DIR/../patches/pytorch/gfx803-disable-warptopk.patch"
readonly SORT_PATCH="$SCRIPT_DIR/../patches/pytorch/gfx803-topk-sort-fallback.patch"

usage() {
  cat <<'EOF'
Usage: verify-schaka-pytorch-topk-patch.sh --source /path/to/ROCm-pytorch

Checks the source revision and runs `git apply --check` only. It does not
modify SOURCE. The subsequent wheel build must record both patch hashes and
TENSOR_TOPK_OPT_LEVEL=-O0 in its receipt.
EOF
}

SOURCE=""
while (($#)); do
  case "$1" in
    --source) SOURCE="${2:?missing source path}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$SOURCE" ]] || { usage >&2; exit 2; }
[[ -f "$WARP_PATCH" ]] || { echo "Missing patch: $WARP_PATCH" >&2; exit 2; }
[[ -f "$SORT_PATCH" ]] || { echo "Missing patch: $SORT_PATCH" >&2; exit 2; }
git -C "$SOURCE" rev-parse --is-inside-work-tree >/dev/null
REV="$(git -C "$SOURCE" rev-parse HEAD)"
[[ "$REV" == "$EXPECTED_REV" ]] || {
  echo "Expected PyTorch $EXPECTED_REV; found $REV" >&2
  exit 1
}
git -C "$SOURCE" apply --check "$WARP_PATCH"
git -C "$SOURCE" apply --check "$SORT_PATCH"
printf 'patches_apply=true\nsource_revision=%s\nwarp_patch_sha256=%s\nsort_patch_sha256=%s\n' \
  "$REV" "$(sha256sum "$WARP_PATCH" | awk '{print $1}')" \
  "$(sha256sum "$SORT_PATCH" | awk '{print $1}')"
