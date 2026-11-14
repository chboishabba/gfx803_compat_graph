# T1.05–T1.07 / K2.06 — original TopK binary attribution runbook

14 November 2026. This is source-written code pending execution on the RX 580 host. Nothing here initializes HIP, runs a GPU kernel, or changes KFD state.

The retained pre-review source maps both 1×151936 and 32×151936 float32, k=50, to mbtopk. The original source SHA-256 is acb592c2c25db61b5048a224d64a7a022fbcda91c5cfaa156e4cfdfa1b58059d. The candidate binary SHA-256 is dd0b4030c4034fdab10daa48dd260397f4de2348ad1cec7ef95474ebd05fa0d2, Build ID 392fee76f7a23e82b345dae1b40d02bd0ea32cd5. Inclusion of mbtopk symbols in this binary does NOT establish incident-time dispatch or original source-to-build linkage.

## Complete CPU-only run

~~~bash
set -euo pipefail
cd /mnt/truenas/comet-net/gfx803_compat_graph
git pull --ff-only

python3 -m unittest discover -s tests -p 'test_gfx803_mbtopk_offline_attribution.py' -v
python3 -m unittest discover -s tests -p 'test_gfx803_kfd_topk_offline_cut.py' -v

OUT=/mnt/truenas/comet-net/experiments/gfx803_t105_k206_20261114
mkdir -p "$OUT"
BASE=/mnt/truenas/comet-net/.gfx803-schaka-101-work/out/pytorch-topk-gfx803-20261109
ELF="$BASE/python-overlay-r2/torch/lib/libtorch_hip.so"
SRC="$BASE/hip-audit-r3/TensorTopK.hip"
RECEIPT=docs/receipts/gfx803_k205_t104_source_binary_attribution_20261114.json

python3 scripts/gfx803_mbtopk_elf_attribution.py \
  --libtorch-hip "$ELF" --source "$SRC" \
  --attribution-receipt "$RECEIPT" \
  --dump-fatbin "$OUT/libtorch_hip_fatbin.bin" \
  --out "$OUT/mbtopk_elf_inventory.json"

python3 scripts/gfx803_mbtopk_fatbin_scan.py \
  --fatbin "$OUT/libtorch_hip_fatbin.bin" \
  --extract-dir "$OUT/amdgpu_candidates" \
  --out "$OUT/embedded_elf_candidates.json"

OLD=/mnt/truenas/comet-net/experiments/gfx803_k205_t1_static_20261114
HANDOFF=docs/receipts/gfx803_kfd_kernel_source_handoff_20261114.json

python3 scripts/gfx803_kfd_topk_evidence_join.py \
  --incident "$OLD/incident_static.json" \
  --trace "$OLD/kprobe_inventory.json" \
  --topk "$OLD/topk_static.json" \
  --handoff "$HANDOFF" \
  --source-attribution "$RECEIPT" \
  --topk-elf "$OUT/mbtopk_elf_inventory.json" \
  --out "$OUT/kfd_topk_join.json"
~~~

Each output refuses overwrite; use a new directory if rerunning. The first auditor verifies the exact original library SHA and ELF Build ID against the committed attribution receipt before extracting anything. GNU readelf is required; objcopy is needed for fatbin extraction. The ELF scanner requires only Python and checks ELF64 little-endian machine 224, section and program header extents. The symbol display is capped, but the receipt records the full matching-line count separately; generic `.rodata` is not treated as an offload section.

If extracted candidates exist, inspect them with read-only tools:

~~~bash
for file in "$OUT"/amdgpu_candidates/*.elf; do
  [ -f "$file" ] || continue
  readelf -h "$file" || true
  readelf -n "$file" || true
  readelf -Ws "$file" | grep -Ei 'mbtopk|gather|topk' | head -80 || true
done
~~~

AMDGPU machine 224 alone does not identify gfx803. Check target IDs, notes, amdhsa.kernels metadata, VGPR/SGPR, LDS and kernel symbols with installed LLVM tools. A fatbin may use compressed wrappers rather than directly embedded ELF; zero candidates is inconclusive. Extracted candidate ELF extent can exclude trailing vendor wrapper metadata. Do not execute those candidates.

## Exact gates and acceptance

| Gate | Evidence required | Status |
| --- | --- | --- |
| K2.06 | GFX8 non-MES queue-unmap/fence-timeout path in v7.3 reference | Source-mapped |
| K2.05 | Incident-time selected return and queue fence state | OPEN |
| T1.04 | Retained pre-review TensorTopK source selects mbtopk | Source-mapped |
| T1.05 | SHA/Build-ID verified exact HIP ELF, symbols/fatbin inventory | Code ready; host run pending |
| T1.06 | Original source↔binary build manifest, compiler/flags and actual benchmark-loaded ELF path | OPEN |
| T1.07 | Actual incident selected HSACO, launch grid, VGPR/SGPR/LDS and first stalled dispatch | OPEN |
| J1/F1 | Causal trigger/recovery join and patch | BLOCKED |
| Release | Sustained stable GPU plus KFD/Wayland recovery | BLOCKED |

The retained 1-row pass and 32-row hang share source-level mbtopk, but the 32-row shape has 32× the input elements (151,936 vs 4,861,952). Minimum f32 input bytes are 607,744 versus 19,447,808. Minimum full-sort index bytes would be 1,215,488 versus 38,895,616; those are NOT actual mbtopk workspace allocations. No specific race, deadlock, LDS/register exhaustion or VM error is proven by this arithmetic.

Historical binary link demands original build log/manifest including source hash, patch revision, compiler flags, final ELF SHA/Build ID AND process loader maps or equivalent. A new rebuild cannot replace missing incident-time evidence. The v7.3 reference maps Polaris non-MES unmap_queues_cpsch to amdkfd_fence_wait_timeout, but the exact CachyOS source package, actual incident errno and fence state remain unproven.

No destructive TopK run on the sole display GPU; a future fault reproducer requires an independently recoverable non-display host. Keep all local scripts and AI-work documentation out of Schaka PR #8 per maintainer instructions.
