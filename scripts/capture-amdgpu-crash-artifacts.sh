#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

SINCE_ARG="${1:-10 minutes ago}"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
OUTDIR="${CRASH_OUTDIR:-$REPO_ROOT/out/crashlogs/$STAMP}"

mkdir -p "$OUTDIR"

# Preserve the kernel log first. It is the least risky source and often
# references the exact devcoredump path the driver created.
journalctl -k -b --since "$SINCE_ARG" --no-pager > "$OUTDIR/kernel-journal.txt"

find_live_devcoredump() {
  find /sys/class/drm -maxdepth 6 -path '*/device/devcoredump/data' 2>/dev/null | head -n 1
}

dump_path="$(find_live_devcoredump || true)"

if [ -n "$dump_path" ]; then
  dump_dir="$(dirname "$dump_path")"
  printf '%s\n' "$dump_path" > "$OUTDIR/devcoredump-path.txt"
  ls -la "$dump_dir" > "$OUTDIR/devcoredump-ls.txt" 2>&1 || true

  # Copy the binary payload once, without printing it to the terminal.
  dd if="$dump_path" of="$OUTDIR/amdgpu-devcoredump.bin" bs=1M status=none

  for meta in uevent; do
    if [ -f "$dump_dir/$meta" ]; then
      cp "$dump_dir/$meta" "$OUTDIR/$meta.txt"
    fi
  done
else
  printf '%s\n' "No live /sys/class/drm/*/device/devcoredump/data node found." > "$OUTDIR/devcoredump-status.txt"
fi

echo "$OUTDIR"
