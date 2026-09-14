# Modern TheRock gfx803 prebuilt and upstream-restoration lane

This lane complements the extracted `5.7`/`6.4` controls and the preserved old-HSA/HIP ABI lane. The broader endpoint is explicit:

> make AMD officially support RX 580 / Polaris (`gfx803`) again, while preserving honest capability boundaries for operations the architecture genuinely cannot perform.

The immediate engineering task is therefore not merely to keep one private fork alive. It is to turn every missing gfx803 capability into a small, testable, upstream-shaped delta and carry the target through TheRock's own promotion states: **Build Passing -> Sanity Tested -> Release Ready**.

## Project lineage

There are several related historical lines and they should not be collapsed:

- early TheRock development used the `nod-ai/TheRock` repository lineage before the project moved under the `ROCm` organization;
- `lamikr/rocm_sdk_builder` was another early community build-system route, and received a public gfx803 support request in 2024;
- Robert Rosenbusch's gfx803 builds established practical application stacks by rebuilding omitted target code;
- Luca Bruni's March 2026 TheRock fork demonstrated that modern TheRock could enumerate gfx803 again by restoring legacy doorbell semantics and CLR admission;
- `Schaka/rocm-gfx803` now provides a separately maintained ROCm 10.0 full-stack reference with prebuilt GHCR images and real-hardware correctness/workload receipts;
- current `ROCm/TheRock` is AMD's build/release system and now exposes an optional `therock_custom_amdgpu_targets.cmake` hook specifically suitable for out-of-tree target bring-up.

The current lane uses those earlier results as evidence and regression fixtures while targeting present upstream source.

## Primary source and reference sources

The default producer pins current upstream TheRock:

- repo: `https://github.com/ROCm/TheRock.git`
- pinned commit: `4213e176e29199c5dea5b54513bc3b1d36d91ca9`
- target family: `gfx803-dgpu`
- target registration: `patches/therock-gfx803/therock_custom_amdgpu_targets.cmake`

Luca's known-restored source remains independently reproducible with:

- repo: `https://github.com/lucbruni-amd/TheRock.git`
- commit: `3d4ad6093a0069876fbfff590bb56ddb340ae9c5`
- option: `--reference-luca`

The reference commit reported `rocminfo` and `clinfo` successfully detecting an RX 550. That receipt establishes a restoration precedent; it is not a claim that every current component or workload is correct.

The Schaka ROCm 10 line is a second, stronger downstream reference rather than an upstream source dependency. Its published image can be probed with:

```bash
bash scripts/probe-schaka-rocm10-gfx803-reference.sh
```

The default image is:

```text
ghcr.io/schaka/rocm-migraphx-ort-torch-builder:rocm10.0-gfx803
```

The probe records the resolved image ID/digest plus `rocminfo` and a tiny PyTorch GPU correctness smoke under `out/rocm10-gfx803-reference/`. Every receipt is marked `reference-only`: **community success != AMD Release Ready**.

For the source-bound patch/capability classification behind that reference, see `docs/GFX803_UPSTREAM_PATCH_ATLAS.md`.

## Current rebase strategy

The modern rebase deliberately preserves AMD's 2026 graceful unsupported-device handling rather than simply reverting it.

The current upstream behavior is approximately:

```text
DoorbellType 2 -> admitted
DoorbellType 0/1/unknown -> INVALID_ISA -> device skipped without killing hsa_init
```

The gfx803 lane changes only the paid coordinate:

```text
DoorbellType 1 (Polaris) -> admitted because legacy queue semantics are restored
DoorbellType 0/unknown   -> existing graceful skip remains
DoorbellType 2           -> native modern AQL path remains
```

The queue implementation and CLR/OpenCL changes are replayed from Luca's hardware-tested patch set, pinned by Git blob IDs. The older constructor hunk is excluded because the current upstream source has the newer safe-skip switch; the repo-owned `0000-rocr-readmit-doorbell-type1.patch` performs the narrower modern adaptation.

This gives a cleaner upstream proposition than deleting the guard wholesale:

```text
safe unsupported-device handling
+
restored, tested type-1 implementation
=
Polaris support without regressing topology safety
```

## Build

Prepare current upstream source and prove that the patch sequence still applies:

```bash
bash scripts/build-therock-gfx803-artifacts.sh --prepare-only
```

Build the small core-runtime lane first:

```bash
bash scripts/build-therock-gfx803-artifacts.sh --core-only
```

Build the wider current gfx803 target:

