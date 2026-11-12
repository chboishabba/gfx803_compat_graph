# Recover reasons for original 183 PyTorch OpInfo skips (12 Nov 2026)

Audit: `/mnt/truenas/comet-net/experiments/gfx803_opinfo_unsupported_audit_20261112.json`
Original discovery matrix SHA-256:
`47c7ed58d7b549abfc038b534faaaa9ecaf6ee2fc18b3ba55addebeed02b7e36`.

Exactly 183 pytest results were mapped to `unsupported`. The original
discovery omitted skip/xfail reasons. These are **183 non-passes**, not
183 proven missing GPU operators. Breakdown: 95 CPU-comparison and
88 variant-consistency; 147 float32, 30 complex64, 4 int64 and
2 float8 e4m3fn scaled-matmul cases.

**Do not use `gfx803_opinfo_full_sweep.py --resume` to acquire the skip
reasons.** The scheduler only chooses `unassayed`, and none remain.
Do not overwrite the original matrix or artificially mark cases unassayed.

## Safe phase A — upstream marker collection, without executing tests

This collects the original 183 generated node IDs and their pytest
`skip`, `skipif` and `xfail` marker expressions/reasons; it does not
execute test setup or test bodies. A static `skipif` condition is **not**
automatically equivalent to a condition evaluated true on gfx803.
Some runtime skip reasons remain unknown after this phase.

The static child explicitly hides CUDA, HIP and ROCR devices before pytest
imports PyTorch. It is a source-marker collection step, not a GPU assay.

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
AUDIT=/mnt/truenas/comet-net/experiments/gfx803_opinfo_unsupported_audit_20261112.json
SOURCE=/mnt/truenas/comet-net/upstream-sources/pytorch-d70fd61-sparse
PYTHON=/nix/store/vq1lgpc49im7qvvxgxabykyfs47l2ykb-gfx803-schaka101-torch-candidate-overlay/bin/gfx803-schaka101-pytest-python
OUT=/mnt/truenas/comet-net/experiments/gfx803_opinfo_skip_markers_20261112

python3 scripts/gfx803_opinfo_skip_reason_probe.py \
  --audit "$AUDIT" --source "$SOURCE" \
  --python-wrapper "$PYTHON" --out "$OUT" --mode static --timeout 180
```

The runner requires the exact original matrix identity, 183 unique
test IDs, pristine pinned PyTorch source, immutable Nix Python wrapper,
and a **fresh** output directory. Child output and receipts are
preserved; release admission remains false.

## Optional phase B — runtime setup skip reasons, GPU caution

For cases whose marks do not explain the skip, the probe can run each
original pytest node's **setup** in a separate subprocess and block
the `call` phase with a guard skip. If PyTorch would otherwise run
the operator test, the receipt says `probe-blocked-call`, never pass.
If upstream skips during setup, it retains `upstream-skipped` and
the actual `longrepr` reason.

**Warning:** setup/fixtures can initialize HIP and may use the GPU;
this is *not* a GPU-free phase. Perform only on a healthy, idle
RX 580 after checking there are no concurrent GPU tenants.
Start small and inspect receipts. A crash/timeout halts the batch.

```bash
python3 scripts/gfx803_opinfo_skip_reason_probe.py \
  --audit "$AUDIT" --source "$SOURCE" \
  --python-wrapper "$PYTHON" \
  --out /mnt/truenas/comet-net/experiments/gfx803_opinfo_skip_setup_00 \
  --mode setup --start 0 --limit 8 --timeout 120 --execute-setup
```

Continue in **new** destination directories with explicit
`--start` and `--limit` ranges after reviewing the first batch.
Do not run Phase B while C2/dense training or TopK benchmarking
occupies the card. It does not automatically reset the GPU.

## Attribution / classification after evidence

Retain: `policy-skip`, `xfail`, `dtype-or-shape-exclusion`,
`optional-dependency`, `setup-environment`, `probe-blocked-call`,
and `unresolved` as distinct outcomes. A source marker may only
support a **candidate** classification until the exact condition
is evaluated. An upstream skip is not a kernel failure, and a test
body blocked by this probe is not a successful GPU execution.

Do not change original statuses or promote the closure. Only after
the reasons are recovered should we prioritize **shared** missing
gfx803 implementations or obsolete upstream exclusions. Existing
four complex64 VM fault candidates and three normal failures remain
independent.
