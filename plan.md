# Plan

## Milestone 1 — establish the exact PyTorch candidate

- Validate `patches/pytorch/gfx803-disable-warptopk.patch` against the pinned
  ROCm/PyTorch `d70fd61` source.
- Build a separate gfx803 wheel with that patch and Schaka's explicit
  `TENSOR_TOPK_OPT_LEVEL=-O0` TensorTopK compiler setting.
- Keep the imported, relocated ROCm 10.1 candidate unchanged as the control.

## Milestone 2 — prove the local operator repair

- Run the authentic C2 `[2,4]`, `k=2` probe plus values/indices/NaN/tie
  semantics against CPU.
- Capture the selected kernel and dmesg/KFD result; reject any fault.

## Milestone 3 — admit only the scoped workload

- Run C2 forward and backward parity, one AdamW update, and the bounded
  20-step trajectory.
- Review runtime linkage and retained receipts before accepting a Cachix
  candidate.  Do not extrapolate to unrestricted training.