```bash
bash scripts/build-therock-gfx803-artifacts.sh --full
```

Reproduce Luca's independently known-restored March lane:

```bash
bash scripts/build-therock-gfx803-artifacts.sh --reference-luca --full
```

The primary materialized artifact is:

```text
artifacts/therock-gfx803/
├── meta/
│   ├── source.env
│   ├── unsupported_component_frontier.txt
│   ├── promotion.env
│   ├── rocminfo.txt
│   ├── clinfo.txt
│   └── smoke.env
├── rocm/                   # prebuilt TheRock ROCm distribution
└── work/                   # source/build workspace; rebuildable
```

The reference lane is kept separate under `artifacts/therock-gfx803-reference-luca/` by default.

## Capability debt is not permanent impossibility

The initial exclusion frontier follows the known-restored March target:

- `hipBLASLt`
- `hipSPARSELt`
- `composable_kernel`
- `rocWMMA`
- `rocprofiler-compute`
- `MIOpen`

Each exclusion is now an investigation item, not a declaration that the card can never support the library. The ROCm 10 reference is particularly useful here: it already includes working gfx803-specific paths for components that the initial TheRock target excluded, so exclusion from one build target cannot establish technical impossibility.

Classify each missing component into one of these categories:

```text
policy / support-matrix gate
removed implementation that can be restored
target code no longer emitted
build-system regression
algorithm requires an unavailable ISA feature
algorithm can use a fallback implementation
runtime correctness defect
unknown
```

A component that genuinely requires unavailable hardware instructions may stay excluded. The project should then look for another mathematically equivalent algorithm, a fallback implementation, or a different execution decomposition where that is practical. `gfx803 good` does not require pretending the silicon has instructions it does not have.

## Query-indexed promotion ladder

Do not collapse support into one boolean. Advance the target through:

1. target registered by TheRock
2. patch set applies to the pinned current source
3. build produced (**Build Passing** candidate)
4. `rocminfo` enumerates gfx803
5. queue creation and tiny HSA dispatch
6. tiny HIP kernel
7. OpenCL enumeration/kernel where relevant
8. basic rocBLAS / rocSOLVER / primitive-library smokes
9. rebuilt PyTorch tensor execution
10. numerical determinism/correctness
11. async/ordering correctness
12. real-workload reset safety
13. AMD CI / **Sanity Tested**
14. AMD support matrix / **Release Ready**

Important non-implications remain:

```text
Build Passing != Sanity Tested
Sanity Tested != every workload correct
rocminfo enumeration != HIP execution
HIP execution != library target code present
library launch != numerical correctness
short correctness != long async/reset safety
community prebuilt != official AMD support
```

## Existing high-value regressions

The old lanes already provide downstream tests rather than forcing the modern lane to rediscover failures at application scale:

- LeechTransformer isolates a layout/materialization nondeterminism boundary and records that `HIP_LAUNCH_BLOCKING=1` changes the outcome;
- WhisperX exposes a copy/wait-adjacent queue forward-progress/reset failure under real load;
- the old-ABI and extracted 5.7/6.4 lanes provide comparison points for ABI, enumeration and numerical behavior.

The ROCm 10 reference adds another discriminator: its patch history contains independently hardware-tested copy/GPUVM fixes. Those are candidate mechanisms to test against our Leech/WhisperX reproducers, not automatic explanations of them.

Once current TheRock pays enumeration and basic execution, route it directly into those existing discriminators.

## Publish / restore

The standard cache publisher includes `artifacts/therock-gfx803` when present:

```bash
bash scripts/publish-ollama-and-extracted-artifacts-to-cachix.sh artifacts/therock-gfx803
```

A fresh clone can restore published artifacts using the existing cache contract:

```bash
cachix use gfx803-rocm
bash scripts/restore-cachix-artifacts.sh
```

Publishing is a distribution receipt, not an AMD support receipt.

## Upstream objective

The desired upstream state is ultimately a normal TheRock target entry and corresponding release extra, analogous to existing older targets such as `gfx900`/`gfx906`:

```text
gfx803 target registered upstream
-> supported component exclusions have issue-linked reasons
-> build artifacts published by AMD
-> Polaris hardware runner / repeatable sanity receipt
-> SUPPORTED_GPUS.md Build Passing
-> Sanity Tested
-> Release Ready
-> official ROCm compatibility/support surface
```

The repo's job is to make that progression cheap to review: small patches, exact source pins, prebuilt artifacts, reproducible failure cases, and evidence for every promotion step.
