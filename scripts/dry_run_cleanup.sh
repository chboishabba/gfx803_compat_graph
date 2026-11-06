#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

section() {
  echo
  echo "== $1 =="
}

show_matches() {
  local pattern="$1"
  local matched=0

  shopt -s nullglob
  local paths=( $pattern )
  shopt -u nullglob

  if ((${#paths[@]} == 0)); then
    echo "(none matched: $pattern)"
    return
  fi

  for path in "${paths[@]}"; do
    matched=1
    du -sh "$path" 2>/dev/null
  done

  if ((matched == 0)); then
    echo "(none matched: $pattern)"
  fi
}

list_group() {
  local label="$1"
  shift
  section "$label"
  for pattern in "$@"; do
    show_matches "$pattern"
  done
}

group_bytes() {
  local total=0
  local pattern

  for pattern in "$@"; do
    shopt -s nullglob
    local paths=( $pattern )
    shopt -u nullglob

    local path
    for path in "${paths[@]}"; do
      if [[ -e "$path" ]]; then
        local size_kib
        size_kib=$(du -sk "$path" 2>/dev/null | awk '{print $1}')
        total=$((total + size_kib * 1024))
      fi
    done
  done

  echo "$total"
}

human_bytes() {
  local bytes="$1"
  awk -v bytes="$bytes" '
    function human(x) {
      split("B KiB MiB GiB TiB", units, " ")
      i = 1
      while (x >= 1024 && i < length(units)) {
        x /= 1024
        i++
      }
      return sprintf("%.1f %s", x, units[i])
    }
    BEGIN { print human(bytes) }
  '
}

total_group() {
  local label="$1"
  shift
  section "$label (TOTAL)"
  local bytes
  bytes=$(group_bytes "$@")
  echo "approx total: $(human_bytes "$bytes")"
}

doc_refs_for_pattern() {
  local pattern="$1"
  local had_refs=0

  shopt -s nullglob
  local paths=( $pattern )
  shopt -u nullglob

  local path
  for path in "${paths[@]}"; do
    local clean_path="${path#./}"
    local refs
    refs=$(rg -n -F "$clean_path" README.md docs 2>/dev/null || true)
    if [[ -n "$refs" ]]; then
      if ((had_refs == 0)); then
        echo "references for $pattern:"
      fi
      had_refs=1
      echo "$refs"
    fi
  done

  if ((had_refs == 0)); then
    echo "no README/docs references found for $pattern"
  fi
}

reference_check_group() {
  local label="$1"
  shift
  section "$label"
  local pattern
  for pattern in "$@"; do
    doc_refs_for_pattern "$pattern"
  done
}

SAFE_DELETE_PATTERNS=(
  "artifacts/rocm-runtime-probes*"
  "artifacts/rocm64-upgrade-math-profiles/"
  "artifacts/pytorch-framework-rebuild-*"
)

HOLD_PATTERNS=(
  "artifacts/rocm-runtime-hybrids/"
  "out/whisperx-rca-matrix/"
  "out/whisperx-trace/"
  ".rocprofv3/"
)

KEEP_PATTERNS=(
  "lib-compat/"
  "docker-venv/"
  "artifacts/rocm57/"
  "artifacts/rocm64-upgrade-oldabi/"
  "artifacts/rocm64-upgrade-safe-support/"
  "artifacts/ollama_reference/"
)

echo "ROOT: $(pwd)"
echo "This is a DRY RUN. Nothing will be deleted."

list_group "RCA: runtime-boundary discovery (SAFE DELETE)" "${SAFE_DELETE_PATTERNS[@]}"
total_group "RCA: runtime-boundary discovery" "${SAFE_DELETE_PATTERNS[@]}"

list_group "RCA: workload-correctness / evidence (HOLD)" "${HOLD_PATTERNS[@]}"
total_group "RCA: workload-correctness / evidence" "${HOLD_PATTERNS[@]}"

list_group "RCA: runtime / accepted lanes (KEEP)" "${KEEP_PATTERNS[@]}"
total_group "RCA: runtime / accepted lanes" "${KEEP_PATTERNS[@]}"

reference_check_group "Doc reference check for HOLD group" "${HOLD_PATTERNS[@]}"

echo
echo "Tip: keep paths that are still referenced by retained RCA docs until those references are moved or rewritten."
