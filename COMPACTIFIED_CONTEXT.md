# Compactified context

## 2026-03-30 Transcribe-selected crash boundary update

### Current decision

- Do not treat a fixed named stage as the primary profiler control law for the
  long WhisperX repro file anymore.
- Keep exact-stage selection available for comparison and successful
  observability runs.
- Move the next primary crash attempt to a compute-stage policy:
  - start profiling at the first compute stage reached
  - keep exact-stage selection as a secondary comparison surface

### What the latest run established

- selected-region profiling around `align` is now validated on successful runs:
  - `out/whisperx-trace/2026-03-30T12-25-36/`
  - `out/whisperx-trace/2026-03-30T12-28-28/`
  - both retained:
    - `profiler_region_start: align`
    - `profiler_region_end: align`
    - `run_end status=ok`
    - non-empty `profiler/whisperx_results.db`
- the main long-file crash run at
  `out/whisperx-trace/2026-03-30T12-38-04/` failed earlier:
  - completed `load_model`
  - completed `load_audio`
  - entered `transcribe`
  - never reached `stage_end:transcribe`
  - never reached `stage_start:align`
- the retained `run.log` tail for that crash ends with:
  - `hipMemcpyWithStream(... hipMemcpyDeviceToHost ...)`
  - host active wait
  - `HW Exception by GPU node-1 ... reason :GPU Hang`
- previous-boot kernel logs for that window show:
  - first reset wave at `2026-03-30 12:39:27`
  - `ring gfx timeout`
  - `GPU reset begin`
  - `BACO reset`
  - `VRAM is lost due to GPU reset`
  - VM fault on `TC4`
  - fresh devcoredump `/var/log/amdgpu-devcoredumps/card1-devcoredump-20260330-123928.bin`
- the `profiler/` directory for that crashy run is empty, but this time that is
  because profiling never reached the selected `align` region, not because the
  selected-region mechanism failed

### Consequence

- the hot boundary for the long file is now earlier than the current
  `align`-selected profiler gate
- a late D2H copy is now the last retained userspace operation before the hang
- that strengthens copy-path suspicion as a candidate subwindow, but does not
  yet promote copy activity to root cause
- the stronger bounded statement is now:
  - copy/wait is the point where the fault becomes visible
  - the first `Host active wait ... for -1 ns` is now the earliest reliable
    pre-crash sentinel on the retained userspace path
  - pinned memory likely sits on the failing DMA path, because fast async D2H
    copy depends on host pages that are pinned and GPU-accessible
  - the leading root-cause class is still lower-level queue progress loss or
    GPU VM / pinned-page failure, not a promoted host-side overflow or
    successful bad-data-delivery story
- the next admissible gate is therefore not "`align`" or "`transcribe`" as a
  fixed label, but "first compute stage reached"
- the current next crash-lane increment is not another gate change; it is
  `first_compute` plus memory-copy trace so the retained `rocpd` bundle can
  distinguish copy-heavy subwindows directly

## 2026-03-30 Copy/wait-adjacent crash tightening

### Current decision

- Do not promote "copy overflow" or "userspace crash copied back from GPU" as
  the current RCA.
- Promote only the narrower statement that D2H copy plus host wait is the
  current exposure point for a deeper GPU-side failure.

### What the latest crash established

- the `first_compute + memory-copy-trace` run at
  `out/whisperx-trace/2026-03-30T14-45-28/`:
  - completed `transcribe`
  - entered `align`
  - then crashed at `2026-03-30 15:27:20`
- the last retained userspace sequence in `run.log` is:
  - late softmax / direct-copy / GEMM activity
  - `hipMemcpyWithStream(... hipMemcpyDeviceToHost, 121916, ...)`
  - `Host active wait for Signal ... for -1 ns`
  - `hipMemcpyWithStream(... hipMemcpyHostToDevice, 812160, ...)`
  - another `Host active wait for Signal ... for -1 ns`
  - `GPU Hang`
