# Polaris (GFX803) Stability Blueprint

This document outlines the stabilized profile for running modern Machine Learning workloads (Diffusion, WhisperX) on AMD Polaris (RX 480/580) hardware using ROCm 6.x.

## ⚠️ Identified Hazards

1.  **Winograd Hangs:** Common convolution solvers that cause GPU ring timeouts and system freezes.
2.  **GEMM Drift:** MIOpen solver `GemmFwdRest` (ID 91) is numerically incorrect on Polaris, causing a ~0.15 drift per iteration.
3.  **rocBLAS Non-determinism:** `torch.einsum` and batch matmuls are non-deterministic by default on this architecture.
4.  **State Poisoning:** Sustained high-volume kernel launches degrade numerical integrity until even 1x1 convolutions fail.

## 🛡️ Recommended "Safe Profile"

To achieve stable and reproducible results, use the following environment variables.

### Environment Variables

```bash
# General Compatibility
export HSA_OVERRIDE_GFX_VERSION=8.0.3
export ROC_ENABLE_PRE_VEGA=1

# MIOpen Mitigations (Hangs & Noise)
export MIOPEN_DEBUG_CONV_WINOGRAD=0     # Fixes system hangs
export MIOPEN_DEBUG_CONV_GEMM=0         # Fixes major numerical noise/drift
export MIOPEN_DEBUG_CONV_FFT=0          # Extra safety margin

# Enforced Stability
export MIOPEN_DEBUG_CONV_DET=1          # Force deterministic solver selection
export MIOPEN_DEBUG_DISABLE_FIND_DB=1   # Bypass potentially stale or poisoned caches
export MIOPEN_FIND_ENFORCE=3            # Speed up startup with stable selection

# rocBLAS / PyTorch Determinism
export CUBLAS_WORKSPACE_CONFIG=:4096:8  # Required for deterministic matmuls
```

### PyTorch Configuration

Always initialize your scripts with:

```python
import torch

# Enable deterministic algorithms for Einsum/Attention
torch.use_deterministic_algorithms(True)

# (Optional) The "Absolute Precision" mode
# If you still see drift, disable MIOpen entirely. 
# This is slow but bit-perfect.
# torch.backends.cudnn.enabled = False 
```

## 🔍 Deep-Dive Findings

### Identified Failing Kernel
Through `rocprof`, the unstable kernel has been identified as a Tensile GEMM kernel:
`Cijk_Ailk_Bljk_SB_MT64x64x16_SN_AMAS3_BL1_BS1_EPS1_GLVWA4_GLVWB4_GRVWn1_GSU1_GSUASB_ISA803_K1_KLA_LPA0_LPB4_LRVW4_MMFGLC_NLCA1_NLCB1_PGR1_PLR1_SIA1_SU32_SUS256_SVW4_TT4_4_USFGROn1_VAW1_VSn1_VW4_VWB4_WG16_16_1_WGM8`

**Root Cause:** Tensile YAML generation bug for GFX803. Likely an indexing or register reuse issue in the assembly generation.

## Polaris ROCm Sanity Checklist

This is a practical coverage checklist for the failure class currently seen in
the WhisperX lane:

- `ring gfx timeout`
- `Host active wait ... for -1 ns`
- artifacted display / brief black screen / VRAM-loss reset

It is a stabilization and triage surface, not a promoted claim that every item
below is causal for the current WhisperX crash.

### 0. Baseline bring-up

Run once and keep the output:

```bash
rocminfo | rg -i 'name|gfx'
dmesg | rg -i 'amdgpu|kfd'
```

Expected:

- device enumerates as `gfx803`
- KFD is present
- no immediate firmware-load errors

### 1. Known-good stack discipline

Polaris is sensitive to ROCm/kernel/firmware drift.

Prefer:

- known-good ROCm `5.x` or early `6.x` lanes for `gfx803`
- kernel / firmware / ROCm combinations that are already retained in this repo

Avoid:

