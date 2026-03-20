#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CACHE_NAME="${CACHIX_CACHE:-gfx803-rocm}"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [artifact-dir...]

Uploads artifact directories to the ${CACHE_NAME} Cachix cache.

If no paths are provided, uploads the repository's standard extracted payloads that exist:
- lib-compat
- docker-venv
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
    "$REPO_ROOT/artifacts/ollama_reference"
    "$REPO_ROOT/artifacts/rocm57"
    "$REPO_ROOT/artifacts/rocm-latest"
  )
else
  ARTIFACT_PATHS=("$@")
fi

TO_UPLOAD=()
for path in "${ARTIFACT_PATHS[@]}"; do
  if [ ! -e "$path" ]; then
    echo "INFO: skipping missing path: $path" >&2
    continue
  fi

  if [ ! -d "$path" ]; then
    echo "WARN: $path exists but is not a directory; skipping" >&2
    continue
  fi

  store_path=$(nix store add-path "$path")
  echo "Mapped $(realpath "$path") -> $store_path"
  TO_UPLOAD+=("$store_path")

done

if [ "${#TO_UPLOAD[@]}" -eq 0 ]; then
  echo "No artifact directories found to upload." >&2
  usage >&2
  exit 1
fi

cachix push "$CACHE_NAME" "${TO_UPLOAD[@]}"

echo "Done. Uploaded ${#TO_UPLOAD[@]} path(s) to Cachix cache '$CACHE_NAME'."
