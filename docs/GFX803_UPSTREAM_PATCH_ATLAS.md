# gfx803 upstream patch atlas

This atlas separates **what makes current gfx803 work** from **what AMD would need to carry upstream**. It is source-bound and deliberately keeps proven fixes, candidate fixes, superseded hypotheses, hardware faults, and release-policy state distinct.

## Reference lines

| Line | Role | Evidence status |
|---|---|---|
| Arch/CachyOS ROCm 7.2.4 | Native installed control | distro package baseline |
| extracted ROCm 5.7/6.4 | older compatibility controls | existing project receipts |
| Luca Bruni TheRock `3d4ad609...` | known-restored enumeration reference | RX550 `rocminfo` + `clinfo` reported working |
| Schaka/rocm-gfx803 `bc4b5acfd24cf29e1736900d54c047ca608da0b2` | current full-stack reference | ROCm 10.0 image + real-hardware workload receipts |
| current ROCm/TheRock | upstream target | minimal patch/review target |

The Schaka line is particularly important because it already demonstrates a ROCm 10.0 stack containing ROCr/CLR, rocBLAS, MIOpen, rocSOLVER, MIGraphX, PyTorch, ONNX Runtime, Triton and a gfx803 vLLM fork, with prebuilt GHCR images. That means the remaining project question is not whether modern ROCm can execute useful workloads on gfx803, but which deltas are necessary, which are optional/fallbacks, and which are upstreamable.

**Firewall:** `community success != AMD Release Ready`.

## Classification vocabulary

Every patch or exclusion should be assigned one primary class:

- **runtime prerequisite** — required for enumeration, queue creation, dispatch or memory semantics;
- **correctness fix** — wrong output, stale data, invalid mapping, crash, fault or hang with a bounded reproducer;
- **fallback / alternate computation** — avoids a hardware capability that gfx803 genuinely lacks while preserving the consumer query;
- **performance adaptation** — not needed for correctness, but materially improves practical use;
- **genuine ISA absence** — hardware feature does not exist; expose refusal or another algorithm rather than emulating support dishonestly;
- **diagnostic / superseded** — useful investigation history but not promoted causal mechanism;
- **hardware / VBIOS** — physical operating condition, not ROCm software debt;
- **release-policy debt** — target works for some query but lacks upstream build/sanity/release promotion.

## Runtime / enumeration foundation

### `hsa-agent-rejects-legacy-doorbell.patch`

**Class:** runtime prerequisite.

Restores the complete legacy DoorbellType 0/1 queue protocol that was removed upstream, not merely the agent-constructor admission check. The important dependency is:

```text
agent admitted
+
legacy queue resource/wptr semantics
+
legacy doorbell write protocol
-> usable HSA dispatch
```

For current upstream, retain AMD's newer graceful-skip behavior for genuinely unsupported types and re-admit only a legacy type whose queue path is actually restored and tested.

### `opencl-gfx8-hardcoded-rejection.patch`

**Class:** runtime/frontend-policy prerequisite.

Removes the explicit non-HIP GFX8 policy rejection and makes unsupported image-extension queries degrade image capability rather than reject the whole compute device. This is an exemplar of:

```text
missing optional capability != unusable GPU
```

## Copy / memory correctness seams

### `d2h-staged-copy.patch`

**Class:** correctness fix + alternate transfer strategy.

Schaka reports D2H copies into pinned/registered host memory faulting under allocation/free churn on gfx803. Their measured repair routes D2H through an existing GPU staging buffer plus CPU memcpy instead of letting the copy engine write the host destination directly. The important lesson is not merely the patch but the fallback shape:

```text
broken direct D2H path
-> staged GPU buffer
-> CPU landing copy
-> same user-visible copy result
```

This is directly relevant to our WhisperX copy/wait investigation, but it is **not yet evidence that WhisperX has the same root cause**. It is a candidate discriminator.

### `d2h-null-dsthost.patch`

**Class:** correctness fix.