- treating latest ROCm as the default Polaris target
- mixing very new kernels with weakly supported older ROCm userspace without an
  explicit reason

### 2. VRAM and memory-pressure discipline

Keep:

- `WHISPERX_BATCH_SIZE=1`
- `WHISPERX_COMPUTE_TYPE=int8` unless a comparison run needs another type

Reduce concurrent pressure when testing:

- close browser and video-accelerated apps
- avoid concurrent GPU jobs

Interpretation:

- if shorter inputs improve stability a lot, VM / mapping pressure gets
  stronger as a trigger class

### 3. Pinned-memory hygiene

Pinned memory stays on the suspect DMA surface for the current crash lane.

Prefer:

- smaller batches
- fewer large host-device transfer bursts

Do not overread this:

- pinned memory being on the path does not by itself prove successful
  bad-data delivery into userspace

### 4. Kernel recovery parameters

Candidate watchdog / recovery settings:

```bash
amdgpu.lockup_timeout=10000
amdgpu.gpu_recovery=1
```

Rationale:

- more time before watchdog timeout
- better chance of reset instead of hard wedge

Treat these as stabilizers, not fixes.

### 5. Queue sensitivity probe

Useful toggle:

```bash
export HIP_LAUNCH_BLOCKING=1
```

Interpretation:

- if failures disappear, async queue progression is implicated more strongly
- if failures remain, the path is likely deeper than ordinary launch ordering

### 6. Display/compositor isolation

Because the symptom set includes artifacts and compositor fallout, try at least
one comparison run with lower display pressure if practical:

- avoid active desktop churn
- if safe, switch to TTY or reduce compositor stress before the run

Interpretation:

- improvement here suggests display contention is an aggravator
- it still does not promote the compositor to root cause

### 7. Thermal and power sanity

Fans ramping is consistent with firmware fallback. Check that thermals and power
are not adding noise:

```bash
watch -n1 sensors
```

### 8. Current pre-crash sentinel

For the retained WhisperX crash lane, treat:

- first `Host active wait ... for -1 ns`

as the earliest reliable pre-crash sentinel.

Record:

- stage where it first appears
- last concrete op before it
- rough delay to visible crash/reset

### 9. Minimal differential runs

For the current RCA path, the smallest useful matrix is:

- A: long-file baseline with memory-copy trace on
- B: shorter or chunked input, same lane
- C: same long input, memory-copy trace off
- D: same long input, alternate compute type if supported

Read them in layers:

- confirmed failure class:
  - does `ring gfx timeout` still appear?
- trigger class:
  - does lower memory pressure help?
  - does lower copy-path perturbation help?
- ownership hypothesis:
  - does changing compute type move the failure enough to implicate a specific
    ROCm/kernel/library path?

## Patch shapes by failure layer

This is the practical "what would we actually change?" view for the current
WhisperX reset-class lane. These are intervention families, not yet accepted
fixes.

Current chain:

- compute tail
- D2H copy
- first `Host active wait ... for -1 ns`
- `ring gfx timeout`
- reset / VRAM-loss / artifacts

### 1. VM / page-mapping pressure reduction

Patch shapes:

- chunk input or process shorter segments
- flush or release intermediate GPU state between segments if the workload
  allows it
- preallocate and reuse buffers where practical instead of churn-heavy
  allocation/free cycles
- keep peak VRAM footprint low

Expected movement:

- first `-1 ns` appears later or disappears
- timeout becomes more input-length or pressure sensitive

### 2. Queue / ring forward-progress visibility

Patch shapes:

- `HIP_LAUNCH_BLOCKING=1` as a probe
- explicit sync or drain points after heavy phases where the framework makes
  that possible
- watchdog tolerance as a stabilizer only:
  - `amdgpu.lockup_timeout=10000`

Expected movement:

- failure becomes earlier but clearer
- `-1 ns` may move earlier, or a clearer earlier failure may replace a later
  opaque stall
- longer watchdog can increase delay to reset without changing root cause

### 3. DMA / D2H completion-path relief

Patch shapes:

