# gfx803 ROCm 10.1 PyTorch operator conformance matrix

**9 November 2026. Candidate assay source only. No new on-card outcomes in this document.**

## Why this exists

Schaka's upstream ROCm 10.1 gfx803 release reports 202/202 Torch operation
checks, plus broader GPU tests on its validation hardware. This is valuable
**prior evidence**, not a complete guarantee for the local RX 580, specific
PyTorch binary, input/gradient shape, backward mode or sustained workload.
Upstream also explicitly documents compiling `TensorTopK.hip` at `-O0`
because higher optimization levels do not complete compilation on gfx803.
That workaround does **not** establish runtime correctness of the exact
`warptopk::warpMergeSortTopK<2,...>` kernel used by original C2.

The local original `torch.topk` with genuine [2,4], k=2 router scores
caused a GPU VM page fault. A model-local GPU sort selector avoided that
specific kernel and completed 20/20 matched AdamW steps, checking all
36 focused trainable gradient tensors and GPU repeats. The gfx803-only
PyTorch dispatch patch at factory PR #5 commit `5080c1c` cleanly applies
to the exact source revision, but a patched wheel has **not** been built or
physically accepted. Keep this distinction in every promotion decision.

## Run, bounded and fail-closed

Use the **same imported Schaka 10.1 Nix Python** from the real 10.1
candidate with the independently relocated ROCm root. Do not run the
host 6.4 Python or allow host /opt/rocm libraries to be mapped.

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
PY101=/nix/store/ACTUAL-101-VENV/bin/python
ROCM101=/nix/store/5dbvxcs7l4mvnj1cq3ybbkdm15jpvqr9-staged-rocm

# Safe first pass: the already-faulting topk case stays UNASSAYED.
env -u LD_PRELOAD "$PY101" scripts/gfx803_torch_conformance.py \
  --rocm-root "$ROCM101" \
  --timeout 60 \
  --out out/gfx803-101-conformance-first

# Deliberate topk experiment ONLY after updating to a patched PyTorch wheel,
# on a controlled machine with kernel/GPU fault logging. Use a fresh output.
# It can fault or wedge the device; never run this as routine CI.
env -u LD_PRELOAD "$PY101" scripts/gfx803_torch_conformance.py \
  --rocm-root "$ROCM101" \
  --timeout 60 --include-known-faults \
  --out out/gfx803-101-conformance-patched-topk
```

The runner refuses an existing output directory and uses **a separate
subprocess for every case**, with a per-case timeout, captured stderr,
real HIP architecture, PyTorch/HIP version and mapped-library checks.
After each child, `matrix.json` is atomically updated. A fatal signal
or timeout stops the remaining assay by default, leaving later cases
**unassayed**; do not use `--continue-after-fault` in an ordinary run
because a GPU reset may poison subsequent tests or destabilize the host.

Each case compares original CPU inputs to HIP on forward scalars, input
gradients and two GPU executions; index-valued selectors additionally
compare indices on deliberately **tie-free** inputs. This does not establish
`torch.topk` ordering compatibility on tied values or NaNs.
The selected registry covers:
tensor copy/views, layernorm, softmax, FP32 GEMM, batched matmul,
sort, topk [2,4]/k=2, gather, scatter-add, embedding, small conv2d,
and AdamW. **An unchecked operator, dtype, tensor layout or shape is
unassayed, not passed.**

## Coverage and upstream ownership

- Upstream Schaka: GPU/ROCm patches, the published image, WGM and FP32 SGEMM
  findings, wave64 and the TopK compilation workaround:
  https://github.com/Schaka/rocm-gfx803
- PyTorch ATen/HIP: original TopK implementation and eventual architecture
  dispatch fix; local patch is a candidate and should be offered upstream.
- Local gfx803 factory: Nix import, source/ABI attestation, operator receipts
  and release acceptance, **not independent attribution for Schaka patches**.
- LILA: original model tensors, router score trace and training gate receipts.

This matrix is not a complete enumeration of all PyTorch ops, all floating
point dtypes, numerical boundaries, gradients through every parameter,
Triton, attention engines, or long-term reset stability. Expand coverage
from **recorded production ATen operator traces**, and record each new
operator/shape/dtype signature, source commit and binary hash. A changing
binary **invalidates** inherited local pass claims; Schaka's upstream
202/202 remains separately attributed evidence.

## Promotion rule

The script's verdict always sets `training_admitted=false` and
`cachix_release_admitted=false`, even if all registered cases pass.
Actual TopK acceptance requires the patched PyTorch wheel, original
faulting [2,4], k=2 router trace, tie and NaN policies, CPU/GPU
index/forward parity, backward and repeated GPU results, hardware/KFD
fault checks, plus the authentic unswapped C2 20-step trajectory.
Full workload/host-stability and clean-client Cachix gates stay separate.

CPU-only source and receipt contracts:

```bash
python3 -m unittest discover -s tests -p 'test_gfx803_torch_conformance.py' -v
```
