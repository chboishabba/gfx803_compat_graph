#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CACHE_NAME="${CACHIX_CACHE:-gfx803-rocm}"
CACHE_URL="${CACHIX_URL:-https://${CACHE_NAME}.cachix.org}"
CACHE_PUBLIC_KEY="${CACHIX_PUBLIC_KEY:-gfx803-rocm.cachix.org-1:UTaIREqPZa9yjY7hiMBYG556OrGR6WEhWPjqX4Us3us=}"
MANIFEST_PATH="${CACHIX_MANIFEST_PATH:-$REPO_ROOT/cachix-artifacts.manifest}"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [artifact-dir...]

Uploads artifact directories to the ${CACHE_NAME} Cachix cache.
Also refreshes ${MANIFEST_PATH} so a fresh clone can relink the same store paths.

If no paths are provided, uploads the repository's standard extracted payloads that exist:
- lib-compat
- docker-venv
- artifacts/rocm64-upgrade
- artifacts/rocm64-upgrade-oldabi
- artifacts/rocm64-oldabi-sdk
- artifacts/rocm64-upgrade-safe-support
- artifacts/ollama_reference
- artifacts/rocm57
- artifacts/rocm-latest
USAGE
}

if ! command -v nix >/dev/null 2>&1; then
  echo "ERROR: 'nix' is required for nix-store/import and was not found." >&2
  exit 1
fi

if ! command -v cachix >/dev/null 2>&1; then
  echo "ERROR: 'cachix' is required for upload and was not found." >&2
  exit 1
fi

if [ "$#" -eq 0 ]; then
  ARTIFACT_PATHS=(
    "$REPO_ROOT/lib-compat"
    "$REPO_ROOT/docker-venv"
    "$REPO_ROOT/artifacts/rocm64-upgrade"
    "$REPO_ROOT/artifacts/rocm64-upgrade-oldabi"
    "$REPO_ROOT/artifacts/rocm64-oldabi-sdk"
    "$REPO_ROOT/artifacts/rocm64-upgrade-safe-support"
    "$REPO_ROOT/artifacts/ollama_reference"
    "$REPO_ROOT/artifacts/rocm57"
    "$REPO_ROOT/artifacts/rocm-latest"
  )
else
  ARTIFACT_PATHS=("$@")
fi

TO_UPLOAD=()
MANIFEST_LINES=()
for path in "${ARTIFACT_PATHS[@]}"; do
  if [ ! -e "$path" ]; then
    echo "INFO: skipping missing path: $path" >&2
    continue
  fi

  if [ ! -d "$path" ]; then
    echo "WARN: $path exists but is not a directory; skipping" >&2
    continue
  fi

  abs_path="$(realpath "$path")"
  store_path=$(nix store add-path "$abs_path")
  echo "Mapped $abs_path -> $store_path"
  TO_UPLOAD+=("$store_path")

  if [[ "$abs_path" == "$REPO_ROOT/"* ]]; then
    MANIFEST_LINES+=("${abs_path#"$REPO_ROOT/"}"$'\t'"$store_path")
  else
    echo "INFO: skipping manifest entry for external path: $abs_path" >&2
  fi

done

if [ "${#TO_UPLOAD[@]}" -eq 0 ]; then
  echo "No artifact directories found to upload." >&2
  usage >&2
  exit 1
fi

{
  echo "# cache_name=$CACHE_NAME"
  echo "# cache_url=$CACHE_URL"
  echo "# public_key=$CACHE_PUBLIC_KEY"
  printf '%s\n' "${MANIFEST_LINES[@]}"
} > "$MANIFEST_PATH"

if [ "${WRITE_MANIFEST_ONLY:-0}" != "1" ]; then
  cachix push "$CACHE_NAME" "${TO_UPLOAD[@]}"
  echo "Done. Uploaded ${#TO_UPLOAD[@]} path(s) to Cachix cache '$CACHE_NAME'."
else
  echo "Done. Refreshed manifest only at $MANIFEST_PATH."
fi
