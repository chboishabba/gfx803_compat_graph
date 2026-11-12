# gfx803 complex64 inverse-unary GPU faults — source-bound replay

Observed discovery source: `docs/receipts/gfx803_opinfo_discovery_20261112.json`
on `master`, matrix SHA256
`47c7ed58d7b549abfc038b534faaaa9ecaf6ee2fc18b3ba55addebeed02b7e36`.

## Evidence

The four recorded GPU fault candidates are upstream `TestCommonCUDA`
`test_variant_consistency_eager` on `acos`, `acosh`, `asin`,
`asinh` at complex64. All were associated with an amdgpu
`VM_CONTEXT1_PROTECTION_FAULT_STATUS=0x1004800C`, address zero,
read from `TC4`. That signature is evidence of a device VM fault, NOT
identification of the instruction or kernel responsible.

The exact pinned PyTorch source `d70fd61bab718a3d49b053efa8058efc0566b2b0`
uses matching `AT_DISPATCH_COMPLEX_TYPES_AND(kComplexHalf, ...)` then
`gpu_kernel(iter, [] GPU_LAMBDA(scalar_t a) ...)` with
`at::opmath_type<scalar_t>` and `::acos`, `::acosh`,
`::asin`, `::asinh` respectively. Each is a distinct CUDA/HIP
translation unit. The common dispatch/lambda/complex-math pattern is a
**hypothesis**, not proof that one implementation fault causes all four.

The original test family is *variant-consistency*, so an ordinary
`torch.acos(z.cuda())` forward may succeed while the upstream
variant/out/in-place/gradient or sample-shape path faults. Never
infer original OpInfo correctness from a forward-only probe.

## Highest-information experiment order

1. Confirm GPU health and no concurrent tenant. If recovering from a prior
   fault, inspect KFD/amdgpu logs, reset/reboot if necessary. NEVER run
   automatic replays while the host is in a faulted state.
2. Replay exactly **one** original upstream faulting node with existing
   pinned `test/test_ops.py` using the composed Nix pytest interpreter.
   Retain exact stdout/stderr, GPU kernel logs and source/host identity.
   An exit signal or timeout remains a fault; do not run further tests
   on a possibly wedged GPU.
3. Only on a recovered/healthy host, run a *single* simplest forward-only
   control via `scripts/gfx803_complex_unary_fault_probe.py`. Run
   separately for each shape/dtype and operation; do not batch the known
   faulting operations into one GPU process.
4. Compare complex64 contiguous vs strided vs empty, complex128,
   float32 and neighboring `atan`, `atanh`, `sin`, `cos`,
   `log`, `sqrt`. A pass in one dtype does not imply a pass in
   another. Record failures exactly.
5. If forward-only is clean but upstream OpInfo fails, use the original
   test's generated inputs and variants to bisect in-place/out,
   autograd and noncontiguous inputs. If forward-only faults, capture
   the actual dispatched kernel name with a HIP debugger/tracer on a
   recovered host, then inspect the shared complex-math lowering.
6. Only then select the smallest correction: upstream compiler/codegen,
   PyTorch dispatch, or fallback. Do not push untested kernel patches.

## One-shot probe example

Provide actual existing paths for `PYTHON` (the composed pytest Python),
`ROCM` (selected immutable runtime), and a fresh `OUT` directory.
One invocation runs **one operation/profile only**.

```bash
PYTHON=/mnt/truenas/comet-net/.gfx803-schaka-101-work/out/gfx803-101-composed-candidate-pytest-v3/bin/gfx803-schaka101-pytest-python
ROCM=/nix/store/5dbvxcs7l4mvnj1cq3ybbkdm15jpvqr9-staged-rocm

python3 scripts/gfx803_complex_unary_fault_probe.py \
  --python-wrapper "$PYTHON" --rocm-root "$ROCM" \
  --op acos --profile complex64-contiguous \
  --out out/complex-acos-c64-forward-review

# Above only records a non-execution receipt. After checking host state,
# rerun with a fresh destination and explicit --execute:
python3 scripts/gfx803_complex_unary_fault_probe.py \
  --python-wrapper "$PYTHON" --rocm-root "$ROCM" \
  --op acos --profile complex64-contiguous \
  --out out/complex-acos-c64-forward-run1 --execute
```

The probe records the selected device/runtime mappings and numerical
CPU/GPU parity, if the GPU path returns. It is diagnostic only and
cannot prove correctness for upstream variants, backward, sustained
compute or a complete ROCm release.

## Independent ordinary failures

Do not merge these failures into the complex unary fault family:
`test_compare_cpu_sparse_sampled_addmm_cuda_float32`,
`test_compare_cpu_topk_cuda_float32`, and
`test_variant_consistency_eager_topk_cuda_float32`.
In particular, the native TopK 120-case semantic sweep passed, but
the two original OpInfo tests failed on another test envelope. Inspect
their original sample input/dtype/shape, error message, exact build,
and expected variant behaviour before changing the already validated
sort-backed TopK patch.

## Attribution and acceptance

The test sources and complex unary kernels belong to upstream PyTorch;
Schaka owns his original gfx803 ROCm work; the local Nix/runtime
composition, fault isolation and device-specific receipts are distinct.
The reviewed summary can be committed; do not fabricate or replace the
original raw host logs. Preserve `release_admitted=false` and
unreplayed faults as open.
