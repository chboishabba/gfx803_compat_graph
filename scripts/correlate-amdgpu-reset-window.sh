#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/correlate-amdgpu-reset-window.sh --since "2026-03-25 21:42:00" --until "2026-03-25 21:45:30" [--boot -1]

Options:
  --since TIME       Required. journalctl-compatible start time.
  --until TIME       Required. journalctl-compatible end time.
  --boot BOOT        Optional. journalctl boot selector. Default: -1.
  --dump-dir DIR     Optional. Dump directory. Default: /var/log/amdgpu-devcoredumps.
  -h, --help         Show this help.
EOF
}

SINCE=""
UNTIL=""
BOOT="-1"
DUMP_DIR="/var/log/amdgpu-devcoredumps"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --since)
      SINCE="${2:-}"
      shift 2
      ;;
    --until)
      UNTIL="${2:-}"
      shift 2
      ;;
    --boot)
      BOOT="${2:-}"
      shift 2
      ;;
    --dump-dir)
      DUMP_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$SINCE" ] || [ -z "$UNTIL" ]; then
  echo "--since and --until are required." >&2
  usage >&2
  exit 2
fi

since_key="$(date -d "$SINCE" +%Y%m%d-%H%M%S)"
until_key="$(date -d "$UNTIL" +%Y%m%d-%H%M%S)"

print_section() {
  printf '\n== %s ==\n' "$1"
}

print_section "Window"
printf 'boot:   %s\n' "$BOOT"
printf 'since:  %s\n' "$SINCE"
printf 'until:  %s\n' "$UNTIL"
printf 'dumps:  %s\n' "$DUMP_DIR"

print_section "Kernel"
journalctl -k -b "$BOOT" --since "$SINCE" --until "$UNTIL" --no-pager \
  | rg "amdgpu|drm|kfd|devcoredump|reset|ring|VRAM|BACO|timeout|gfx|parser|wedged" || true

print_section "Service"
journalctl -u amdgpu-devcoredump.service -b "$BOOT" --since "$SINCE" --until "$UNTIL" --no-pager || true

print_section "Dump Files"
if [ -d "$DUMP_DIR" ]; then
  found=0
  while IFS= read -r path; do
    base="$(basename "$path")"
    stamp="$(printf '%s\n' "$base" | sed -n 's/.*-\([0-9]\{8\}-[0-9]\{6\}\)\.bin$/\1/p')"
    if [ -z "$stamp" ]; then
      continue
    fi
    if [[ "$stamp" < "$since_key" || "$stamp" > "$until_key" ]]; then
      continue
    fi
    found=1
    ls -lh --time-style=long-iso "$path"
  done < <(find "$DUMP_DIR" -maxdepth 1 -type f -name '*-devcoredump-*.bin' | sort)

  if [ "$found" -eq 0 ]; then
    echo "No dump files matched the requested window."
  fi
else
  echo "Dump directory does not exist: $DUMP_DIR"
fi
