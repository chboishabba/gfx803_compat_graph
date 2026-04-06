# Incident: 2026-03-30 WhisperX Align GPU Hang Without Profiler, Full Completion With `rocprofv3`

This note captures the first clean split between the no-profiler WhisperX crash
path and the profiler-attached WhisperX path on this host.

Later runs on the same date refined that boundary further for the main long
file: the crash can also land earlier, during `transcribe`, before an
`align`-selected profiler region ever begins.

## Why this matters

The repo previously only had a retained boundary of "after `transcribe`
starts". The new pair of runs is stronger:

- the no-profiler run completed `transcribe`, entered `align`, and then hit a
  retained `GPU Hang`
- the `rocprofv3` run completed `align` and wrote real profiler artifacts, then
  later crashed inside profiler teardown instead of the GPU workload itself

That means the instrumentation path is now a real confounder. It can change the
timing or pressure enough to let the same workload survive.

## Correlated evidence

No-profiler run:

- bundle root:
  - `out/whisperx-rca-matrix/manual-no-prof-2026-03-29T23-30-36/2026-03-29T23-30-36/`
- retained harness events:
  - `out/whisperx-rca-matrix/manual-no-prof-2026-03-29T23-30-36/2026-03-29T23-30-36/harness/events.jsonl`
- retained run log:
  - `out/whisperx-rca-matrix/manual-no-prof-2026-03-29T23-30-36/2026-03-29T23-30-36/run.log`

Profiler-attached run:

- bundle root:
  - `out/whisperx-rca-matrix/manual-rocprofv3-2026-03-29T22-43-27/2026-03-29T22-43-27/`
- retained harness events:
  - `out/whisperx-rca-matrix/manual-rocprofv3-2026-03-29T22-43-27/2026-03-29T22-43-27/harness/events.jsonl`
- profiler output directory:
  - `out/whisperx-rca-matrix/manual-rocprofv3-2026-03-29T22-43-27/2026-03-29T22-43-27/profiler/`
- retained run log:
  - `out/whisperx-rca-matrix/manual-rocprofv3-2026-03-29T22-43-27/2026-03-29T22-43-27/run.log`

Host-side crash evidence correlated with the no-profiler lane:

- fresh devcoredump:
  - `/var/log/amdgpu-devcoredumps/card1-devcoredump-20260330-011329.bin`
- previous-boot kernel journal window:
  - `journalctl -k -b -1 --since '2026-03-30 00:35:00' --until '2026-03-30 01:25:00'`

## Narrowest safe current reading

From the no-profiler `events.jsonl`:

- `run_start` at `2026-03-29T23:30:44+1000`
- `load_model` ended at `23:30:53`
- `load_audio` ended at `23:31:00`
- `transcribe` ended at `2026-03-30T00:41:27+1000`
- `align` started at `2026-03-30T00:41:27+1000`
- no retained `stage_end` for `align`
- no retained `run_end`

From the no-profiler `run.log` tail:

- final retained userspace signal:
  - `HW Exception by GPU node-1 ... reason :GPU Hang`

From the host journal:

- first matching reset wave starts at `2026-03-30 01:13:28`
- the kernel reports:
  - `ring gfx timeout, signaled seq=40155106, emitted seq=40155108`
  - `GPU reset begin`
  - `BACO reset`
  - `VRAM is lost due to GPU reset!`
  - `device wedged, but recovered through reset`
- repeated soft-recovered `ring gfx timeout` lines continue after that first
  reset

From the profiler-attached `events.jsonl`:

- `transcribe` ended at `2026-03-29T23:01:58+1000`
- `align` ended at `2026-03-30T00:34:11+1000`
- `run_end status=ok` at `2026-03-30T00:34:11+1000`

From the profiler-attached `run.log` tail:

- result files under `profiler/` were opened and written
- the later failure is a `SIGSEGV` in `librocprofiler-sdk.so.1.1.0` /
  `librocprofiler-sdk-tool.so.1.1.0`

## Implications

This lets us say:

- the no-profiler WhisperX lane can survive through `transcribe`, enter
  `align`, and then still hit the GPU hang/reset class
