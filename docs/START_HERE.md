# Start Here

This page is for someone who has just opened the project and wants the shortest possible path to understanding what matters.

If you need one document to send to another person, start with [docs/USER_GUIDE.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/USER_GUIDE.md).

## What problem this project is solving

AMD Polaris cards such as the RX 580 use `gfx803`. Modern ROCm releases no longer treat that hardware as a normal supported target, so getting useful ML workloads running means combining:

- compatibility shims and restored runtime behavior where support was removed
- fallback algorithms where a newer fast path genuinely needs unavailable hardware features
- rebuilt target code where upstream binaries omit gfx803
- stability controls and careful numerical/reset validation
- reproducible prebuilt artifacts

The long-term endpoint is **official AMD support for RX580/Polaris again**, not merely a private fork. The repo therefore keeps community success, upstream patch applicability, TheRock Build Passing, Sanity Tested, and Release Ready as distinct states.

## What is already true

- The repo contains previously extracted `6.4` runtime artifacts in `lib-compat/`
- The repo contains a previously extracted Python environment in `docker-venv/`
- The more current reproducible workflow is in `gfx803_flake_v1/`
- The repo has a public Cachix binary cache at `https://gfx803-rocm.cachix.org`
- The extracted `6.4` host path covers torch and ComfyUI without needing the old full Docker at runtime
- WhisperX can launch on the same runtime and use the GPU, but remains an RCA/reproducer surface because real runs can still trigger KFD/reset instability
- the patched Ollama GPU path is extracted to `artifacts/ollama_reference/`, while host stability remains under investigation
- the `5.7` payload is separately usable under `artifacts/rocm57/`
- the native Arch/CachyOS ROCm 7.2.4 install is a useful distro control, not the current upstream-development target
- the repo has a framework rebuild driver that produces gfx803-targeted torch/vision/audio wheels against the preserved old-ABI SDK/runtime lane
- the project now carries a **current-upstream** TheRock gfx803 lane under `scripts/build-therock-gfx803-artifacts.sh`
- Luca Bruni's March 2026 TheRock restoration remains a known-restored enumeration reference
- Schaka's ROCm 10.0 gfx803 stack is an independent full-stack community reference with prebuilt GHCR images; probe it with `scripts/probe-schaka-rocm10-gfx803-reference.sh`
- `docs/GFX803_UPSTREAM_PATCH_ATLAS.md` classifies runtime prerequisites, correctness fixes, alternate-computation fallbacks, genuine ISA absence, superseded hypotheses, hardware/VBIOS faults, and release-policy debt
- the repo has initial CI validation scaffolding, but not a finished automatic GPU-backed publish pipeline

## If you only do one thing

For the existing local stack, run:

```bash
cd gfx803_flake_v1
nix develop .#base
verify-gfx803-host
```

For the modern already-built reference, use:

```bash
bash scripts/probe-schaka-rocm10-gfx803-reference.sh
```

That second command is deliberately a **reference-only** probe. A community image working on the card is strong feasibility/correctness evidence, but it is not an AMD support receipt.

## The practical paths

### Path A: Reuse the extracted `6.4` environment

```bash
bash scripts/extract-docker-libs.sh
source scripts/polaris-env.sh
./scripts/host-docker-python.sh tests/bug_report_mre.py
```

### Path B: Use the Nix entrypoints

```bash
cd gfx803_flake_v1
nix develop .#pytorch
run-drift-matrix
```

### Path C: Preserve/test the `5.7` diagnostic lane

```bash
bash scripts/extract-rocm57-artifacts.sh
bash scripts/host-rocm57-python.sh -c 'import torch; print(torch.cuda.is_available())'
```

### Path D: Keep the moving `ROCm 7+` extraction lane as a control

```bash
bash scripts/extract-rocm-latest-artifacts.sh
bash scripts/host-rocm-latest-python.sh -c 'import torch; print(torch.__version__)'
```

This is a moving-source experiment lane, not the modern gfx803 support path.

### Path E: Current-upstream TheRock restoration

First prove that the pinned source and patch series still compose:

```bash
bash scripts/build-therock-gfx803-artifacts.sh --prepare-only
```

Then pay the smallest useful build boundary:

```bash
bash scripts/build-therock-gfx803-artifacts.sh --core-only
```

Only then widen the build:

```bash
bash scripts/build-therock-gfx803-artifacts.sh --full
```

### Path F: Known-restored Luca reference

```bash
bash scripts/build-therock-gfx803-artifacts.sh --reference-luca --full
```

### Path G: Prebuilt ROCm 10.0 community reference

```bash
bash scripts/probe-schaka-rocm10-gfx803-reference.sh
```

This avoids a multi-hour local rebuild when the immediate question is whether our Leech/WhisperX discriminators reproduce on a modern full-stack gfx803 environment.

## Publish / restore

A repo-owned TheRock artifact can be published through the existing cache path:

```bash
bash scripts/publish-ollama-and-extracted-artifacts-to-cachix.sh artifacts/therock-gfx803
```

On another machine:

```bash
cachix use gfx803-rocm
bash scripts/restore-cachix-artifacts.sh
```

Publishing is a distribution receipt, not a Release Ready receipt.

## Important caveat

Do not interpret every gfx803 crash as a ROCm software bug. The current patch atlas includes at least one investigation where a software-looking hang was ultimately traced to VRAM-clock marginality from a mining-tuned VBIOS. Record hardware operating state before promoting reset-class causal claims.

## Files worth reading next

- [docs/THEROCK_GFX803_PREBUILT.md](THEROCK_GFX803_PREBUILT.md)
- [docs/GFX803_UPSTREAM_PATCH_ATLAS.md](GFX803_UPSTREAM_PATCH_ATLAS.md)
- [docs/USER_GUIDE.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/USER_GUIDE.md)
- [gfx803_flake_v1/README.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/gfx803_flake_v1/README.md)
- [POLARIS_STABILITY_BLUEPRINT.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/POLARIS_STABILITY_BLUEPRINT.md)
- [TODO.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/TODO.md)
