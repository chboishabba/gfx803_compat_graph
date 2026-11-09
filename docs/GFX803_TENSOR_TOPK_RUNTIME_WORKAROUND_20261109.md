# gfx803 TensorTopK runtime-workaround candidate

## Evidence boundary

The relocated Schaka ROCm 10.1 candidate passes the frozen QKV and original
LILA dense-model parity gates.  The C2 checkpoint faults only when its router
calls ordinary GPU `torch.topk` on its authentic two-row, four-expert score
matrix with `k=2`.  The preserved GDB trace terminates in PyTorch's
`warptopk::warpMergeSortTopK<2,2,64,1,float,unsigned int,true,64>` kernel.

The model's explicit diagnostic `torch.sort(..., descending=True)` selector
matches the observed router choices, passes CPU/GPU forward and backward
parity, and completes the bounded 20-step C2 gate.  That proves neither the
general semantics of a replacement nor a PyTorch runtime repair; it makes the
selection-kernel dispatch the current minimal fault boundary.

Schaka's pinned `8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78` build scripts
already compile `TensorTopK.hip` with `TENSOR_TOPK_OPT_LEVEL=-O0` because the
gfx803 compiler path otherwise fails to complete.  This build-time workaround
is separate evidence from the runtime fault.

## Candidate patch

The first candidate, `patches/pytorch/gfx803-disable-warptopk.patch`, checks
the runtime `gcnArchName` and makes only `gfx803` decline the ROCm warp-merge
TopK route. Hardware evidence showed that its `sbtopk` fallback also faults
for the authentic router operand. It is retained as a mechanism record, not
as a successful repair.

The replacement candidate,
`patches/pytorch/gfx803-topk-sort-fallback.patch`, makes only non-Boolean
`gfx803` tensors take PyTorch's existing GPU sort-backed TopK path before the
normal size heuristic. This is the same implementation family as the working
model-level `torch.sort` control, but still requires on-card API semantic and
C2 validation.

The guard deliberately checks the architecture token boundary because HIP may
report a suffix such as `gfx803:xnack-`.

Before a source build, validate the patch against a checkout at the exact
PyTorch revision:

```bash
scripts/verify-schaka-pytorch-topk-patch.sh --source /path/to/ROCm-pytorch
```

The verifier only runs `git apply --check`; it does not touch that checkout.

## Build and acceptance sequence

1. Start from the exact `d70fd61bab718a3d49b053efa8058efc0566b2b0` source
   revision used by the imported candidate.
2. Apply the candidate patch in a separate, writable source worktree.
3. Build the wheel for `gfx803` with **`TENSOR_TOPK_OPT_LEVEL=-O0`** and record
   both patch SHA-256 values and the compiler wrapper/command in the build
   receipt. Do not infer that flag from the image revision.
4. Run the authentic `[2,4]`, `k=2` top-k probe before the full model.  Require
   no GPU fault; compare values and indices with CPU for non-ties, ties, NaNs,
   both `largest` directions, and both sorted modes.
5. Run C2 forward parity, backward parity, one matched AdamW update, then the
   existing 20-step trajectory.  The current sort-selector receipt is a
   control, not promotion evidence for this wheel.
6. Preserve mapped-library, kernel-name, dmesg/KFD, and receipt hashes before
   considering Cachix publication.

The previous `sbtopk` failure is the reason this sort-backed candidate exists.
Do not promote either candidate, or the model-level sort control, until the
semantic matrix and native C2 trajectory pass on card.

## Non-goals

- This does not alter Schaka's SGEMM replacement, ROCr/CLR, or TensorTopK
  compiler workaround.
- This does not claim the runtime fault is caused by optimization level.
- This does not admit unrestricted C2 training or publish a Cachix closure.