- the strongest current retained boundary is now later than the older
  March 27 note:
  - `transcribe` completed
  - `align` started
  - then the GPU hang/reset landed
- `rocprofv3` is now proven usable enough to generate real kernel, marker, and
  memory-trace artifacts on this host
- `rocprofv3` also changes timing or pressure enough that the same reduced run
  can complete successfully

This does **not** let us say:

- that `align` is definitively the unique first bad compute path
- that memory pressure is the only trigger
- that compositor redraw or `alt-tab` caused the reset

## First profiler readout

The successful `rocprofv3` bundle is already useful even before deeper
post-processing.

What the tail of `whisperx_kernel_trace.csv` shows near the end of successful
`align`:

- repeated Tensile / rocBLAS GEMM families, especially:
  - `Cijk_Alik_Bljk_SB_MT32x32x32...`
  - `Cijk_Alik_Bljk_SB_MT64x128x16...`
  - `Cijk_S`
- PyTorch pointwise kernels interleaved with those GEMMs:
  - `vectorized_layer_norm_kernel`
  - `GeluCUDAKernelImpl`
  - `direct_copy_kernel_cuda`
  - `CUDAFunctor_add`
  - final `softmax_warp_forward`

What the tail of `whisperx_memory_copy_trace.csv` shows in the same late window:

- repeated short `DEVICE_TO_HOST` copies followed by `HOST_TO_DEVICE` copies
- the retained late-window copies are small compared with the heaviest copies in
  the full trace

What is missing from the current retained profiler output:

- in the first successful heavy `align` bundle, the expected explicit
  `stage_start` / `stage_end` ROCTX markers did not appear in
  `whisperx_marker_api_trace.csv`
- that earlier file mostly showed library-level marker/range activity such as
  `rocblas_*`, not the harness stage labels

Follow-up verification after patching the harness:

- verification bundle:
  - `out/whisperx-trace/2026-03-30T07-54-25/`
- the harness now binds `librocprofiler-sdk-roctx.so.1`
- the retained marker CSV now contains:
  - `run_start`
  - `stage_start:load_model`
  - `stage_end:load_model`
  - `whisperx:load_model`
  - `run_end:load_model`

Follow-up heavy profiler run after that marker fix:

- crash bundle:
  - `out/whisperx-trace/2026-03-30T08-23-52/`
- retained harness events show:
  - `run_start` at `2026-03-30T08:23:59+1000`
  - `stage_end:transcribe` at `2026-03-30T08:41:34+1000`
  - `stage_start:align` at `2026-03-30T08:41:34+1000`
  - no retained `stage_end:align`
  - no retained `run_end`
- retained `run.log` tail again ends in:
  - late softmax / copy activity
  - `HW Exception by GPU node-1 ... reason :GPU Hang`
  - `rocprofv3` catching signal `6`
- host-side reset wave starts at `2026-03-30 09:40:16` and shows:
  - `ring gfx timeout`
  - `GPU reset begin`
  - `BACO reset`
  - `VRAM is lost due to GPU reset`
  - repeated soft-recovered `ring gfx timeout` lines afterward
- matching fresh devcoredumps:
  - `/var/log/amdgpu-devcoredumps/card1-devcoredump-20260330-094017.bin`
  - `/var/log/amdgpu-devcoredumps/card1-devcoredump-20260330-094044.bin`
  - `/var/log/amdgpu-devcoredumps/card1-devcoredump-20260330-094111.bin`
- important limit:
  - the `profiler/` directory for this crashy profiled run stayed empty, so no
    stage-marked profiler CSV survived the reset

So the first useful read is:

- late successful `align` is dominated by long GEMM-heavy compute with
  pointwise normalization / activation / copy steps around it
- the current profiler bundle is strong enough to name kernel families
- the marker-visibility issue is now fixed for newly captured bundles
- a heavier profiled `align` run can still crash even with the fixed harness
- but if the host resets before `rocprofv3` flushes its outputs, the explicit
  stage markers still do not survive into retained profiler CSVs
- so the remaining gap is no longer marker labeling alone; it is profiler
  durability under the crashy workload