- previous-boot kernel evidence for that same window shows:
  - `ring gfx timeout`
  - failed suspend of WhisperX process `pid 81461`
  - BACO reset
  - VRAM loss
  - compositor fallout after reset
- `profiler/` still did not retain structured `rocpd` output across the reset

### Consequence

- the repo can now safely say the crash boundary is copy/wait-adjacent
- the repo can also now safely say the first `-1 ns` host-wait line is the
  earliest reliable pre-crash sentinel on this lane
- the repo should still not say copy is the proven root trigger
- the admissibility split is now:
  - confirmed failure class: `ring gfx timeout` / queue forward-progress failure
  - promoted exposure point: copy/wait-adjacent crash boundary
  - promoted sentinel: first `Host active wait ... for -1 ns`
  - candidate trigger classes:
    - GPU VM or pinned-page failure
    - memory-pressure-driven DMA/copy-path stall
  - candidate ownership hypothesis:
    - ROCm/amdgpu path on `gfx803` / Polaris under mixed compute and copy load
- pinned host memory remains on the suspect surface because DMA likely depends
  on it here, but the current logs fit stalled completion much better than
  "bad payload copied back successfully, then userspace crashed"
- the leading root-cause classes remain:
  - GPU VM or pinned-page failure
  - memory-pressure-driven copy-path instability
  - with queue/ring timeout now treated as the observed failure class above them

### Minimal next matrix

- Run A: current long-file baseline
  - `first_compute + memory-copy-trace`
- Run B: lower memory pressure
  - shorter slice or shorter input that still reaches the compute path
- Run C: same long input, same lane, but no memory-copy trace
  - proxy for lower copy-path perturbation
- Run D: same long input and lane, but alternate compute type if supported
  - for example `float16` or `float32`

Interpretation:

- observed failure class is already fixed higher in the stack:
  - `ring gfx timeout` / queue forward-progress failure
- B improves a lot:
  - VM / mapping pressure gets stronger as the trigger
- C improves a lot:
  - DMA / copy-path sensitivity gets stronger as the trigger
- D alone changes outcome:
  - library/kernel-path bug gets stronger as the ownership hypothesis
- all fail similarly:
  - deeper ROCm/amdgpu infrastructure failure on `gfx803` / Polaris remains the
    best umbrella ownership class

### Patch-shape map for the current failure ladder

Current chain:

- late compute tail
- D2H `hipMemcpyWithStream(...)`
- first `Host active wait ... for -1 ns`
- short delay
- `ring gfx timeout`
- reset / VRAM-loss / artifact wave

Current patch-shape families and expected sentinel movement:

- VM / mapping-pressure reduction
  - chunk input
  - reuse allocations and reduce churn
  - reduce peak VRAM footprint
  - expected movement:
    - first `-1 ns` appears later or disappears
    - timeout becomes more input-length or pressure dependent
- queue visibility / drain points
  - `HIP_LAUNCH_BLOCKING=1`
  - explicit sync fences at heavy phase boundaries if the surface allows them
  - expected movement:
    - failure surfaces earlier and more cleanly
    - `-1 ns` may move earlier or give way to a clearer earlier boundary
- DMA / D2H completion-path relief
  - memory-copy trace off as a perturbation check
  - smaller or staged D2H copies if that path becomes editable
  - dedicated copy stream if the workload ever exposes that control
  - expected movement:
    - `-1 ns` shifts or disappears
    - timeout becomes less deterministic or less frequent if D2H pressure was
      the active trigger
- backend / kernel-path substitution
  - alternate compute type
  - alternate library/kernel mix where available
  - expected movement:
    - binary outcome shift across compute paths
    - ownership hypothesis moves toward a narrower ROCm/library path
- display isolation
  - lower compositor churn or TTY comparison
  - expected movement:
    - artifact presentation may reduce
    - underlying timeout may still remain, which keeps compositor fallout
      secondary

The repo should treat these as patch-shape families, not yet as promoted fixes.
The active goal is to see which family moves the two live sentinels:

