#!/usr/bin/env bash
# serve-ollama-gfx803.sh
# Convenience launcher: start the extracted gfx803-ready Ollama server on host.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Polaris overrides (gfx803 / RX 580)
source "$REPO_ROOT/scripts/polaris-env.sh"

# Delegate to the extracted host runner; defaults to artifacts/ollama_reference
exec "$REPO_ROOT/scripts/run-ollama-reference-host.sh" serve "$@"
