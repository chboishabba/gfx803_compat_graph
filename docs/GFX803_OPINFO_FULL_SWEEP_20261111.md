# Execute the complete 1,774-node PyTorch OpInfo corpus (RX 580)

Source pin: PyTorch `d70fd61bab718a3d49b053efa8058efc0566b2b0`.
This uses the existing **collected 1,774 CUDA/HIP generated CPU-comparison
node IDs**, not a hand-picked or randomly sampled subset. All 1,774 cases
remain in the matrix. It does not vendor PyTorch tests or run arbitrary tests
outside the collected source-bound set.

## Required separation and operating conditions

Run only on the local RX 580 host with the selected composed Nix pytest Python,
not on a CI worker. Do not launch while the separate model-quality training
run is active. A pytest process can fault a HIP queue and impair subsequent
processes even if its Unix process terminates. A timeout or GPU fault therefore
halts the sweep rather than automatically beginning the next case. The operator
must inspect kernel/KFD logs and GPU health, recover the GPU as needed, and
explicitly acknowledge recovery when resuming.

This is **operator evidence, not a release gate override**. `gpu_validated`
and `release_admitted` remain false even after 1,774 passes.

## Commands

Use the existing completed collection receipt and **matching selected**
runtime/source. Substitute actual existing host paths for `OUTROOT` and
`SOURCE`, retaining the pinned SHA and wheel.

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
COLLECTION=/mnt/truenas/comet-net/experiments/gfx803_opinfo_collection_20261111_v2/matrix.json
SOURCE=/mnt/truenas/comet-net/upstream-sources/pytorch-d70fd61-sparse
PYTHON=/mnt/truenas/comet-net/.gfx803-schaka-101-work/out/gfx803-101-composed-candidate-pytest-v3/bin/gfx803-schaka101-pytest-python
ROCM=/nix/store/5dbvxcs7l4mvnj1cq3ybbkdm15jpvqr9-staged-rocm
OUTROOT=/mnt/truenas/comet-net/experiments/gfx803_opinfo_full_20261111

# Dry preparation: verify full collection count, source and selected Python.
python3 scripts/gfx803_opinfo_full_sweep.py \
  --collection "$COLLECTION" --source "$SOURCE" \
  --python-wrapper "$PYTHON" --rocm-root "$ROCM" \
  --out "$OUTROOT"

# Execute the first 24 nodes. Same corpus, no selective exclusion.
python3 scripts/gfx803_opinfo_full_sweep.py \
  --collection "$COLLECTION" --source "$SOURCE" \
  --python-wrapper "$PYTHON" --rocm-root "$ROCM" \
  --out "$OUTROOT" --resume --execute --batch-size 24 --timeout 180

# Repeat the same command on additional batches until unassayed==0.
```

Each invocation runs at most `--batch-size` previously-unassayed nodes.
The runner takes a nonblocking output-directory lock to prevent concurrent
runs into the same receipt. For each child, it writes complete stdout/stderr
files with SHA-256, stores its exact node ID/return code/time, and atomically
updates `matrix.json`. A process interrupted mid-test remains visibly
`interrupted`, not silently unassayed/passed.

After **actual** GPU health inspection/recovery, if there was a prior
fault/timeout/interruption, use `--recover-after-fault` with `--resume`.
Previously faulting nodes retain their original status; remaining unassayed
nodes continue in their originally collected order. Do not substitute a
success receipt for the failed node.

## Semantics and limits

Outcomes are `pass`, `fail`, `unsupported`, `fault`, `timeout`,
`interrupted`, `unassayed`. Wholly skipped, xfailed or xpassed tests
are **not passes**. Ordinary failures are retained and the sweep continues,
to maximize diagnostic evidence; faults/timeouts stop the GPU runner.
This test family is selected upstream `test_compare_cpu` and
`test_variant_consistency_eager`, not every PyTorch test family,
dtype, stride, PyTorch mode, or every HIP/ROCm backend. Therefore
1,774/1,774 (even if achieved) would not imply universal GPU safety.

After the full sweep, join the original results with the existing
device-indexed capability atlas; retain the matrix, child output files,
source SHA, wheel SHA, kernel logs and any GPU recovery reports. In parallel,
run Schaka's independent direct MIOpen/rocBLAS/rocSOLVER/Triton/coherence
suites, then matching TheRock HIP/ROCr/KFD tests, and later clean-client
Cachix restore and longer stability tests.