## Current working model

The strongest current model is:

- WhisperX remains a good GPU-workload reproducer for the reset class
- no-profiler runs now narrow the retained crash boundary to after `align`
  begins
- profiler overhead is significant enough to mask or defer the reset path on at
  least this reduced run
- the next best RCA surface is the successful `rocprofv3` bundle, because it
  finally contains profiler artifacts from the same general workload shape

Later same-day selected-region follow-up:

- `align`-selected profiling is now validated on successful shorter runs:
  - `out/whisperx-trace/2026-03-30T12-25-36/`
  - `out/whisperx-trace/2026-03-30T12-28-28/`
  - both retained non-empty `profiler/whisperx_results.db`
- the main long-file run at `out/whisperx-trace/2026-03-30T12-38-04/` crashed
  earlier:
  - `load_model` completed
  - `load_audio` completed
  - `transcribe` started
  - no retained `stage_end:transcribe`
  - no retained `stage_start:align`
- that run's retained `run.log` ends with:
  - `hipMemcpyWithStream(... hipMemcpyDeviceToHost ...)`
  - host active wait
  - `GPU Hang`
- matching previous-boot kernel evidence starts at `2026-03-30 12:39:27` and
  shows:
  - `ring gfx timeout`
  - `GPU reset begin`
  - `BACO reset`
  - `VRAM is lost due to GPU reset`
  - VM fault reading from `TC4`
  - fresh devcoredump `/var/log/amdgpu-devcoredumps/card1-devcoredump-20260330-123928.bin`

So the current primary profiler gate should move away from a fixed named stage
for the long-file crash lane. `align` remains useful as a successful
observability lane, but it is now too late for the main crashing input. The
next better control law is a compute-stage policy:

- start profiling at the first compute stage reached
- keep exact-stage selection available for shorter successful comparison runs

That control law is now implemented in the harness and wrapper as:

- `--profile-stage-policy first_compute`
- `WHISPERX_PROFILE_STAGE_POLICY=first_compute`

## Consequence for repo claims

Repo-facing wording should currently distinguish:

- WhisperX can launch and use the GPU on the extracted host runtime
- the no-profiler reduced repro can still hit a GPU hang/reset after `align`
  starts
- `rocprofv3` is now a valid evidence path for this repo, but its own teardown
  can segfault after writing results
- none of that promotes WhisperX to a host-stable workflow claim

## Next action

Use the successful `rocprofv3` bundle as the new comparison anchor:

- correlate `whisperx_marker_api_trace.csv` with `whisperx_kernel_trace.csv`
- identify the last kernel families and memory-copy bursts near the
  `transcribe -> align` transition
- compare those with the no-profiler crash boundary and the `01:13:28`
  reset window
- if another profiled heavy run is attempted, prefer the new crash-capture
  mode in `scripts/trace-whisperx-rocprof.sh`
  - it keeps the profiler surface narrower:
    - marker trace
    - kernel trace
    - optional memory-copy trace when copy-path suspicion is the active target
    - CSV or `rocpd`, with `rocpd` preferred for the next crashy attempt
  - it now supports selected-region profiling around a policy-controlled stage
  - for the long-file crash lane, the next run should use a compute-stage
    policy rather than hardcoding `align` or `transcribe`
  - the current primary long-file crash command should enable memory-copy trace
    on that `first_compute` policy so the retained `rocpd` bundle can test the
    copy-heavy-subwindow hypothesis directly
  - `--collection-period` remains available as a fallback when stage-gated
    profiling is not enough
  - it also keeps a cheap `heartbeat.log` side channel alive in the retained
    bundle so the current stage and profiler mode survive even if structured
    profiler output does not
  - it now also keeps a stronger `observer.log` stream with:
    - recent `run.log` tail
    - recent `events.jsonl` tail
    - profiler file names and sizes
    - current-boot kernel tail

Until that lands, the safe claim remains:

- WhisperX is a useful GPU RCA/reproducer surface
- no-profiler runs can still hang/reset after `align` begins
- long-file profiler-attached runs can also hang/reset during `transcribe`
  before `align` begins
