#!/usr/bin/env bash
# Keep a persistent, container-based Ollama GPU service on gfx803 without repeated fetches.

set -euo pipefail

IMAGE="${OLLAMA_IMAGE:-robertrosenbusch/rocm6_gfx803_ollama}"
TAG="${OLLAMA_TAG:-6.4.3_0.11.5}"
FULL_IMAGE="${IMAGE}:${TAG}"
CONTAINER_NAME="${OLLAMA_CONTAINER_NAME:-gfx803-ollama}"
HOST_PORT="${OLLAMA_HOST_PORT:-11434}"
DEFAULT_CACHE_ROOT="${OLLAMA_CACHE_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/gfx803-ollama}"
CACHE_ROOT="$DEFAULT_CACHE_ROOT"
RUNTIME_UID="${OLLAMA_DOCKER_UID:-$(id -u)}"
RUNTIME_GID="${OLLAMA_DOCKER_GID:-$(id -g)}"
RUNTIME_HOME="/workspace/.ollama"
RUN_WEBUI=0
RESTART_EXISTING=0
COMMAND_ARGS=(serve)

show_help() {
  cat <<USAGE
Usage:
  run-gfx803-ollama-container.sh [--with-webui] [--name <container>] [--port <port>] [--root <dir>] [--restart] [--stop]

Defaults:
  image: robertrosenbusch/rocm6_gfx803_ollama:6.4.3_0.11.5
  name:  gfx803-ollama
  port:  11434
  root:  ${DEFAULT_CACHE_ROOT}

Notes:
  - default mode starts only the Ollama binary (no Open WebUI, no repeated install fetch).
  - add --with-webui to run the image default ol_serve.sh wrapper.
  - to recreate an existing container instead of reusing it, pass --restart.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-webui)
      RUN_WEBUI=1
      shift
      ;;
    --name)
      CONTAINER_NAME="$2"
      shift 2
      ;;
    --port)
      HOST_PORT="$2"
      shift 2
      ;;
    --root)
      CACHE_ROOT="$2"
      shift 2
      ;;
    --stop)
      if docker ps -a --format '{{.Names}}' | rg -qx "$CONTAINER_NAME"; then
        docker rm -f "$CONTAINER_NAME"
      fi
      exit 0
      ;;
    --restart)
      RESTART_EXISTING=1
      shift
      ;;
    --help|-h)
      show_help
      exit 0
      ;;
    --)
      shift
      COMMAND_ARGS+=("$@")
      break
      ;;
    *)
      COMMAND_ARGS+=("$1")
      shift
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FALLBACK_CACHE_ROOT="$REPO_ROOT/.cache/gfx803-ollama"
if [ -e "$CACHE_ROOT" ] && [ ! -w "$CACHE_ROOT" ]; then
  CACHE_ROOT="$FALLBACK_CACHE_ROOT"
elif [ -e "$CACHE_ROOT" ] || mkdir -p "$CACHE_ROOT" 2>/dev/null; then
  :
elif [ -w "$HOME" ] && [ ! -e "$CACHE_ROOT" ]; then
  mkdir -p "${CACHE_ROOT%/*}" || true
  if ! mkdir -p "$CACHE_ROOT" 2>/dev/null; then
    CACHE_ROOT="$FALLBACK_CACHE_ROOT"
  fi
fi

if ! mkdir -p "$CACHE_ROOT"; then
  echo "ERROR: cannot create cache root '$CACHE_ROOT'. Set OLLAMA_CACHE_ROOT to a writable directory and rerun."
  exit 1
fi
if [ "$CACHE_ROOT" != "$DEFAULT_CACHE_ROOT" ] && [ ! -w "$CACHE_ROOT" ]; then
  echo "ERROR: cache root '$CACHE_ROOT' is not writable. Set OLLAMA_CACHE_ROOT to a writable directory."
  exit 1
fi

OLLAMA_MODELS_DIR="$CACHE_ROOT/.ollama"
OPENWEBUI_DATA_DIR="$CACHE_ROOT/open-webui"
mkdir -p "$OLLAMA_MODELS_DIR" "$OPENWEBUI_DATA_DIR"

if docker ps -a --format '{{.Names}}' | rg -qx "$CONTAINER_NAME"; then
  if docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null | rg -qx true && [[ "$RESTART_EXISTING" -eq 0 ]]; then
    echo "Container '$CONTAINER_NAME' is already running."
    echo "Reusing it and its cache at: $OLLAMA_MODELS_DIR"
    echo "To force recreate (including env flags): bash $0 --restart"
    echo "To stop: bash $0 --stop"
    exit 0
  fi
  docker rm -f "$CONTAINER_NAME"
fi

DOCKER_OPTS=(
  --name "$CONTAINER_NAME"
  --device=/dev/kfd
  --device=/dev/dri
  --group-add=video
  --ipc=host
  --user "${RUNTIME_UID}:${RUNTIME_GID}"
  -p "127.0.0.1:${HOST_PORT}:11434"
  -e HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-8.0.3}"
  -e ROC_ENABLE_PRE_VEGA="${ROC_ENABLE_PRE_VEGA:-1}"
  -e OLLAMA_HOST="0.0.0.0:11434"
  -e HOME="$RUNTIME_HOME"
  -e OLLAMA_HOME="$RUNTIME_HOME"
  -e OLLAMA_MODELS="$RUNTIME_HOME/models"
  -e OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-5m}"
  -e OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-0}"
  -v "$OLLAMA_MODELS_DIR:$RUNTIME_HOME"
)

if (( RUN_WEBUI == 1 )); then
  docker run -d --rm \
    "${DOCKER_OPTS[@]}" \
    -e DATA_DIR="/open-webui-data" \
    -v "$OPENWEBUI_DATA_DIR:/open-webui-data" \
    "$FULL_IMAGE" \
    "${COMMAND_ARGS[@]}"
else
  docker run -d --rm \
    --entrypoint /ollama/ollama \
    "${DOCKER_OPTS[@]}" \
    "$FULL_IMAGE" \
    "${COMMAND_ARGS[@]}"
fi

echo "Started $FULL_IMAGE as $CONTAINER_NAME on 127.0.0.1:${HOST_PORT}"
echo "Model cache: $OLLAMA_MODELS_DIR"
echo
echo "Use:"
echo "  OLLAMA_HOST=http://127.0.0.1:${HOST_PORT} ollama pull mistral:7b"
echo "  OLLAMA_HOST=http://127.0.0.1:${HOST_PORT} ollama run mistral:7b 'Once upon a time Lila'"