- first `Host active wait ... for -1 ns`
- `ring gfx timeout`

Concrete tool mapping for those families is now documented too:

- runtime/env:
  - `HIP_LAUNCH_BLOCKING=1`
  - shorter or chunked input
  - alternate compute type
  - memory-copy trace off
- API-level patterns if the workload path becomes editable:
  - sync fences
  - event timing
  - pinned-buffer reuse
  - chunked D2H
  - dedicated copy stream
- kernel/driver:
  - `amdgpu.lockup_timeout=...`
  - `amdgpu.gpu_recovery=1`
  - previous-boot kernel logs

The repo should keep these as mitigation/tooling patterns, not as proof that
gfx803 with modern ROCm has already "solved" the underlying root cause.

### Current lane matrix

The doc matrix now centers on five implementation lanes:

1. Baseline crash lane (`first_compute + memory-copy trace`)
2. Queue/visibility lane (`HIP_LAUNCH_BLOCKING=1`, syncs)
3. Pressure-control lane (smaller segments, `batch_size=1`)
4. DMA-light lane (copy trace off, staged transfers)
5. Backend lane (alternate compute type / kernel mix)

Each lane produces the same `-1 ns` / timeout / segment metadata records before its mitigations are promoted.

### Pressure-model tightening

The newer stability signal sharpens the trigger model further:

- long files are not dangerous merely because total duration is long
- the better predictor is effective live pressure during Whisper / WhisperX
  segment processing
- the current best control surface is:
  - segment size
  - batch size
  - hidden or explicit concurrency
  - overlap / retained intermediate state

Working model:

- long file
- many segment windows
- enough per-segment footprint and concurrent live state
- D2H copy reaches the unstable boundary
- first `-1 ns`
- `ring gfx timeout`

Important correction:

- "fewer segments" is not automatically safer
- smaller segments can be safer even if there are more of them, if they keep
  the peak live working set below the failure threshold

So the current pressure model is:

- file length is a proxy
- segment size is a stronger direct control
- effective pressure is closer to:
  - segment size × batch size × concurrency

This makes the next pressure-focused patch shapes more specific:

- force smaller segment windows
- keep `batch_size=1`
- reduce concurrent segment processing
- flush and release intermediate state between segments where possible

## 2026-03-30 WhisperX profiler-vs-no-prof split

### Current decision

- Treat the profiler-attached WhisperX lane and the no-profiler WhisperX lane as
  distinct admissibility surfaces.
- The no-profiler lane is the crash-boundary lane.
- The `rocprofv3` lane is now a real observability lane, but it is also a
  timing/pressure confounder because it can let the same reduced workload
  finish.

### What the latest pair established

- no-profiler reduced `stage=align` run:
  - completed `load_model`
  - completed `load_audio`
  - completed `transcribe`
  - entered `align`
  - then retained `GPU Hang`
- previous-boot kernel logs for that window show:
  - `ring gfx timeout`
  - `GPU reset begin`
  - `BACO reset`
  - `VRAM is lost due to GPU reset`
  - repeated soft-recovered `ring gfx timeout` lines after the first reset
- `/var/log/amdgpu-devcoredumps/card1-devcoredump-20260330-011329.bin` matches
  that no-profiler failure window
- profiler-attached reduced run:
  - completed `transcribe`
  - completed `align`
  - wrote real `rocprofv3` artifacts under `profiler/`
  - later hit a teardown `SIGSEGV` in `librocprofiler-sdk.so.1.1.0`
  - late successful `align` is dominated by Tensile / rocBLAS GEMM families plus
    pointwise kernels like layer norm, GELU, direct copy, add, and final softmax
  - the current `whisperx_marker_api_trace.csv` does not expose the expected
    harness `stage_*` ROCTX labels, so stage-to-kernel attribution is still
    weaker than intended

### Consequence

- the strongest current no-profiler retained boundary is now later than the
  March 27 note:
  - `transcribe` completed
  - `align` started
  - then the GPU hang/reset class landed