- same long input with memory-copy trace off
- reduce D2H burst size or frequency where the workload allows it
- stage or split host transfers if that path becomes editable
- avoid unnecessary contention on default/null stream

Expected movement:

- first `-1 ns` shifts or disappears
- timeout becomes less deterministic or less frequent if D2H completion
  pressure was the active trigger

### 4. Backend or kernel-path substitution

Patch shapes:

- alternate compute type such as `float16` or `float32` if supported
- any future toggle that swaps kernel family mix without changing workload
  semantics

Expected movement:

- one path survives while another fails
- ownership hypothesis shifts toward a narrower ROCm/library/kernel-path bug

### 5. Display-path isolation

Patch shapes:

- lower desktop churn
- TTY comparison run if safe
- keep browsers and video acceleration out of the test window

Expected movement:

- artifact presentation may reduce
- a surviving `ring gfx timeout` still keeps the display stack secondary

## Tool and mitigation matrix

This section maps the current failure layers onto existing tools and controls.
These are the concrete levers already available to the harness, workload, host,
or driver surface. They are not all equally safe as defaults.

### 1. Runtime and environment controls

| Tool / method | Targets | How to use | What it does | Expected signal |
| --- | --- | --- | --- | --- |
| `HIP_LAUNCH_BLOCKING=1` | queue, VM | `export HIP_LAUNCH_BLOCKING=1` | serializes launches and surfaces ordering/progress problems earlier | first `-1 ns` may disappear or move earlier; timeout frequency can drop if async queueing is the issue |
| lower batch / chunk input | VM | keep `WHISPERX_BATCH_SIZE=1`; shorten or segment input | lowers peak VRAM pressure and mapping churn | first `-1 ns` appears later or disappears; resets become more pressure dependent |
| smaller segment windows | VM | prefer shorter segment or chunk windows on long files | lowers per-segment tensor and transfer footprint | stability improves even when total file length stays large |
| alternate compute type | VM, bug | switch `int8` / `float16` / `float32` if supported | changes kernel mix and memory footprint | one path stable and another crashy points toward a narrower ROCm/kernel-path bug |
| memory-copy trace off | DMA | leave `WHISPERX_ROCPROFV3_ENABLE_MEMORY_COPY_TRACE` unset | reduces copy-path perturbation from tracing | if stability improves, copy-path sensitivity gets stronger |

Pressure note:

- for the current WhisperX lane, total file length is a weaker control than the
  effective live working set
- the better pressure surface is:
  - segment size
  - batch size
  - overlap / retained state
  - effective concurrency
- a useful working approximation is:
  - segment size × batch size × concurrency

### 2. HIP / ROCm API patterns

| Tool / method | Targets | How to use | What it does | Expected signal |
| --- | --- | --- | --- | --- |
| stream fences / sync points | queue | insert `hipStreamSynchronize(...)` or equivalent drain point at heavy phase boundaries if the code path becomes editable | forces completion and surfaces bad state earlier | failure moves earlier and cleaner, often before the first `-1 ns` |
| event timing | queue | bracket copies or kernels with `hipEventRecord` / `hipEventQuery` if the code path becomes editable | shows which operation stops completing | first non-completing event should align with `T0` |
| pinned-memory reuse | VM, DMA | allocate pinned buffers once and reuse them if the code path becomes editable | reduces fragmentation and mapping churn | fewer stalls; first `-1 ns` less frequent |
| avoid zero-copy / mapped-host shortcuts | VM | avoid direct mapped-host access where the stack allows it | simplifies the address space | fewer VM / mapping-related failures |
| dedicated copy stream | DMA, queue | move critical D2H/H2D operations onto a dedicated stream if the workload surface becomes editable | decouples compute and copy contention | fewer stalls if compute/copy contention was the trigger |
| chunked D2H | DMA | split larger D2H operations into smaller copies if the path becomes editable | reduces DMA burst pressure | first `-1 ns` shifts or disappears |

### 3. ROCm profilers and tracers

