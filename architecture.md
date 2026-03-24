# gfx803 old-ABI rebuild architecture

## Layers

1. Control lane
- Frozen extracted `6.4` Python/framework layer
- Known-working selected runtime/math layer

2. Upgrade lane
- Preserved old-HSA/HIP ABI lane
- Coherent extracted old-ABI ROCm SDK root
- Newer support libs only where they do not cross the ABI seam

3. Framework rebuild lane
- Rebuild `torch`
- Rebuild `torchvision`
- Rebuild `torchaudio`
- Treat torch smoke as the gate before moving to vision/audio

## Constraints

- Never silently fall back to `/opt/rocm` latest payloads during an old-ABI-targeted run.
- Prefer explicit repo-local artifact roots over ambient host ROCm state.
- Keep the control lane untouched.