- `rocprofv3` is now promoted from "candidate profiler path" to "working
  profiler evidence path with its own teardown bug"
- compositor/redraw and memory-pressure ideas remain hypotheses until the
  profiler traces are correlated with the reset boundary

## 2026-03-27 WhisperX RCA note

### Current decision

- Keep WhisperX RCA local to this repo.
- Use `zkperf` only as a pattern source for stage comparison, artifact collation, and run orchestration.
- Do not adopt `zkperf` scripts directly for this lane because they are `perf`/`strace` oriented and not aware of ROCm, `amdgpu` resets, or `devcoredump` capture.
- Treat host CPU saturation as a first-class RCA signal alongside GPU resets.

### What the current live runs established

- the current `rocprof` path is still blocked by a host/runtime `libstdc++` ABI mismatch:
  - `CXXABI_1.3.15` required by `/opt/rocm/lib/libroctracer64.so.4`
- the retained-bundle logic now correctly discards those profiler-startup failures instead of misclassifying them as GPU wedges
- when the user could not tell which process was burning CPU, a host-side process snapshot showed:
  - `ffmpeg` decoding the `MP4` was the main CPU hotspot
  - the WhisperX harness Python process was the secondary hotspot
- the RCA lane therefore needs host CPU snapshots in each retained bundle so CPU-only preprocessing is not mistaken for GPU-stage failure

## 2026-03-29 GPU execution-path admissibility note

### Current decision

- Treat admissibility below the app-stage layer as a literal GPU execution-path question.
- The safe object is not just `WhisperX transcribe` or `Ollama decode`; it is the path through pinned host pages, HSA queues, GPU VM mappings, kernel families, rings, and reset behavior.
- Keep desktop redraw, `alt-tab`, and compositor activity labeled as trigger or aggravation hypotheses, not as promoted root-cause claims.

### Current failure ladder

- userspace Python workload allocates tensors and ROCm-managed buffers
- host page pinning or GPU VM mapping pressure rises
- queue or kernel progress degrades
- `amdgpu` reports VM faults, `init_user_pages` failure, or ring timeout
- reset begins, VRAM can be lost, and display corruption becomes visible collateral

### Current evidence status

- `init_user_pages: Failed to get user pages: -1` is lower-level pinning or mapping failure evidence, not evidence that Python GC recovered anything
- Python GC can change host object lifetime, but it does not explain ring timeout, GPU reset, or VRAM loss
- the repo should distinguish:
  - app-stage admissibility
  - GPU execution-path admissibility
  - reset-correlation evidence

## 2026-03-22

### Current decision

- The maintainable target is a reproducible Nix-owned `gfx803` stack, not permanent dependence on the historical Docker rebuilds.
- The first build boundary is PyTorch, not Ollama.
- The control lane must stay untouched:
  - frozen extracted `6.4` Python/framework layer
  - known-working selected runtime/math layer
- The upgrade lane must initially keep that same frozen Python/framework layer and vary only the ROCm/runtime side underneath it.

### What the recent ROCm-upgrade mapping established

- A fully synced latest-class userspace is not the first practical upgrade shell for Polaris:
  - pure extracted latest imports `torch 2.10.0+rocm7.2.0.gitb6ee5fde`
  - `torch.cuda.is_available()` is still `False`
  - a fully synced `6.4`-upgrade lane reaches the same GPU-gated state
- The first meaningful upgrade boundary with the frozen framework is smaller:
  - upgraded `libamd_comgr`
  - upgraded `librocm-core`
  - upgraded `libelf`
  - upgraded `libnuma`
  - upgraded `libdrm`
  - upgraded `libdrm_amdgpu`
  - upgraded `libdrm_radeon`
- That `safe-support` set preserves:
  - frozen extracted torch import
  - `torch.cuda.is_available() == True`
- The real ABI boundary is the HIP/HSA jump:
  - upgrading `libamdhip64`, `libhsa-runtime64`, `libhiprtc`, or libs that pull them in tends to either hide the GPU or break import on the frozen framework
