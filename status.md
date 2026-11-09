# Status

- Phase: Schaka ROCm 10.1 gfx803 C2 admission, candidate PyTorch repair
- Control lane: preserved and untouched
- Runtime baseline: relocated Schaka candidate passes frozen-QKV and dense-LILA
  CPU/GPU parity; it is not yet an accepted release
- Current blocker: `torch.topk` faults in gfx803 `warptopk` for the authentic
  C2 `[2, 4]`, `k=2` router input
- Candidate: architecture-scoped TensorTopK dispatch guard that falls through
  to the existing `sbtopk` route; source build and physical semantic/C2 gates
  remain open
