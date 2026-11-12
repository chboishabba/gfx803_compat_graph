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

CUDA OpInfo nodes are generated conditionally, so static collection retains
the qualified runtime's visible device. It invokes `--collect-only` and never
runs setup or a test body, but it can import PyTorch's ROCm test configuration.
The receipt rejects a collection unless every one of the requested historical
node IDs was generated; zero-node or partial collection is diagnostic failure,
never a recovered reason.

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


## Discovery after static v4 receipt: call-time skip remains possible

Static v4: all 183 nodes collected, zero attached `skip`/`skipif`/
`xfail` markers, zero test bodies executed. This only rules out **attached
static markers collected by the probe**; it does NOT prove all 183 are
setup-time skips, or all are dynamic GPU exclusions.

Pinned upstream `test/test_ops.py` shows:
- `test_compare_cpu` calls `op.reference_inputs(device, dtype)`
  **inside the original test body**.
- `test_variant_consistency_eager` calls `op.sample_inputs(...)`
  **inside the original test body**.

Therefore an operator-specific `unittest.SkipTest` or `pytest.skip`
raised during the sample-generation or call path cannot be recovered
by the setup-only probe. A reported `probe-blocked-call` means only
that the guarded setup reached the call phase. **Do not classify it as
upstream-support, a missing kernel, a pass, or an identified skip policy.**

The setup probe now replaces each collected item's original `runtest`
callable with the deliberate `GFX803_SKIP_REASON_PROBE_BLOCKED_TEST_BODY`
skip, rather than relying solely on hook execution order. Setup
fixtures can still initialize HIP or dispatch work.

**Decision cut after guarded setup:** identify cases actually skipped
during setup, then group remaining `probe-blocked-call` cases by
upstream OpInfo sample-generator and decorator implementation. Their
skip reasons may require real, individual, opt-in test-body replay
(`pytest -q -rs <exact-node-id>`) on a healthy GPU with failure
containment, preserving a separate result receipt and original discovery.
Never remove original upstream guards to force a test into execution.