- The newer framework rebuild work has now separated packaging bugs from runtime bugs:
  - the rebuilt torch wheel imports with the correct wheel-local `libtorch_*` libraries once the rebuild driver keeps `torch/lib` ahead of system `/usr/lib`
  - missing-library churn was a rebuild-driver/runtime-path problem and is now mostly automated away
  - the active blocker is now raw Polaris runtime compatibility under the latest-class ROCm line, not generic `.so` discovery

### Active migration shape

- `gfx803-pytorch-stack`:
  - control shell
  - frozen framework
  - control libs
- `gfx803-pytorch-stack-upgrade`:
  - first accepted upgrade shell
  - frozen framework
  - safe-support upgraded libs only
- Full latest-class userspace remains a separate experiment lane, not the default upgrade shell.
- The primary short-term upgrade lane is now `artifacts/rocm64-upgrade-oldabi/`, which preserves the old HSA/HIP ABI, upgrades only selected low-risk support libs around it, and now carries explicit newer-soname compatibility aliases for the runtime load path.

### 2026-03-25 framework rebuild result

- The old-ABI PyTorch framework rebuild now completes successfully in `artifacts/pytorch-framework-rebuild-oldabi-kinetooff/work/pytorch/`.
- The final install target reached `work/pytorch/torch/` after the following compatibility fixes:
  - redirected ccache to a writable workspace directory instead of the read-only default cache
  - added the ROCm include root to `c10_hip`
  - added a fallback for `__AMDGCN_WAVEFRONT_SIZE` in the ROCm HIP headers used by gfx803
  - gated hipBLASLt outer-vector scale-mode calls on actual header symbol availability
- The build still emits non-fatal warnings, including `-Wno-duplicate-decl-specifier` being ignored by GCC for C++ and several existing PyTorch/ROCm deprecation warnings, but they no longer block install.
- The current result is a working rebuilt framework tree, not just a partial compile graph.
- A direct runtime smoke against `libtorch_python.so` initially exposed the old/new ROCm seam: with a fully constrained old-ABI library path, the load failed on missing newer sonames such as `libhipblas.so.3`; with the host `/opt/rocm/lib` in play, it could pull in latest-class `libamdhip64.so.7` and hit the ROCR symbol mismatch again.
- Reproducible compatibility symlinks in `artifacts/rocm64-upgrade-oldabi/lib-compat` close that seam for direct loading:
  - `libamdhip64.so.7 -> libamdhip64.so.6`
  - `libhipblas.so.3 -> libhipblas.so.2`
  - `libhipsparse.so.4 -> libhipsparse.so.1`
  - `librocblas.so.5 -> librocblas.so.4`
  - `libhipblaslt.so.1 -> libhipblaslt.so.0`
  - `libhipsolver.so.1 -> libhipsolver.so.0`
- With those aliases in place, `ctypes.CDLL(libtorch_python.so)` now succeeds on the preserved old-ABI lane without borrowing `/opt/rocm/lib`.
- The remaining runtime verification target is a clean `import torch` smoke from an isolated wrapper path that exposes only the built `torch` package and its compiled `_C` extension, not the whole source root that shadows stdlib modules.
- A non-building wrapper probe still fails because the current tree exposes `libtorch_python.so` but not a packaged `torch._C` extension module that `torch.__init__` can import directly.
- The intended import smoke path is now a tiny targeted compile of `torch/csrc/stub.c` into the wrapper so `torch._C` can resolve without rerunning the full PyTorch packaging workflow.
- That isolated wrapper smoke now succeeds when the wrapper includes both the compiled `torch._C` stub loader and the `torchgen` package from the source tree; this keeps stdlib shadowing out of the import path while staying far cheaper than `setup.py develop`.
- The smoke helper now captures stderr and only prints the success lines from `import torch`, so the runtime verification output stays clean even if the underlying loader emits harmless ROCm path noise.

### Next technical target

