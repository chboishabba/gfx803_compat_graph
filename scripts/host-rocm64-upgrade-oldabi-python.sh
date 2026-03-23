#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

export ROCM64_UPGRADE_LIB_ROOT="${ROCM64_UPGRADE_LIB_ROOT:-$REPO_ROOT/artifacts/rocm64-upgrade-oldabi}"

exec "$SCRIPT_DIR/host-rocm64-upgrade-frozen-python.sh" "$@"
