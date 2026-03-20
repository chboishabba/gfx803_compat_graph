#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
MANIFEST_PATH="${CACHIX_MANIFEST_PATH:-$REPO_ROOT/cachix-artifacts.manifest}"

if [ ! -f "$MANIFEST_PATH" ]; then
  echo "ERROR: Manifest not found: $MANIFEST_PATH" >&2
  echo "Run the publish helper on a machine that already has the extracted artifacts." >&2
  exit 1
fi

if ! command -v nix >/dev/null 2>&1; then
  echo "ERROR: 'nix' is required and was not found." >&2
  exit 1
fi

cache_url="$(awk -F= '/^# cache_url=/{print $2; exit}' "$MANIFEST_PATH")"

if [ -z "$cache_url" ]; then
  echo "ERROR: cache_url missing from $MANIFEST_PATH" >&2
  exit 1
fi

while IFS=$'\t' read -r rel_path store_path; do
  [ -n "${rel_path:-}" ] || continue
  case "$rel_path" in
    \#*) continue ;;
  esac

  target="$REPO_ROOT/$rel_path"
  parent_dir="$(dirname "$target")"

  echo "Restoring $rel_path from $store_path"
  nix copy --from "$cache_url" "$store_path" >/dev/null
  mkdir -p "$parent_dir"

  if [ -L "$target" ]; then
    rm -f "$target"
  elif [ -e "$target" ]; then
    if [ "${RESTORE_FORCE:-0}" != "1" ]; then
      echo "ERROR: $target already exists. Re-run with RESTORE_FORCE=1 to replace it." >&2
      exit 1
    fi
    rm -rf "$target"
  fi

  ln -s "$store_path" "$target"
done < "$MANIFEST_PATH"

echo "Done. Restored artifact links from Cachix into $REPO_ROOT."