- The first full old-HIP/newer-math import sweep is now complete on top of the safe-support base.
- The coarse-pass `green` profiles turned out not to be real newer-math wins:
  - `rocblas_only`
  - `hipblas_only`
  - `hipblaslt_only`
  - `hipsparse_only`
  - `hipsolver_only`
  - `rocblas_bundle`
- Loader-resolution and hash checks showed why:
  - the frozen framework still requests the old sonames:
    - `librocblas.so.4`
    - `libhipblas.so.2`
    - `libhipblaslt.so.0`
    - `libhipsparse.so.1`
    - `libhipsolver.so.0`
  - the extracted latest lane provides newer sonames instead:
    - `librocblas.so.5`
    - `libhipblas.so.3`
    - `libhipblaslt.so.1`
    - `libhipsparse.so.4`
    - `libhipsolver.so.1`
  - so the coarse-pass profiles kept binding the control `6.4` math binaries, not newer ones
- The current real newer-lib overlays that were actually exercised are the ones with compatible sonames:
  - `miopen_only` used the newer `libMIOpen.so.1` payload and failed at the newer HIP ABI seam
  - `rocsolver_only` used the newer `librocsolver.so.0` payload and failed at the newer HIP ABI seam
  - `rocsparse_only` likewise fails at that seam
- The runtime bring-up work under the rebuilt framework lane established a sharper split:
  - full latest-class userspace causes `rocminfo` to fail with `HSA_STATUS_ERROR`
  - swapping only latest `libhsa-runtime64` onto the working base is enough to trigger that failure
  - swapping only latest HIP userspace is not enough to trigger that failure
  - restoring an old HSA-side cluster on top of the latest userspace can make `rocminfo` enumerate `gfx803` again
  - debugger-side follow-up should use `mcp-gdb` or plain `gdb` for `rocminfo` userspace call-path inspection; `rocprofv3` is for GPU execution-path attribution, not for replacing a userspace debugger
  - the first debugger-backed artifact is now retained at `out/rocminfo-gdb/2026-03-29T21-59-30/gdb-hsa-flow.txt`
  - on that failing latest-HSA surface, `hsa_init()` returns `4096` and `hsa_iterate_agents` is not reached
  - but rebuilt torch still fails there because latest `libamdhip64.so.7` expects newer ROCR/HSA symbols (`hsa_amd_memory_get_preferred_copy_engine@ROCR_1`)
- The active seam is therefore:
  - latest HSA breaks Polaris enumeration
  - old HSA restores enumeration
  - latest HIP requires newer HSA symbols
- The current reproducible hybrid runtime probes are:
  - `oldhsa_oldaql`
  - `oldhsa_oldprof`
  - `oldhsa_fullcluster`
- Those hybrid lanes are diagnostic only:
  - `rocminfo` works there
  - rebuilt latest-class torch does not
- The old-ABI preserved lane is now the primary short-term build target for the flake upgrade shell and the framework rebuild driver.
- The first old-ABI-targeted framework smoke was still not trustworthy because the rebuild toolchain/runtime leaked `/opt/rocm` latest sonames:
  - `torch.cuda.is_available() == False`
  - `ldd` showed `libamdhip64.so.7`, `librocblas.so.5`, and related latest-class libs resolving from `/opt/rocm/lib`
  - so the next concrete fix is a coherent extracted old-ABI ROCm SDK root plus a rebuild-driver guard that rejects that leakage
