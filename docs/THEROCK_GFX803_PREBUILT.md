# Modern TheRock gfx803 prebuilt lane

This lane complements the existing extracted `5.7`/`6.4` controls and the preserved old-HSA/HIP ABI upgrade lane. It does **not** replace them.

The purpose is to make a modern source-built ROCm/gfx803 artifact reproducible enough to publish through the repo's existing `gfx803-rocm` Cachix cache, while preserving the exact source/patch boundary that restored Polaris enumeration.

## Pinned source

The default producer pins Luca Bruni's TheRock restoration commit:

- repo: `https://github.com/lucbruni-amd/TheRock.git`
- commit: `3d4ad6093a0069876fbfff590bb56ddb340ae9c5`
- target: `gfx803-dgpu`
- patch tag: `gfx803`

That commit restores the gfx8/Polaris build target, legacy ROCr doorbell semantics, and CLR/OpenCL admission. It also records an explicit component frontier for libraries that do not currently have a usable gfx8 path in that lane.

## Build

For the complete gfx803 target allowed by the pinned restoration commit:

```bash
bash scripts/build-therock-gfx803-artifacts.sh --full
```

For the smaller core bring-up lane used to test enumeration/HIP/OpenCL before spending cycles on the wider library graph:

```bash
bash scripts/build-therock-gfx803-artifacts.sh --core-only
```

To fetch and pin the source without building:

```bash
bash scripts/build-therock-gfx803-artifacts.sh --prepare-only
```

The materialized artifact is written under:

```text
artifacts/therock-gfx803/
├── meta/
│   ├── source.env
│   ├── unsupported_component_frontier.txt
│   ├── rocminfo.txt        # when the smoke runs
│   ├── clinfo.txt          # when clinfo is available
│   └── smoke.env
├── rocm/                   # prebuilt TheRock ROCm distribution
└── work/                   # source/build workspace; large and rebuildable
```

The distributable payload is `artifacts/therock-gfx803/rocm`. The `meta` receipts keep the source commit, patch tag, build mode, and smoke state attached to it.

## Current unsupported-component frontier

The pinned restoration commit excludes these from its gfx803 target:

- `hipBLASLt`
- `hipSPARSELt`
- `composable_kernel`
- `rocWMMA`
- `rocprofiler-compute`
- `MIOpen`

That exclusion list is a capability boundary, not a statement that the rest of the stack is validated. In particular:

```text
build produced
!= rocminfo enumerates
!= OpenCL enumerates
!= HIP kernel executes correctly
!= rocBLAS is numerically trustworthy
!= PyTorch workload is stable
```

## Publish / restore

The standard cache publisher now includes `artifacts/therock-gfx803` when the directory exists:

```bash
bash scripts/publish-ollama-and-extracted-artifacts-to-cachix.sh artifacts/therock-gfx803
```

or publish the normal set of present artifacts:

```bash
bash scripts/publish-ollama-and-extracted-artifacts-to-cachix.sh
```

The publisher maps the artifact directory into the Nix store, pushes it to the public `gfx803-rocm` Cachix cache, and records the resulting store path in `cachix-artifacts.manifest`.

A fresh clone can then restore it with the existing generic restore path:

```bash
cachix use gfx803-rocm
bash scripts/restore-cachix-artifacts.sh
```

## Promotion order

Treat the modern lane as a staged compatibility producer:

1. source pinned / patch applied
2. build produced
3. `rocminfo` enumeration
4. `clinfo` enumeration where relevant
5. tiny HIP execution smoke
6. library-specific smoke (`rocBLAS`, etc.)
7. deterministic/correct PyTorch micro-repro
8. short real workload
9. long/reset-sensitive workload
10. publish/promote as a user-facing prebuilt lane

The old-ABI lane remains the practical control while the modern TheRock lane advances through those gates.
