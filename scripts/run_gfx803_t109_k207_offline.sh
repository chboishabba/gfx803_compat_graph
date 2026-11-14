#!/usr/bin/env bash
# One-command read-only RX580 T1.09/T1.10/T1.11 + K2.07/K2.08 suite.
# No torch import, HIP calls, GPU workload, active tracing, root or kernel changes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="/mnt/truenas/comet-net/experiments/gfx803_t109_k207_20261114"
if [[ $# -ge 1 ]]; then OUT="$1"; fi
if [[ -e "$OUT" ]]; then
  echo "REFUSING TO OVERWRITE: $OUT (choose unused output directory)" >&2
  exit 2
fi

HSACO="$(printenv HSACO || true)"
if [[ -z "$HSACO" ]]; then
  HSACO="/mnt/truenas/comet-net/experiments/gfx803_t108_offload_20261114/gfx803.hsaco"
fi
BASE="$(printenv TOPK_BASE || true)"
if [[ -z "$BASE" ]]; then
  BASE="/mnt/truenas/comet-net/.gfx803-schaka-101-work/out/pytorch-topk-gfx803-20261109"
fi
SOURCE="$(printenv TOPK_SOURCE || true)"
if [[ -z "$SOURCE" ]]; then SOURCE="$BASE/hip-audit-r3/TensorTopK.hip"; fi
RECEIPT="docs/receipts/gfx803_k205_t104_source_binary_attribution_20261114.json"
C="docs/receipts/gfx803_t105_t108_host_20261114"

for file in "$HSACO" "$SOURCE" "$RECEIPT" \
    "$C/fatbin_container.json" "$C/mbtopk_elf_inventory.json" \
    "$C/kfd_topk_join.json"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing input: $file" >&2
    exit 2
  fi
done

echo "Running all offline regression contracts (no GPU)..."
for suite in \
    test_gfx803_kfd_topk_offline_cut.py \
    test_gfx803_mbtopk_offline_attribution.py \
    test_gfx803_mbtopk_offload_container.py \
    test_gfx803_t109_k207_integrated.py \
    test_gfx803_amdgpu_msgpack_notes.py; do
  python3 -m unittest discover -s tests -p "$suite" -v
done

mkdir -p "$OUT"
python3 scripts/gfx803_mbtopk_hsaco_metadata.py \
  --hsaco "$HSACO" \
  --container-receipt "$C/fatbin_container.json" \
  --out "$OUT/hsaco_metadata.json"

python3 scripts/gfx803_amdgpu_msgpack_notes.py \
  --hsaco "$HSACO" \
  --container-receipt "$C/fatbin_container.json" \
  --out "$OUT/amdgpu_msgpack_notes.json"

python3 scripts/gfx803_mbtopk_retained_source_audit.py \
  --source "$SOURCE" \
  --attribution-receipt "$RECEIPT" \
  --out "$OUT/mbtopk_retained_source.json"

python3 scripts/gfx803_kfd_safehost_trace_plan.py \
  --out "$OUT/safehost_trace_qualification.json" \
  --trace-source "$OUT/kfd_nonmes_safehost_trace.bt"

KFD_JOIN_ARGS=()
KFD_SOURCE_DQM="$(printenv KFD_SOURCE_DQM || true)"
KFD_SOURCE_GPUVM="$(printenv KFD_SOURCE_GPUVM || true)"
if [[ -n "$KFD_SOURCE_DQM" && -n "$KFD_SOURCE_GPUVM" ]]; then
  if [[ ! -f "$KFD_SOURCE_DQM" || ! -f "$KFD_SOURCE_GPUVM" ]]; then
    echo "Explicit KFD source missing; refusing attribution" >&2
    exit 2
  fi
  python3 scripts/gfx803_kfd_nonmes_source_audit.py \
    --source "$KFD_SOURCE_DQM" --source "$KFD_SOURCE_GPUVM" \
    --handoff docs/receipts/gfx803_kfd_kernel_source_handoff_20261114.json \
    --out "$OUT/kfd_nonmes_source.json"
  KFD_JOIN_ARGS=(--kfd-source "$OUT/kfd_nonmes_source.json")
fi

python3 scripts/gfx803_t109_k207_final_join.py \
  --source-attribution "$RECEIPT" \
  --container-receipt "$C/fatbin_container.json" \
  --elf-inventory "$C/mbtopk_elf_inventory.json" \
  --hsaco-metadata "$OUT/hsaco_metadata.json" \
  --note-metadata "$OUT/amdgpu_msgpack_notes.json" \
  --retained-source "$OUT/mbtopk_retained_source.json" \
  --old-join "$C/kfd_topk_join.json" \
  --safehost-plan "$OUT/safehost_trace_qualification.json" \
  "${KFD_JOIN_ARGS[@]}" \
  --out "$OUT/t109_k207_final_join.json"

python3 - "$OUT" <<'PY'
import json,sys
from pathlib import Path
out=Path(sys.argv[1])
d=json.loads((out/"t109_k207_final_join.json").read_text())
print("offline suite completed:",out)
for key in ("T1.09","T1.10","T1.11","T1.06","T1.07","K2.05","J1","F1","release"):
    x=d["gates"].get(key,{})
    print(f"{key}: {x.get('status','not-recorded')}")
print("No GPU run or live kernel trace was attempted.")
PY