- profiler instrumentation can mask the failure enough to complete the same
  reduced path

## 2026-03-30 15:27:20 copy/wait-adjacent crash

The later `first_compute + memory-copy-trace` run under
`out/whisperx-trace/2026-03-30T14-45-28/` tightened the boundary again:

- `transcribe` completed
- `align` started
- the last retained userspace sequence was:
  - `hipMemcpyWithStream(... hipMemcpyDeviceToHost, 121916, ...)`
  - `Host active wait for Signal ... for -1 ns`
  - `hipMemcpyWithStream(... hipMemcpyHostToDevice, 812160, ...)`
  - `Host active wait for Signal ... for -1 ns`
  - `GPU Hang`
- previous-boot kernel logs for `15:27:20` show:
  - `ring gfx timeout`
  - failed suspend of WhisperX process `pid 81461`
  - BACO reset
  - VRAM loss

This is strong enough to promote:

- `ring gfx timeout` is now the strongest directly observed failure class
- copy/wait adjacency is now the strongest current exposure point
- the first `Host active wait ... for -1 ns` is now the earliest reliable
  retained pre-crash sentinel on this lane
- pinned-memory-backed DMA remains on the suspect surface because fast async
  D2H/H2D transfer likely depends on pinned host pages here

It is still not strong enough to promote:

- copy overflow as the root cause
- a simple host userspace crash copied back from GPU memory
- successful delivery of a bad payload into userspace as the primary failure
  shape

The best bounded statement remains:

- queue/ring forward-progress failure is the observed failure class
- a lower-level GPU VM, pinned-page, or DMA/copy-path trigger is most likely
  becoming visible during D2H copy and host wait
- that is more consistent with stalled copy completion than with a completed
  copy of already-corrupted data into host userspace

Minimal discriminating next matrix:

- A: current long-file baseline
  - `first_compute + memory-copy-trace`
- B: shorter or chunked input
  - same lane, lower memory footprint
- C: same long-file lane with memory-copy trace off
  - proxy for lower copy-path perturbation
- D: same long-file lane with alternate compute type if supported

Expected readout:

- observed failure class:
  - `ring gfx timeout` / queue forward-progress failure
- B improves a lot:
  - VM / mapping pressure gets stronger as trigger
- C improves a lot:
  - DMA / copy-path sensitivity gets stronger as trigger
- D alone changes outcome:
  - ROCm/kernel/library-path bug gets stronger as ownership hypothesis
- all fail similarly:
  - deeper ROCm/amdgpu instability on `gfx803` / Polaris remains the best
    umbrella ownership class

The doc chooses these five implementation lanes (baseline, queue/visibility, pressure-control, DMA-light, backend) and only promotes a claim once the lane whose tooling actually moves the `-1 ns` / `ring gfx timeout` sentinels behaves as expected.

## Later matrix follow-up: `per_segment_light` crash and `blocking` summary-only success

The named matrix lanes later refined the same-day RCA again.

`per_segment_light` on the long file still crashed even with `10s` chunking and
concurrency `1`, and the retained boundary tightened to:

- `hipEventSynchronize(...)`
- `Host active wait ... for -1 ns`
- `Memory access fault by GPU node-1 ... Reason: Page not present or supervisor privilege`
- `rocprofv3 caught signal 6`

That result promoted GPU VM / page-mapping fault above the earlier
copy-first suspicion for the non-blocking lanes.

The next named lane, `blocking`, then produced the first long-file matrix
success at the summary level:

- summary file:
  - `out/whisperx-rca-matrix/2026-03-30T16-45-56/summary.csv`
- retained summary fields:
  - `lane=blocking`
  - `hip_launch_blocking=1`
  - `memory_copy_trace=1`
  - `exit_code=0`
  - `kept_bundle=0`

Because `kept_bundle=0`, there is no retained success bundle for direct
`run.log` / `events.jsonl` / `whisperx_results.db` comparison yet.

So the safe current promotion is:

- `HIP_LAUNCH_BLOCKING=1` is the first practical stabilizing lever on the
  long-file repro
- but it is not yet a retained-bundle success claim
