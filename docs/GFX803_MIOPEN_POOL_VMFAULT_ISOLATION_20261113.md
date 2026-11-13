# RX 580 / ROCm 10.1 — isolate MIOpen pool_sweep GPU page fault

Original Schaka source: `8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78`.
Original whole MIOpen receipt: `/mnt/truenas/comet-net/experiments/gfx803_schaka_miopen_20261113/matrix.json`.
The original whole suite remains **immutable**: 23 target entries,
18 passed, 2 solver shape-lists without applicable cases, 1 pooling
device fault, 1 activation OOM before summary, and 1 groupnorm suite
recorded as fail despite Schaka source expecting two boundary rejections.

## P0: recover original compilation inputs

Read the exact original build receipt, do not guess `hipcc`/prefix:

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
git pull --ff-only
export OLD=/mnt/truenas/comet-net/experiments/gfx803_schaka_miopen_20261113
export SCHAKA=$(python3 -c 'import json,os; print(json.load(open(os.environ["OLD"]+"/build.json"))["source"])')
export PREFIX=$(python3 -c 'import json,os; print(json.load(open(os.environ["OLD"]+"/build.json"))["rocm_prefix"])')
export HIPCC=$(python3 -c 'import json,os; print(json.load(open(os.environ["OLD"]+"/build.json"))["hipcc"])')
printf 'SCHAKA=%s\nPREFIX=%s\nHIPCC=%s\n' "$SCHAKA" "$PREFIX" "$HIPCC"
```

The diagnostic consumes source from the **original pinned Schaka
checkout**, not our modified PR or the newer TopK source.

## P1: build source-preserving diagnostic derivative (CPU compilation)

```bash
export OUT=/mnt/truenas/comet-net/experiments/gfx803_pool_isolation_20261113
python3 -m unittest discover -s tests -p 'test_gfx803_miopen_pool_case_isolation.py' -v
python3 scripts/gfx803_miopen_pool_case_isolation.py \
  --source "$SCHAKA" --rocm-prefix "$PREFIX" --hipcc "$HIPCC" \
  --out "$OUT" --build --build-timeout 900
```

The source transformation requires one exact original
`for (auto mode : modes) for (auto& c : cases)` block and exactly
14 shape records. It retains `run_one`, the CPU reference and
original MIOpen API calls byte-for-byte. It only inserts an
environment-selected case index and a flushed pre-call marker.
The resulting binary is **diagnostic, not an upstream patch**.

## P2: physically isolate 42 original cases, one process each

Perform only on the recovered, idle RX 580. The previous pool
VM page-not-present fault must be cleared at device/driver level
before initiating a new probe; merely starting a new process does
not itself prove that recovery occurred.

```bash
python3 scripts/gfx803_miopen_pool_case_isolation.py \
  --source "$SCHAKA" --rocm-prefix "$PREFIX" --hipcc "$HIPCC" \
  --out "$OUT" --resume --execute --batch-size 42 --timeout 90 --auto-recover
```

Each case is an independent child process. On a fault or timeout, the runner
saves its original case index, then replaces its coordinator with a fresh
Python process using a minimal environment and continues every remaining
unassayed case. The faulting case is never retried. Its original case index,
mode, C/H/W, pooling kernel dimensions, stride and pad in
`$OUT/matrix.json`; individual stdout/stderr logs are SHA-256-bound.

Index ordering is:

- 0–13: Max pooling, original 14 shapes
- 14–27: Average pooling, same 14 shapes
- 28–41: AverageInclusive pooling, same 14 shapes

The 8/9, 16/17, 32/33, 64/65 and 128 output-width
thresholds, asymmetric 32×100 shapes and global-pooling shape
are all retained.

**Never auto-retry a faulting case.** Automatic continuation isolates discovery
from the failed child; it is not evidence that the GPU driver recovered. If a fault appears, inspect
kernel logs and GPU state, then bisect the selected shape on a
separate controlled branch of the diagnostic (not by changing the
original acceptance receipt). A single fresh process is not enough
to demonstrate GPU/KFD reset.

## P3: actual repair (still OPEN)

After recovering the exact first faulting mode+shape:

1. Capture the before-dispatch marker, kernel fault address, queue
   identity, MIOpen selected kernel/solver and any generated code
   identity.
2. Read MIOpen `PoolingForward2d` dispatch and work-group tile
   arithmetic at that shape. Check out-of-range reads/writes and
   workspace bounds before choosing a fix.
3. Patch the **shared upstream MIOpen implementation**, not a
   PyTorch special case, only after causal source evidence.
4. Build the patched component in a new immutable Nix candidate;
   rerun the exact faulting shape, all 42 original pooling cases,
   full 23-entry MIOpen suite and composed workload controls.
5. Keep groupnorm's two expected rejections and activation OOM
   as independent audit gates. Do not infer their cause from pool.

No patch, extra pass or release acceptance is claimed here.
