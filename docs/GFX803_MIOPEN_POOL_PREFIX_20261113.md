# MIOpen pool_sweep: 42 isolated passes, next in-process prefix diagnostic

## What changed in the evidence

The 2026-11-13 RX 580 isolated receipt
`/mnt/truenas/comet-net/experiments/gfx803_pool_isolation_20261113_v3/matrix.json`
records exactly 42 `pass` entries, no fault, timeout or numeric failure,
and no `unassayed` cases. Its high-level status remains
`batch-checkpointed` (a reporting/terminal-state discrepancy, **not**
an incomplete case universe).

Earlier original whole-process `pool_sweep` caused a GPU
page-not-present fault during the 23-entry MIOpen suite. Individual
fresh-process success excludes a consistently faulting isolated
mode/shape under the tested conditions, but does not prove
cumulative-state causality.

## What the new experiment measures

`scripts/gfx803_miopen_pool_prefix_probe.py` takes the original
source-pinned `pool_sweep.cpp` from Schaka
`8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78`. It leaves the
`run_one` function, MIOpen API, CPU reference, allocation lifecycle,
and original case ordering unchanged. Only the top-level source loop
is replaced: a fresh child executes **the first N** cases in one
process for each prefix, with a flushed `POOL_BEGIN`/`POOL_END`
marker around each case. Original summary and numeric exit status
remain required.

The default ladder is
`1,2,4,8,14,16,21,28,35,42`, spanning first mode and
cross-mode boundaries. Each prefix is a **new process** but all N
cases *within* that prefix share runtime/allocator/cache context.

This is diagnostic derivative source, not a proposed upstream MIOpen
patch or modification to the original acceptance suite.

## Build using the already verified Schaka MIOpen receipt

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_gfx803_miopen_pool_prefix_probe.py' -v

OLD=/mnt/truenas/comet-net/experiments/gfx803_schaka_miopen_20261113
SCHAKA=/mnt/truenas/comet-net/upstream-sources/schaka-rocm-gfx803-8fdcf7b-clean
OUT=/mnt/truenas/comet-net/experiments/gfx803_pool_prefix_20261113

python3 scripts/gfx803_miopen_pool_prefix_probe.py \
  --source "$SCHAKA" --build-receipt "$OLD/build.json" \
  --out "$OUT" --build
```

This step compiles a new diagnostic binary using exact original source,
compiler path and ROCm prefix from `build.json`; no GPU test is
performed. It writes a separate `build.json`, binary SHA-256,
derived-source SHA-256 and a planned test matrix.

## GPU execution

Run only on an idle healthy RX 580, with no concurrent C2, OpInfo,
TopK or MIOpen stress tenants. The previous GPU fault must have been
cleared; successful later cases are evidence of recovery for those
cases, not proof that all driver state is healthy.

```bash
python3 scripts/gfx803_miopen_pool_prefix_probe.py \
  --source "$SCHAKA" --build-receipt "$OLD/build.json" \
  --out "$OUT" --resume --execute --batch-size 2 --timeout 180
```

Repeat the same command if each batch passes. Do not restart after a
nonpassing prefix automatically. It stops at the first nonpass and
records the last `POOL_BEGIN` index, all completed indices,
the original exit code and stdout/stderr digests. A failed prefix
is **not** rerun automatically. The original, single-case and
prefix receipts remain separate.

## Interpretation and next cuts

- All prefixes pass: the original fault is intermittent,
  environment-dependent, preexisting GPU-state-dependent, or
  otherwise not reproduced by the controlled derivative. Then
  compare original full binary vs the 42-prefix derivative in a
  new independent run, using kernel logs, loaded-library maps and
  a controlled idle/warm-start crossover.
- A prefix N fails but N' smaller passes: investigate the first
  completed/started case transition and precisely which resources
  are retained between cases. A fresh-prefix binary search can
  narrow the first reproducibly failing length after device recovery.
- A fault at first case, despite earlier individual passes:
  suspect intermittent loader/driver or environmental differences.
  Do not assign kernel causality without a selected-kernel trace.
- OOM: record alloc/cache/free memory by call boundary before
  proposing changes to allocation behavior. Do not recast OOM as
  a kernel page fault.

The next repair must be located in actual MIOpen runtime/kernel
source or HIP/HSA allocation/queue handling with causal evidence.
Do not patch `PoolingForward2d` tile math on the basis of this
single historical fault alone.

Independent gates remain: activation OOM and the intentional
groupnorm negative controls; broad HIP/ROCr/KFD test coverage; TopK
reviewed-binary performance; compositional workload stability.

**No new GPU result or release admission is asserted by this code.**