On ROCm 10.0, a staged D2H copy into a host-accessible device allocation could pass `NULL` via `getHostMem()` and crash in `memcpy(dst=0x0, ...)`. The repair uses the destination device VA as the host-visible address for this allocation class. Schaka reports real-hardware vLLM completion after this and its VA-reuse dependency.

### `va-reuse-defer-noremap.patch`

**Class:** correctness fix / GPUVM lifetime.

Addresses a separate ROCm 10.0 virtual-address reuse collision where a deferred-free object was re-mapped, leaving a kernel GPUVM mapping alive while the userspace aperture allocator reused the same VA. The failure surfaced as code-object load failure / `HSA_STATUS_ERROR_OUT_OF_RESOURCES`, then a misleading no-binary/host-stub crash path. Keep this separate from enumeration and D2H debt.

## Corrected / superseded investigations

### `sdma-doorbell-missing-sfence.patch`

**Class:** diagnostic / superseded.

The patch history explicitly corrects its original causal model twice. The proposed SFENCE was found inert for the actual mapping type; a later ring-double-map hypothesis was also rejected. The ultimately reproduced hang was attributed to **VRAM-clock marginality on a mining-tuned VBIOS**, resolved by returning the memory clock to its rated 1750 MHz / correct VBIOS.

This is high-value negative evidence:

```text
correlated software intervention != established software root cause
```

and:

```text
GPU hang on gfx803 != automatically ROCm regression
```

### VRAM marginality

**Class:** hardware / VBIOS.

Keep operating-point validation as a prerequisite for software RCA. A card running memory above the board/VRAM's stable rating can manufacture VM faults and hangs that resemble runtime defects.

## Genuine hardware capability boundaries

### BF16

**Class:** genuine ISA absence.

The Schaka stack treats bf16 as unavailable on gfx803 rather than silently producing bad results. The practical fallback is fp16 where the application permits it. This is exactly the desired project discipline:

```text
unsupported instruction != unsupported GPU
```

A good gfx803 support profile can reject an unavailable dtype while being correct and well-supported for fp16/fp32 and other applicable consumers.

## Component frontier

The initial TheRock target exclusion list (`hipBLASLt`, `hipSPARSELt`, `composable_kernel`, `rocWMMA`, `rocprofiler-compute`, `MIOpen`) must be treated as an **investigation queue**, not permanent impossibility. Schaka's ROCm 10 line is evidence that at least MIOpen can be made useful with gfx803-specific work, so an exclusion in one build graph cannot itself pay an impossibility claim.

For each component, determine:

1. Does current source compile for gfx803?
2. If not, is the blocker target registration, a build regression, or an ISA requirement?
3. If a fast-path algorithm requires newer instructions, is there a legacy/generic/fallback implementation?
4. Can its core query be satisfied through another computation?
5. Is the result numerically correct on hardware?
6. Is the fallback practical enough to qualify for upstream support?

## Upstream promotion cut

The shortest route to official AMD support is now:

```text
current TheRock custom gfx803 target
-> minimal ROCr legacy queue restoration
-> bounded CLR gfx8 capability fallback
-> basic HIP + rocBLAS correctness
-> selectively upstream high-value correctness/fallback patches
-> reproducible Polaris hardware sanity runner
-> Build Passing
-> Sanity Tested
-> Release Ready
-> official gfx803 / RX580 support
```

Do not make every community workaround a prerequisite. The patch atlas should shrink as current upstream changes, alternatives are found, or investigations are disproved.

## Immediate experiments

1. Run the published ROCm 10 gfx803 reference image against our machine as a **reference-only** lane.
2. Record operating-point/VBIOS state before interpreting any reset-class failure.
3. Run our Leech deterministic layout repro against the ROCm 10 reference.
4. Run the smallest WhisperX/copy reproducer against it.
5. Compare direct versus staged D2H behavior before linking Schaka's D2H fix to our copy/wait sentinel.
6. In parallel, keep the current-upstream TheRock lane minimal and measure exactly which patches it still requires.
