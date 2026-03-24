# gfx803 old-ABI framework rebuild spec

## Goal

Build a reproducible Nix-owned PyTorch framework lane for gfx803/Polaris that keeps the known-working old HSA/HIP ABI intact while rebuilding above it.

## Scope

- Primary target: `torch`
- Secondary targets: `torchvision`, `torchaudio`
- Runtime source: extracted old-ABI ROCm SDK plus the preserved old-ABI compatibility lane
- Explicit non-goal: forcing latest-class ROCm/HIP/HSA onto Polaris before the old-ABI lane is stable

## Success criteria

- The rebuild driver uses only the intended old-ABI SDK/runtime roots.
- `torch` imports from the rebuilt wheel.
- `torch.cuda.is_available()` is `True` on the preserved old-ABI lane.
- The driver fails fast if ROCm payloads resolve from unintended roots such as `/opt/rocm`.
