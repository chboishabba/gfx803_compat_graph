# gfx803 reuse-first qualification: upstream test ownership and evidence

North star: recover auditable **functional** compute across legacy AMD devices;
never promote an entire chip generation because one RX 580 and selected shapes pass.
Test definitions belong to PyTorch, Schaka and ROCm upstream. This factory stores
pins, execution receipts, composition and capability claims by exact device,
software revision, tensor signature, and host environment.

## Existing assets: run upstream, do not rewrite

- **PyTorch OpInfo:** at pinned `d70fd61bab718a3d49b053efa8058efc0566b2b0`, `test/test_ops.py`, `torch/testing/_internal/common_methods_invocations.py` and `common_device_type.py`. Start with `test_compare_cpu` and `test_variant_consistency_eager` generated **CUDA** tests (HIP uses the CUDA device type in torch). Existing OpInfo tolerances, dtype filters, reference definitions and expected skips remain upstream. Use `scripts/gfx803_upstream_assay.py` to collect and execute actual generated pytest nodes on the exact source, one subprocess per case; retain output and process status. `pytest` and original PyTorch test dependencies must be available in the selected candidate Python; absence is an environment failure, not an unsupported GPU operation.
- **Schaka image validation:** `tools/imgvalidate.sh`, `verify.py`, `tools/correctness-suite/torch_op_suite.py`, `fp16_gemm_sweep.py`, `triton_dot_probe.py` and `tools/tc-staleness/` already exercise coherence, GPU-only execution, GEMM, convolution, Triton and kernel logs with negative controls. `imgvalidate.sh` is written for Podman and `/opt/rocm` in an OCI image; do not claim it has been ported to a native Nix closure just by finding it. Run its constituent scripts with properly translated runtime paths where supported, preserving their original source pins and log interpretation.
- **Schaka direct MIOpen tests:** `tools/correctness-suite/build.sh` and `run_all.sh` target solver `IsApplicable` boundaries, not merely common tensor shapes. Reuse these first for MIOpen before inventing any new sweeps. The original suite has documented exclusions (e.g., complex MHA Find2.0, specific training-only operations); classify those as **unassayed**.
- **TheRock/ROCm:** use TheRock's pinned packaging/build graph and its upstream component tests for HIP/ROCr, rocBLAS/rocSOLVER, and compiler functionality. This is a *future separate adapter* until its specific revision and test entrypoints are pinned and verified; do not invent a runner command or silently substitute ROCm 10.1 for another line. Cross-device comparisons should use **separate, immutable device profiles**.

Run offline source-inventory (no device):

```bash
python3 scripts/gfx803_upstream_inventory.py \
  --schaka-source /path/to/Schaka-rocm-gfx803-at-8fdcf7b \
  --pytorch-source /path/to/pytorch-at-d70fd61 \
  --out out/gfx803-upstream-inventory.json
```

Collect real OpInfo CUDA test identities **without executing them**:

```bash
COMPOSED=/nix/store/ACTUAL-COMPOSED-CANDIDATE
ROCM=/nix/store/5dbvxcs7l4mvnj1cq3ybbkdm15jpvqr9-staged-rocm
python3 scripts/gfx803_upstream_assay.py \
  --source /path/to/pytorch-at-d70fd61 \
  --python-wrapper "$COMPOSED/bin/gfx803-schaka101-python" \
  --rocm-root "$ROCM" \
  --out out/gfx803-opinfo-collected-20261111
```

Only after reviewing collected test IDs and ensuring an idle GPU, execute a
bounded subset under the same wrapper (fresh out required):

```bash
python3 scripts/gfx803_upstream_assay.py \
  --source /path/to/pytorch-at-d70fd61 \
  --python-wrapper "$COMPOSED/bin/gfx803-schaka101-python" \
  --rocm-root "$ROCM" \
  --out out/gfx803-opinfo-execute-20261111 \
  --execute --max-cases 20 --timeout 180
```

This runner deliberately stops after a fatal child signal or timeout; that may
still leave a wedged KFD queue requiring operator attention. It never treats a
collected (but unexecuted) case as passed. Some PyTorch tests use randomized
inputs or generate multiple samples; record original PyTorch test failures
instead of translating them into novel local test logic.

## Capability ledger / maximum-cut policy

1. Preserve the prior physical evidence: relocated ROCm 10.1 dense parity, C2
   native TopK 20-step gate, composed ABI and 120/120 TopK cases.
2. Establish actual OpInfo collection and initial CPU/GPU comparison on the
   already SHA-pinned composed closure, then run upstream Schaka component
   sweeps without mutating the original downloaded sources.
3. Classify outcomes by device architecture **and exact board/firmware/host**,
   binary SHA, shape, dtype, strides, mode, and execution context.
4. For each failure, bisect against upstream or known patches; contribute a
   minimal original upstream reproducer, preserving author attribution.
5. Add original direct ROCm backend suites and device-matrix coverage as
   distinct gates; then long-run stability and clean-client Cachix restore.
6. Only promote tested capability slices. "gfx803 full compatibility" and
   "all legacy Radeon compute" remain **unproven**, even with green matrices.

No new GPU or Cachix acceptance result is asserted by this source change.

## Device-indexed capability atlas

The test runner collects generated CUDA OpInfo nodes; these nodes give a
self-enumerating baseline. Record results in a **separate profile per actual
card and driver/firmware/kernel combination**. The ledger normalizes
receipts; it never invents results for untested cases or platforms.

Create a reviewed, explicit JSON profile describing the measured host (fill
real values; do not copy RX 580 metadata to another card):

```json
{
  "architecture": "gfx803",
  "board": "AMD Radeon RX 580 Series",
  "kernel": "ACTUAL-RUNNING-KERNEL",
  "driver": "ACTUAL-DRIVER-BUILD",
  "rocm_store": "/nix/store/ACTUAL-ROCM-CLOSURE",
  "torch_wheel_sha256": "0968548982ba69858d2dfe4ec0090ef1ce41ed610f0f9b3b9f38aebe0f0319eb",
  "source_revision": "8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78"
}
```

Then use the **existing** original matrix receipts, never a hand-authored
"passed" summary:

```bash
python3 scripts/gfx803_capability_atlas.py \
  --profile out/gfx803-reviewed-host-profile.json \
  --receipt topk=out/gfx803-101-topk-semantics-20261111/matrix.json \
  --receipt opinfo=out/gfx803-opinfo-execute-20261111/matrix.json \
  --out out/gfx803-capability-atlas-20261111.json
```

Do not include the optional `opinfo` argument until that matrix actually
exists. The output remains evidence-only and explicitly denies global compute
compatibility or release admission.


## TheRock reuse seam (confirmed upstream, not yet a local gfx803 test run)

TheRock is the modular HIP/ROCm build-and-test superproject, not a
drop-in proof of gfx803 support. Its documented `ctest --test-dir build`
runs the configured component tests when `BUILD_TESTING` is enabled.
`build_tools/install_rocm_from_artifacts.py` explicitly supports retrieving
test artifacts by categories including `hip_tests`, `rocrtst`, `kfdtest`,
`blas`, `solver` and `miopen`. These are the **upstream entrypoints**
for expanding below PyTorch, especially streams, memory, events, queues,
and driver-facing KFD behaviour. Pin a TheRock source and exact matching
runtime line before running them. Do not copy tests into this repository
or claim a current 10.1 Schaka runtime automatically matches TheRock main.

TheRock source: https://github.com/ROCm/TheRock
