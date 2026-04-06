#!/usr/bin/env bash
set -euo pipefail

OUT_FILE="${1:?Usage: bash scripts/watch-host-cpu-hotspots.sh /path/to/output.log}"
POLL_INTERVAL="${POLL_INTERVAL:-1}"
TOP_N="${TOP_N:-12}"

mkdir -p "$(dirname "$OUT_FILE")"

echo "# host cpu hotspot watch" >>"$OUT_FILE"
echo "# poll_interval=${POLL_INTERVAL}s top_n=$TOP_N" >>"$OUT_FILE"

while true; do
  {
    printf '\n[%s]\n' "$(date -Iseconds)"
    ps -eo pid,ppid,pcpu,pmem,stat,comm,args --sort=-pcpu | head -n "$((TOP_N + 1))"
  } >>"$OUT_FILE"
  sleep "$POLL_INTERVAL"
done