- The rebuild driver now starts from a clean `LD_LIBRARY_PATH` built from the intended old-ABI roots only, so the next smoke should no longer inherit `/opt/rocm` from the caller environment.
- The next build failure on the old-ABI lane came from Kineto / `roctracer` headers, so the rebuild driver should disable `USE_KINETO` for this lane rather than trying to compile profiling support from the extracted SDK.
- After disabling Kineto, the next old-ABI lane failure moved into HIP-generated CUB objects under libstdc++ 15:
  - `torch_hip_generated_cub.hip.o`
  - `torch_hip_generated_cub-RadixSortPairs.hip.o`
  - the failure is `std::array` hitting `__glibcxx_assert_fail` in `__host__ __device__` code
  - the first `_GLIBCXX_ASSERTIONS` workaround only reached top-level `CXX flags`
  - the generated HIP compile commands did not carry it into `HIP_CLANG_FLAGS`
  - the workaround is now injected through `HIPFLAGS` and CMake configuration arguments
  - the next failure moved to the ROCm LLVM toolchain itself: bundled `lld` cannot load `libxml2.so.2`
  - the rebuild driver now prepends a host `libxml2` provider before rerunning
  - a later live run showed the first `CMAKE_HIP_FLAGS` env injection was malformed at the cmake command line, so the driver now passes it through `CMAKE_ARGS` as a single escaped value
- The next practical migration target is no longer `latest HIP on gfx803`. It is:
  - preserve the old HSA/HIP ABI while upgrading around it where possible, or
  - patch the newer HSA/HIP line itself before expecting a latest-class framework lane to work

### User goal driving this

- Reach a state soon where the machine can be left to churn on the next meaningful long-running work, ideally recompiles or larger compatibility probes, without risking the known-working control lane.

## 2026-03-30 Blocking lane summary-only success

### Current decision

- Promote `HIP_LAUNCH_BLOCKING=1` to the first practical stabilizing lever for
  the long WhisperX repro file.
- Keep the claim bounded to summary-level success until one kept successful
  trace bundle exists.

### What the latest matrix run established

- the named `blocking` lane at
  `out/whisperx-rca-matrix/2026-03-30T16-45-56/summary.csv` reports:
  - `lane=blocking`
  - `hip_launch_blocking=1`
  - `memory_copy_trace=1`
  - `exit_code=0`
  - `kept_bundle=0`
  - empty `last_trace_dir`
- because `kept_bundle=0`, there is no retained `run.log`, `events.jsonl`, or
  `whisperx_results.db` bundle for post-hoc inspection on that successful run
- that makes the result admissible as:
  - stronger than the crashing non-blocking lanes
  - weaker than a kept-bundle success

### Consequence

- `HIP_LAUNCH_BLOCKING=1` is now the first lane that appears to convert the
  long-file repro from crash to success on this host
- this materially strengthens queue / async progression as a practical
  stabilizing lever
- it does not yet displace GPU VM / page-mapping fault as the leading trigger
  class for the non-blocking lanes
- the next required follow-up is narrow:
  - rerun the same `blocking` lane with `KEEP_SUCCESS_TRACE=1`
  - retain the successful bundle
  - then inspect whether the first `-1 ns` wait and explicit page fault are
    absent rather than merely unobserved in a summary-only success

### Normal WhisperX path split

- the plain `gfx803_flake_v1` `.#whisperx` path is now separated from the
  earlier RCA hang lane
- a short-file non-RCA run with:
  - `HIP_LAUNCH_BLOCKING=1`
  - `batch_size=1`
  - `chunk_size=10`
  - `vad_method=silero`
  still failed before normal transcription with:
  - `/nix/store/...-rocm-device-libs-22.0.0-rocm/.../opencl.bc`
  - `Unknown attribute kind (102) (Producer: 'LLVM22.0.0' Reader: 'LLVM 19.0.0git')`
  - `Couldn't create blit kernels!`
  - then host-side `Segmentation fault`
- this means the `.#whisperx` shell was leaking Nix ROCm device-libs into the
  extracted host runtime
- the correct next step for that path is shell/runtime isolation, not more
  WhisperX RCA theorizing
- once that shell/runtime mixing was tightened, the next short-file normal-path
  failure moved further:
  - `--vad_method silero` now reaches WhisperX startup but fails in
    `torch.hub.load("snakers4/silero-vad", ...)`
  - the retained error is Python SSL / trust failure followed by
    "repo could not be found in the cache"
- so the next normal-path stabilization step is not more GPU tuning; it is a
  local `torch.hub` cache bootstrap for Silero under a repo-local `TORCH_HOME`
