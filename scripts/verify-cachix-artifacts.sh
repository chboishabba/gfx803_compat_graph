#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
MANIFEST_PATH="${CACHIX_MANIFEST_PATH:-$REPO_ROOT/cachix-artifacts.manifest}"
MODE="${VERIFY_MODE:-head}"

usage() {
  cat <<'USAGE'
Usage: verify-cachix-artifacts.sh [--head|--copy]

Checks that every store path listed in cachix-artifacts.manifest is available
from the configured Cachix binary cache.

Modes:
  --head  Verify only that each .narinfo exists in the cache (default).
  --copy  Also run `nix copy --from <cache>` for each store path.

Environment:
  CACHIX_MANIFEST_PATH  Override manifest path.
  VERIFY_MODE           Default mode when no flag is passed: "head" or "copy".
USAGE
}

if [ ! -f "$MANIFEST_PATH" ]; then
  echo "ERROR: Manifest not found: $MANIFEST_PATH" >&2
  exit 1
fi

case "${1:-}" in
  "")
    ;;
  --head)
    MODE="head"
    ;;
  --copy)
    MODE="copy"
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    echo "ERROR: Unknown argument: $1" >&2
    usage >&2
    exit 1
    ;;
esac

case "$MODE" in
  head|copy)
    ;;
  *)
    echo "ERROR: VERIFY_MODE must be 'head' or 'copy', got: $MODE" >&2
    exit 1
    ;;
esac

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: 'curl' is required and was not found." >&2
  exit 1
fi

if [ "$MODE" = "copy" ] && ! command -v nix >/dev/null 2>&1; then
  echo "ERROR: 'nix' is required for --copy mode and was not found." >&2
  exit 1
fi

cache_url="$(awk -F= '/^# cache_url=/{print $2; exit}' "$MANIFEST_PATH")"

if [ -z "$cache_url" ]; then
  echo "ERROR: cache_url missing from $MANIFEST_PATH" >&2
  exit 1
fi

checked=0
head_ok=0
copy_ok=0
failures=0

while IFS=$'\t' read -r rel_path store_path; do
  [ -n "${rel_path:-}" ] || continue
  case "$rel_path" in
    \#*) continue ;;
  esac

  if [[ ! "$store_path" =~ ^/nix/store/ ]]; then
    echo "FAIL invalid store path for $rel_path: $store_path"
    failures=$((failures + 1))
    continue
  fi

  nar_hash="$(basename "$store_path")"
  nar_hash="${nar_hash%%-*}"
  narinfo_url="${cache_url%/}/${nar_hash}.narinfo"

  checked=$((checked + 1))
  echo "Checking $rel_path"

  if curl -fsSI "$narinfo_url" >/dev/null; then
    echo "  HEAD ok: $store_path"
    head_ok=$((head_ok + 1))
  else
    echo "  FAIL missing narinfo: $narinfo_url"
    failures=$((failures + 1))
    continue
  fi

  if [ "$MODE" = "copy" ]; then
    if nix copy --from "$cache_url" "$store_path" >/dev/null; then
      echo "  COPY ok"
      copy_ok=$((copy_ok + 1))
    else
      echo "  FAIL nix copy: $store_path"
      failures=$((failures + 1))
    fi
  fi
done < "$MANIFEST_PATH"

echo
echo "Summary:"
echo "  checked:  $checked"
echo "  head ok:  $head_ok"
if [ "$MODE" = "copy" ]; then
  echo "  copy ok:  $copy_ok"
fi
echo "  failures: $failures"

if [ "$failures" -ne 0 ]; then
  exit 1
fi