| Tool / method | Targets | How to use | What it shows | Expected signal |
| --- | --- | --- | --- | --- |
| `rocprofv3` with `rocpd` | all | current wrapper default for crash-focused structured capture | retained kernel plus copy timeline when it survives | last completed op before stall; confirms or weakens D2H adjacency |
| `--memory-copy-trace` | DMA | enable selectively with `WHISPERX_ROCPROFV3_ENABLE_MEMORY_COPY_TRACE=1` | copy bursts, sizes, and directions | copy-heavy tail before stall strengthens DMA exposure |
| `rocminfo` / `rocm-smi` | VM, queue | quick state checks outside the run | device state, clocks, memory state | can confirm post-reset VRAM loss or abnormal clocks, but not the exact pre-crash op |

### 4. Kernel / driver controls

| Tool / method | Targets | How to use | What it does | Expected signal |
| --- | --- | --- | --- | --- |
| `amdgpu.lockup_timeout=` | queue | kernel cmdline | increases watchdog window | first `-1 ns` still appears, but delay to reset increases |
| `amdgpu.gpu_recovery=1` | queue | kernel cmdline | favors reset over hard wedge | recovery to shell becomes more likely |
| `journalctl -k` / previous-boot logs | VM, queue | inspect after crash | names ring timeout, VM fault, BACO, VRAM loss | confirms failure class and recovery shape |

### 5. System and display isolation

| Tool / method | Targets | How to use | What it does | Expected signal |
| --- | --- | --- | --- | --- |
| TTY / low-compositor run | queue, VRAM | reduce or remove compositor load if safe | removes display contention and makes fallout cleaner | artifacts may reduce even if resets remain |
| disable other GPU users | VM, DMA | close browsers, video decode, and other GPU clients | lowers background memory and copy pressure | fewer or later stalls |

### 6. Version and stack selection

| Tool / method | Targets | How to use | What it does | Expected signal |
| --- | --- | --- | --- | --- |
| ROCm version swap | bug | move between retained `5.x` and early `6.x` style lanes | changes runtime, kernel-path, and firmware interaction | binary stable-vs-crashy outcome strengthens ownership toward stack/driver path |
| kernel version swap | bug, queue | compare across retained kernels if available | changes scheduler and VM behavior | timeout cadence or recovery behavior changes materially |

### Minimal discriminator using the matrix

The smallest high-value run sequence remains:

1. baseline
2. baseline plus `HIP_LAUNCH_BLOCKING=1`
3. shorter or chunked input

Read it as:

- blocking-mode fix:
  - async queue or ordering problem gets stronger
- shorter-input fix:
  - VM / mapping pressure gets stronger
- neither helps, but backend changes do:
  - ROCm/library/kernel-path bug gets stronger

### Implementation lane alignment

The doc surface now treats each lane as an explicit implementation target:

1. Baseline crash lane (`first_compute` + memory-copy trace)
2. Queue/visibility lane (`HIP_LAUNCH_BLOCKING=1`, drain points)
3. Pressure-control lane (shorter segments, batch_size=1)
4. DMA-light lane (copy trace off, staged copies)
5. Backend lane (alternate compute or kernel mix)

Each lane feeds the shared sentinels before any claim is promoted.

### Pressure-focused discriminator

If the newer observation is that smaller segment windows stay stable even on
longer files, prefer this tighter sequence:

1. baseline
2. same long file with smaller segment windows and `batch_size=1`
3. same long file with `HIP_LAUNCH_BLOCKING=1`

Read it as:

- smaller-segment fix:
  - per-segment memory pressure is the active trigger
- blocking-mode fix:
  - async queue overlap is the active trigger
- both help:
  - VM / mapping pressure and queue progression are interacting

### 10. Low-value rabbit holes

De-prioritize:

- host-only segfault theory
- "bad memcpy should have returned an error immediately"
- compositor as primary cause

The retained failure shape is lower than that layer:

- queue forward-progress loss
- D2H copy/wait exposure
- reset / VRAM loss / artifacts
