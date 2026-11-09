#!/usr/bin/env bash
# Check that the narrowly-scoped gfx803 TensorTopK patch applies to the exact
# PyTorch source used by the imported Schaka ROCm 10.1 candidate.  This script
# deliberately does not alter a source checkout or build a wheel.
set -euo pipefail

readonly EXPECTED_REV="d70fd61bab718a3d49b053efa8058efc0566b2b0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PATCH_FILE="$SCRIPT_DIR/../patches/pytorch/gfx803-disable-warptopk.patch"

usage() {
  cat <<'EOF'
Usage: verify-schaka-pytorch-topk-patch.sh --source /path/to/ROCm-pytorch

Checks the source revision and runs `git apply --check` only.  It does not
modify SOURCE.  The subsequent wheel build must record both this patch hash
and TENSOR_TOPK_OPT_LEVEL=-O0 in its receipt.
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
[[ -f "$PATCH_FILE" ]] || { echo "Missing patch: $PATCH_FILE" >&2; exit 2; }
git -C "$SOURCE" rev-parse --is-inside-work-tree >/dev/null
REV="$(git -C "$SOURCE" rev-parse HEAD)"
[[ "$REV" == "$EXPECTED_REV" ]] || {
  echo "Expected PyTorch $EXPECTED_REV; found $REV" >&2
  exit 1
}
git -C "$SOURCE" apply --check "$PATCH_FILE"
printf 'patch_applies=true\nsource_revision=%s\npatch_sha256=%s\n' \
  "$REV" "$(sha256sum "$PATCH_FILE" | awk '{print $1}')"
