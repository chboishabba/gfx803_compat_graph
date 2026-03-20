#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

OUT_ROOT="${CRASH_OUTDIR_ROOT:-$REPO_ROOT/out/crashlogs/live-watch}"
POLL_INTERVAL="${POLL_INTERVAL:-0.2}"
mkdir -p "$OUT_ROOT"

find_live_devcoredump() {
  find /sys/class/drm -maxdepth 6 -path '*/device/devcoredump/data' 2>/dev/null | head -n 1
}

echo "Watching for amdgpu devcoredump nodes..."
echo "Output root: $OUT_ROOT"
echo "Poll interval: ${POLL_INTERVAL}s"

last_seen=""

while true; do
  dump_path="$(find_live_devcoredump || true)"

  if [ -n "$dump_path" ] && [ "$dump_path" != "$last_seen" ]; then
    stamp="$(date +%Y-%m-%dT%H-%M-%S)"
    outdir="$OUT_ROOT/$stamp"
    dump_dir="$(dirname "$dump_path")"

    mkdir -p "$outdir"
    printf '%s\n' "$dump_path" > "$outdir/devcoredump-path.txt"
    ls -la "$dump_dir" > "$outdir/devcoredump-ls.txt" 2>&1 || true
    journalctl -k -b --since '5 minutes ago' --no-pager > "$outdir/kernel-journal.txt" || true

    # Copy the live payload once without sending it to the terminal.
    if dd if="$dump_path" of="$outdir/amdgpu-devcoredump.bin" bs=1M status=none 2>"$outdir/dd.stderr.txt"; then
      echo "Captured devcoredump to $outdir"
    else
      echo "Found devcoredump but copy failed; see $outdir/dd.stderr.txt" >&2
    fi

    for meta in uevent; do
      if [ -f "$dump_dir/$meta" ]; then
        cp "$dump_dir/$meta" "$outdir/$meta.txt"
      fi
    done

    last_seen="$dump_path"
  elif [ -z "$dump_path" ]; then
    last_seen=""
  fi

  sleep "$POLL_INTERVAL"
done
