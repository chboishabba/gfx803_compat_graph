#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
MANIFEST_PATH="${CACHIX_MANIFEST_PATH:-$REPO_ROOT/cachix-artifacts.manifest}"
CACHE_NAME="${CACHIX_CACHE:-gfx803-rocm}"
KEEP_MODE="${CACHIX_PIN_KEEP_MODE:-revisions}"
KEEP_VALUE="${CACHIX_PIN_KEEP_VALUE:-1}"
PIN_PREFIX="${CACHIX_PIN_PREFIX:-artifact}"

usage() {
  cat <<'USAGE'
Usage: pin-cachix-artifacts.sh

Pins every store path listed in cachix-artifacts.manifest so Cachix garbage
collection does not evict the active artifact set.

Environment:
  CACHIX_MANIFEST_PATH    Override manifest path.
  CACHIX_CACHE            Cachix cache name. Default: gfx803-rocm
  CACHIX_PIN_PREFIX       Prefix for generated pin names. Default: artifact
  CACHIX_PIN_KEEP_MODE    One of: revisions, days, forever. Default: revisions
  CACHIX_PIN_KEEP_VALUE   Value for revisions/days mode. Default: 1
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if [ ! -f "$MANIFEST_PATH" ]; then
  echo "ERROR: Manifest not found: $MANIFEST_PATH" >&2
  exit 1
fi

if ! command -v cachix >/dev/null 2>&1; then
  echo "ERROR: 'cachix' is required and was not found." >&2
  exit 1
fi

case "$KEEP_MODE" in
  revisions)
    KEEP_ARGS=(--keep-revisions "$KEEP_VALUE")
    ;;
  days)
    KEEP_ARGS=(--keep-days "$KEEP_VALUE")
    ;;
  forever)
    KEEP_ARGS=(--keep-forever)
    ;;
  *)
    echo "ERROR: CACHIX_PIN_KEEP_MODE must be revisions, days, or forever." >&2
    exit 1
    ;;
esac

pins=0

while IFS=$'\t' read -r rel_path store_path; do
  [ -n "${rel_path:-}" ] || continue
  case "$rel_path" in
    \#*) continue ;;
  esac

  pin_name="$PIN_PREFIX-$(printf '%s' "$rel_path" | tr '/._' '-')"
  echo "Pinning $rel_path as $pin_name"
  cachix pin "$CACHE_NAME" "$pin_name" "$store_path" "${KEEP_ARGS[@]}"
  pins=$((pins + 1))
done < "$MANIFEST_PATH"

echo "Done. Pinned $pins artifact path(s) in cache '$CACHE_NAME'."
