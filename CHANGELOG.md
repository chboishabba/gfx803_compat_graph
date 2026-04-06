# Changelog

## 2026-03-30

- added a reduced WhisperX crash-capture mode to the `rocprofv3` wrapper so crashy runs can prefer marker trace plus kernel trace with CSV-only output instead of the heavier default trace set
- added a lightweight `heartbeat.log` side channel to the WhisperX trace bundle so current stage, profiler mode, and any already-materialized profiler filenames are flushed periodically even when the host resets before profiler finalize
- extended the crash-capture path so crashy runs can switch `rocprofv3` to `rocpd` output and add `--collection-period` without editing the wrapper directly
- added a stronger `observer.log` stream to the WhisperX trace bundle that periodically snapshots the tail of `run.log`, the tail of `events.jsonl`, current profiler filenames and sizes, and the current-boot kernel tail
- taught the WhisperX harness to call `roctxProfilerResume/Pause` around a selected stage and taught the wrapper to enable `rocprofv3 --selected-regions`, so the next heavy run can start collection when `align` begins instead of using a fixed start delay
- recorded the follow-up selected-region results more accurately:
  - `align`-selected profiling now works and retains `whisperx_results.db` on shorter successful runs
  - the main long-file crash at `out/whisperx-trace/2026-03-30T12-38-04/` died earlier during `transcribe`, before the selected `align` region began
  - the retained `run.log` there ends with `hipMemcpyWithStream(... hipMemcpyDeviceToHost ...)`, host active wait, then `GPU Hang`
  - the matching reset wave starts at `2026-03-30 12:39:27` with BACO reset, VRAM loss, and a VM fault on `TC4`
- replaced the “pick one exact stage” assumption with a stage-policy surface:
  - the harness now supports `--profile-stage-policy exact|first_compute`
  - the wrapper now forwards `WHISPERX_PROFILE_STAGE_POLICY`
  - `first_compute` latches profiling on at the first compute stage reached and keeps it active through the rest of the run
  - exact-stage selection remains available for comparison runs
- extended the WhisperX `rocprofv3` wrapper with `WHISPERX_ROCPROFV3_ENABLE_MEMORY_COPY_TRACE=1` so the primary `first_compute` crash lane can retain memory-copy activity in the same `rocpd` bundle when the copy-path hypothesis is being tested
- recorded the later `2026-03-30T14-45-28` `first_compute + memory-copy-trace` crash more tightly:
  - `transcribe` completed
  - `align` started
  - the final retained userspace sequence is D2H copy, `Host active wait ... for -1 ns`, H2D copy setup, another `-1 ns` wait, then `GPU Hang`
  - previous-boot kernel logs at `15:27:20` show gfx ring timeout, failed suspend of the WhisperX process, BACO reset, and VRAM loss
  - repo wording is now tightened to "copy/wait exposure point" rather than a promoted copy-overflow root-cause claim
- updated the admissibility lattice and repo-facing RCA wording to split:
  - promoted exposure point: copy/wait-adjacent crash boundary
  - candidate root-cause classes: queue-progress loss, GPU VM/pinned-page failure, or DMA/copy-path stall
  - not promoted: copy overflow or host-only userspace crash as the primary RCA
- tightened the pinned-memory wording across repo docs:
  - pinned host memory remains on the suspect DMA surface
  - but the current evidence fits stalled copy completion much better than successful delivery of bad data into host userspace
- updated the lattice and WhisperX docs again to promote the first
  `Host active wait ... for -1 ns` line as the earliest reliable pre-crash
  sentinel on the retained userspace path
- documented the minimal discriminating 4-run matrix:
  - A baseline
  - B lower memory pressure
  - C memory-copy trace off
  - D alternate compute type if supported
- tightened the layered RCA wording again:
  - confirmed failure class: `ring gfx timeout` / queue forward-progress loss
  - promoted exposure point: copy/wait-adjacent boundary
  - promoted sentinel: first `Host active wait ... for -1 ns`
  - candidate trigger classes: GPU VM/pinned-page failure or DMA/copy-path stall
  - candidate ownership hypothesis: ROCm/amdgpu instability on `gfx803` / Polaris
- expanded [POLARIS_STABILITY_BLUEPRINT.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/POLARIS_STABILITY_BLUEPRINT.md) with a Polaris ROCm sanity checklist for reset-class failures:
  - baseline bring-up
  - known-good stack discipline
  - VRAM / pinned-memory hygiene
  - watchdog and recovery settings
  - queue-sensitivity probe
  - display isolation
  - thermal sanity
  - current `-1 ns` sentinel handling
  - the minimal 4-run discriminator matrix
- extended the RCA docs again so they now carry a remediation / patch-shape layer in addition to the failure lattice:
  - VM / mapping-pressure reduction
  - queue visibility / drain-point insertion
  - DMA / D2H completion-path relief
  - backend / kernel-path substitution
  - display isolation as a secondary aggravator check
  - the docs now state the expected movement of the live sentinels (`Host active wait ... for -1 ns` and `ring gfx timeout`) for each patch-shape family
- added a concrete tool / mitigation matrix on top of those patch-shape families:
  - runtime and environment controls
  - HIP / ROCm API patterns
  - `rocprofv3` / copy-trace usage
  - kernel/driver stabilizers
  - display isolation and version/stack swap surfaces
  - the docs now distinguish "existing mitigation patterns" from "promoted fixes"
- tightened the pressure model across the WhisperX RCA docs:
  - raw file length is now treated as a proxy rather than the main control variable
  - segment size and effective concurrency are now documented as the stronger direct controls
  - the docs now state the practical danger surface as approximately `segment size × batch size × concurrency`
  - smaller segment windows are now documented as a first-class stabilizing test on the same long file
- documented the new five-lane RCA matrix (baseline, queue/visibility, pressure-control, DMA-light, backend) and clarified that promotion happens only when the lane-specific tooling moves the shared sentinels as expected
- recorded the first named `blocking` lane success more carefully:
  - `out/whisperx-rca-matrix/2026-03-30T16-45-56/summary.csv` shows
    `lane=blocking`, `hip_launch_blocking=1`, and `exit_code=0`
  - but `kept_bundle=0`, so this is currently a summary-only success rather
    than a kept-bundle success
  - repo wording now promotes `HIP_LAUNCH_BLOCKING=1` as the first practical
    stabilizing lever for the long-file repro while keeping the next follow-up
    explicit: rerun with `KEEP_SUCCESS_TRACE=1`
- updated the repo-facing policy boundary so this WhisperX result now informs
  adjacent compat work too:
  - use blocking-first defaults for fragile runtime-facing workflows
  - prefer short real workloads over synthetic-only smokes when probing a new
    compat lane
  - keep long async GPU workloads outside promoted baseline claims unless they
    have retained success evidence
- added `docs/WHISPERX_OBSERVABILITY_C4.puml` as the current observability container view for the WhisperX RCA path
- added a new WhisperX incident note for the March 30 split between the no-profiler crash path and the profiler-attached success path
- recorded that the reduced no-profiler WhisperX run now has a stronger retained boundary: `transcribe` completed, `align` started, then the run ended with `GPU Hang` and the matching host reset wave produced `/var/log/amdgpu-devcoredumps/card1-devcoredump-20260330-011329.bin`
- recorded that the reduced `rocprofv3` WhisperX run completed and emitted real profiler artifacts, but `rocprofiler-sdk` later segfaulted during teardown after writing result files
- added a new execution-path claim record for the no-profiler WhisperX `align`-start crash boundary and updated project context/TODO so the next RCA step is explicit kernel/marker correlation against the successful `rocprofv3` bundle
- recorded the first successful-profiler readout too: late `align` is GEMM-heavy with interleaved layer norm / GELU / direct-copy / softmax kernels, but the current `rocprofv3` marker CSV still does not expose the expected harness `stage_*` ROCTX labels
- updated `scripts/whisperx_rca_harness.py` so it now prefers `librocprofiler-sdk-roctx` over legacy `libroctx64` and emits explicit `roctxMarkA` run/stage markers alongside pushed ranges, giving `rocprofv3` a better chance to expose the harness stage labels directly
- verified that marker fix with a light `stage=load` profiler run under `out/whisperx-trace/2026-03-30T07-54-25/`: `whisperx_marker_api_trace.csv` now contains `run_start`, `stage_start:load_model`, `stage_end:load_model`, `whisperx:load_model`, and `run_end:load_model`
- recorded the next heavy profiled `align` crash under `out/whisperx-trace/2026-03-30T08-23-52/`: the run completed `transcribe`, entered `align`, then hit `GPU Hang`; the matching host reset wave starts at `09:40:16`, but the `profiler/` directory stayed empty because `rocprofv3` did not flush outputs before reset

## 2026-03-29

- tightened the WhisperX and GPU-reset wording across docs so the safe current model is explicitly lower-level than a single app stage: pinned-page failure, GPU VM faults, queue stalls, reset behavior, and VRAM loss are now treated as the active RCA ladder
- updated `TODO.md` to stop describing the extracted `6.4` host path as if it already covered WhisperX host stability and to add follow-up work for a GPU execution-path admissibility registry
- documented the RCA tool split more explicitly: `gdb` / `mcp-gdb` for host userspace failures such as `rocminfo` HSA errors, and `rocprofv3` plus kernel/devcoredump evidence for GPU hang/reset attribution
- added a debugger-backed `rocminfo` incident note showing that the failing latest-HSA surface reaches `hsa_init()` and returns `4096` before agent enumeration begins
- added `schemas/execution_path_claim.schema.json` plus the first seed records under `artifacts/execution_path_claims/examples/` so lower-level RCA claims can be attached to userspace-init, GPU VM fault, and reset surfaces without blending evidence classes

## 2026-03-27

- added a structured incident note for the `2026-03-25 21:42:41` Wayland-visible reset sequence and recorded the stronger working model: real `amdgpu` reset instability with `kwin_wayland` as the likely first visible casualty rather than the root cause
- added `scripts/correlate-amdgpu-reset-window.sh` to correlate kernel reset lines, `amdgpu-devcoredump.service` activity, and `/var/log/amdgpu-devcoredumps` files for one time window
- added `scripts/whisperx_rca_harness.py` so WhisperX can be exercised stage-by-stage (`load_model`, `transcribe`, `align`, `diarize`) with structured timing, GPU-memory snapshots, and ROCTX stage markers
- added `scripts/trace-whisperx-rocprof.sh` to run that harness under `rocprof` with HIP/HSA tracing plus the existing devcoredump watcher
- tightened the WhisperX trace wrapper so clean runs are discarded by default and only suspicious runs keep their trace bundle
- taught the WhisperX trace wrapper to classify the current `rocprof` `libstdc++` / `CXXABI_1.3.15` startup failure as a tooling dependency problem instead of a fake GPU wedge
- taught the WhisperX trace wrapper to prefer `rocprofv3` automatically when it is available, while keeping legacy `rocprof` as an explicit backend
- forced system `libstdc++.so.6` when using legacy `rocprof` so the extracted Conda runtime does not break `roctracer` startup with the missing `CXXABI_1.3.15` symbol version
- added `scripts/watch-host-cpu-hotspots.sh` and enabled it from the WhisperX trace wrapper so retained bundles now show when `ffmpeg` or another host process is saturating CPU during RCA runs
- added `scripts/run-whisperx-rca-matrix.sh` with the practical default sweep for this failure class:
  - stages: `align`, `diarize`
  - compute types: `int8`, `float16`
  - `HIP_LAUNCH_BLOCKING=0/1`
  - retain bundles only when the run exits badly, logs a stage error, or captures devcoredump evidence
- updated `README.md` and `docs/USER_GUIDE.md` so the new WhisperX RCA workflow is documented in the same place as the existing crash-capture guidance, including the current decision to use `zkperf` only as a pattern source rather than a direct dependency
- tightened the baseline runtime wording so the extracted `6.4` lane now promotes torch import / ComfyUI / userspace bring-up, while WhisperX is documented separately as a GPU RCA surface that can still hit KFD / reset instability at an unknown point
- added a dedicated incident note for the retained `2026-03-27` WhisperX repro evidence, recording that the run had already entered `transcribe` before the crash boundary and therefore does not justify an `align`-specific blame claim

## 2026-03-25

- completed the old-ABI PyTorch framework rebuild lane under `artifacts/pytorch-framework-rebuild-oldabi-kinetooff/work/pytorch/`
  - redirected ccache to a writable workspace cache so the build could run on this filesystem
  - added the ROCm include root to `c10_hip`
  - added a gfx803-safe fallback for `__AMDGCN_WAVEFRONT_SIZE` in the ROCm HIP headers
  - gated hipBLASLt outer-vector scale-mode calls on installed header symbol availability so the bundled ROCm 7.2.26043-9999 SDK can compile the gfx803 lane cleanly
- the build now reaches install successfully and writes the rebuilt framework tree to `work/pytorch/torch/`
- the remaining compiler output is warning-only; the build no longer stops on the earlier HIP/CUB, hipBLASLt, or ROCm header mismatches
- direct runtime smoke against `libtorch_python.so` still shows the ROCm ABI seam is not fully closed:
  - the preserved old-ABI path resolves the older ROCm sonames cleanly
  - the host `/opt/rocm/lib` path can still leak newer `libamdhip64.so.7` / `libhipblas.so.3` style dependencies into the load graph
  - the rebuild is therefore install-complete, but the final runtime path still needs isolation before it can be treated as a fully importable smoke-passed torch tree
- added reproducible compatibility aliases to `artifacts/rocm64-upgrade-oldabi/lib-compat` so the preserved old-ABI lane can satisfy the newer sonames requested by the rebuilt framework at direct-load time:
  - `libamdhip64.so.7 -> libamdhip64.so.6`
  - `libhipblas.so.3 -> libhipblas.so.2`
  - `libhipsparse.so.4 -> libhipsparse.so.1`
  - `librocblas.so.5 -> librocblas.so.4`
  - `libhipblaslt.so.1 -> libhipblaslt.so.0`
  - `libhipsolver.so.1 -> libhipsolver.so.0`
- verified that `ctypes.CDLL(libtorch_python.so)` now succeeds on the preserved old-ABI lane without borrowing `/opt/rocm/lib`, which closes the direct runtime loading gap that was left after the framework install succeeded
- clarified the remaining runtime verification path so `import torch` should be tested from an isolated wrapper package around the rebuilt `torch` tree, not by pointing Python at the whole source root or by invoking `setup.py develop` (which triggers a rebuild path)
- the non-building wrapper probe still fails because the rebuilt tree does not yet expose a packaged `torch._C` extension module; at present it only provides `libtorch_python.so`, which is enough for direct loading but not enough for a clean `import torch`
- refined the import-smoke workflow to target the tiny `torch/csrc/stub.c` loader that exports `PyInit__C`, so the remaining verification can be done without rerunning the full PyTorch packaging pipeline
- the isolated wrapper smoke now succeeds after compiling the tiny `torch/csrc/stub.c` loader and adding `torchgen` to the wrapper path, which keeps the import path clean without invoking `setup.py develop`
- the smoke helper now captures stderr and prints only the success lines from `import torch`, so the verified path is readable even when the runtime emits harmless ROCm table noise

## 2026-03-22

- tightened the old-ABI framework rebuild direction so it is internally coherent:
  - added `scripts/extract-rocm64-oldabi-sdk.sh` to snapshot `/opt/rocm` from the known-working Robert `6.4.3_0.11.5` image into `artifacts/rocm64-oldabi-sdk/`
  - updated the rebuild docs/TODOs to record that a runtime-lib overlay alone was not enough because the first smoke still leaked latest `/opt/rocm` sonames
  - prepared the repo to require a coherent old-ABI ROCm SDK root for future framework rebuilds
- cleaned the framework rebuild driver so it now rebuilds `LD_LIBRARY_PATH` from the intended old-ABI roots instead of inheriting the caller's `/opt/rocm` entries
- disabled Kineto in the old-ABI torch rebuild lane after the extracted SDK's `roctracer` headers triggered ambiguous `operator<<` compile failures in `libkineto`
- promoted the preserved old-HSA/HIP ABI direction from a documented recommendation into repo wiring:
  - added `scripts/create-rocm64-upgrade-oldabi-lane.sh`
  - added `scripts/host-rocm64-upgrade-oldabi-python.sh`
  - changed `.#gfx803-pytorch-stack-upgrade` to point at that old-ABI lane
  - changed the framework rebuild default runtime from `artifacts/rocm-latest/lib-compat` to `artifacts/rocm64-upgrade-oldabi/lib-compat`
- updated publish defaults so `artifacts/rocm64-upgrade-oldabi/` is included in the standard Cachix artifact set
- updated repo docs/TODOs to make the short-term priority explicit:
  - preserve the old HSA/HIP ABI
  - rebuild above it
  - keep full latest-class HSA/HIP as a separate investigation lane
- updated `COMPACTIFIED_CONTEXT.md`, `README.md`, `docs/NIX_MIGRATION_CHECKLIST.md`, and `TODO.md` to record the current HSA/HIP seam more precisely:
  - latest `libhsa-runtime64` breaks `rocminfo` on Polaris
  - latest HIP userspace alone does not
  - old-HSA hybrid lanes can restore `rocminfo`
  - rebuilt latest-class torch still fails there because latest `libamdhip64.so.7` expects newer ROCR/HSA symbols than the restored old HSA runtime exports
- recorded the rebuild-driver/runtime-path progress more accurately:
  - missing-library churn is now mostly automated through `ldd`-driven runtime path discovery
  - the rebuilt wheel now binds its own `torch/lib` copies ahead of system `libtorch_*`
  - the active blocker is now runtime compatibility on Polaris, not generic import-path noise
- added `scripts/create-rocm-latest-hsa-hybrid-lanes.sh` to materialize the current latest-userspace/old-HSA hybrid probe lanes under `artifacts/rocm-runtime-hybrids/`
- added `scripts/probe-rocm-hybrid-runtime-lanes.sh` to run reproducible `rocminfo` and rebuilt-torch checks against those hybrid runtime lanes

- added `COMPACTIFIED_CONTEXT.md` to record the current migration decision plainly: frozen control lane, curated safe-support upgrade lane, full latest-class lane kept separate, and the HIP/HSA ABI jump identified as the next real boundary
- updated `README.md`, `docs/NIX_MIGRATION_CHECKLIST.md`, `gfx803_flake_v1/README.md`, and `TODO.md` so the repo now consistently describes the safe-support lane as the first real upgrade target and the full latest-class lane as a separate negative-control experiment
- recorded the next explicit fallback rule: if the first Nix-owned framework rebuild driver blocks badly, fall back later to the Robert/Docker extraction or rebuild path rather than losing the working artifact lineage
- added `scripts/run-gfx803-pytorch-framework-rebuild.sh` as the first Nix-owned framework rebuild driver targeting `torch`, `torchvision`, and `torchaudio` against the extracted latest compat lane
- exposed that driver in `gfx803_flake_v1` as:
  - app: `.#framework-rebuild`
  - package: `.#run-gfx803-pytorch-framework-rebuild`
  - shell: `.#gfx803-pytorch-framework-rebuild`
- validated the new entrypoint narrowly:
  - `nix flake show ./gfx803_flake_v1 --no-write-lock-file`
  - `nix run ./gfx803_flake_v1#framework-rebuild -- --help`
- recorded the first concrete rebuild failure from that driver:
  - PyTorch stopped in `third_party/fbgemm/src/UtilsAvx512.cc`
  - `-Werror=maybe-uninitialized`
- updated the framework rebuild driver to carry the conservative PyTorch build flags from the later Docker attempts:
  - `BUILD_TEST=0`
  - `USE_NNPACK=0`
  - `USE_TENSORPIPE=0`
  - `USE_DISTRIBUTED=0`
  - `USE_RPC=0`
  - `USE_SYSTEM_PROTOBUF=1`
  - `BUILD_CUSTOM_PROTOBUF=OFF`
  - `CXXFLAGS=-Wno-error=maybe-uninitialized`
- recorded the next concrete rebuild-stage blocker after the torch wheel succeeded:
  - `torchvision` failed while importing the freshly built torch wheel
  - `OSError: libgomp.so.1: cannot open shared object file`
- updated the framework rebuild driver so it now:
  - prepends a `libgomp` directory when available
  - runs a torch-only smoke gate after installing the built torch wheel
  - records `torch.__version__` and `torch.cuda.is_available()`
  - stops before `torchvision` if that smoke gate fails
- updated the framework rebuild driver to reuse an existing torch wheel from `dist/` by default, so later-stage reruns can jump straight to the torch smoke gate and `torchvision` instead of rebuilding torch every time
- updated the framework rebuild driver again so it now auto-discovers missing runtime `.so` dependencies for the installed torch wheel from known compat/system roots before the torch smoke gate runs, instead of patching one missing library at a time
- added a `--torch-smoke-only` mode so the reused-wheel path can be validated without immediately continuing into a longer `torchvision` build
- added `scripts/create-rocm64-upgrade-safe-support-lane.sh` to build `artifacts/rocm64-upgrade-safe-support/` from the control `6.4` lane plus only the upgraded low-risk support libs
- added `scripts/host-rocm64-upgrade-safe-support-python.sh` so the first accepted upgrade lane has its own explicit runner
- added `scripts/probe-rocm64-oldhip-math-subsets.sh` so newer math families can be overlaid one profile at a time on top of the old-HIP safe-support base
- updated `gfx803_flake_v1/flake.nix` so `.#gfx803-pytorch-stack-upgrade` now points at the curated safe-support lane instead of the broader full-sync experiment
- updated `scripts/publish-ollama-and-extracted-artifacts-to-cachix.sh` so the safe-support lane is included in the default artifact publication set
- validated the new safe-support lane end to end:
  - `bash scripts/create-rocm64-upgrade-safe-support-lane.sh`
  - `bash scripts/host-rocm64-upgrade-safe-support-python.sh -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'`
  - result: `torch 2.6.0+gitdae14f9`, `torch.cuda.is_available() == True`
- exercised the first two math-subset profiles on top of that safe-support base:
  - `rocblas_bundle` still imports and reports `torch.cuda.is_available() == True`
  - `miopen_only` still crosses the newer HIP ABI boundary and fails on `/opt/rocm/lib/libamdhip64.so.7` / `ROCR_1`
- completed the first full old-HIP/newer-math import sweep on top of the safe-support base:
  - coarse-pass at import/GPU-visibility level:
    - `rocblas_only`
    - `hipblas_only`
    - `hipblaslt_only`
    - `hipsparse_only`
    - `hipsolver_only`
    - `rocblas_bundle`
  - current hard ABI-seam failures:
    - `miopen_only`
    - `rocsparse_only`
    - `rocsolver_only`
- completed loader-resolution and hash checks for the coarse-pass profiles and confirmed they were false positives:
  - the frozen framework still requests the old control sonames such as `librocblas.so.4`, `libhipblas.so.2`, `libhipblaslt.so.0`, `libhipsparse.so.1`, and `libhipsolver.so.0`
  - the extracted latest lane exposes newer sonames such as `librocblas.so.5`, `libhipblas.so.3`, `libhipblaslt.so.1`, `libhipsparse.so.4`, and `libhipsolver.so.1`
  - so those profiles kept binding the control `6.4` math binaries rather than genuinely switching to newer math code
- confirmed that the actual newer-soname overlays that do bind under matching names (`libMIOpen.so.1`, `librocsolver.so.0`) fail at the newer HIP ABI seam instead
- tightened `docs/NIX_MIGRATION_CHECKLIST.md` so the migration order is now explicit: start with the shared gfx803 PyTorch stack and defer Ollama until after that boundary is working
- classified the Docker-era workarounds in the checklist into:
  - PyTorch-essential derivation inputs
  - historical Docker transport details that should stay documentation-only for now
- added `scripts/host-rocm64-upgrade-frozen-python.sh` so the upgrade lane can keep the frozen control Python/framework set while swapping only the ROCm/runtime side underneath it
- exposed two explicit flake shells in `gfx803_flake_v1/flake.nix`:
  - `.#gfx803-pytorch-stack`
  - `.#gfx803-pytorch-stack-upgrade`
- validated the new shell split:
  - the control framework still imports as `torch 2.6.0+gitdae14f9` with `torch.cuda.is_available() == True`
  - the upgrade runner currently stops at a real ABI boundary because the frozen framework expects `libamdhip64.so.6`
- updated `README.md`, `gfx803_flake_v1/README.md`, `docs/NIX_MIGRATION_CHECKLIST.md`, and `TODO.md` to match that PyTorch-first migration decision and the current ABI-boundary result
- added [docs/NIX_MIGRATION_CHECKLIST.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/NIX_MIGRATION_CHECKLIST.md) to translate the original working gfx803 Docker recipe into a Nix migration plan with three explicit outputs:
  - the exact working ingredients to preserve
  - the split between essential gfx803 requirements and historical Docker workarounds
  - the target mapping into runtime, support-lib, math-lib, framework, and app layers
- updated `README.md`, `TODO.md`, and `gfx803_flake_v1/README.md` so the repo now points directly at that migration checklist instead of treating the historical Docker line as an implicit source of truth
- added `scripts/clone-rocm64-upgrade-lane.sh` to create a reproducible `6.4`-derived upgrade lane under `artifacts/rocm64-upgrade/` instead of mutating the extracted `6.4` control in place
- added `scripts/host-rocm64-upgrade-python.sh` so the cloned lane has an explicit runner separate from the control `6.4` host wrapper
- added `scripts/capture-leech-minimal-repros.sh` to freeze the current minimal Leech repro matrix for any lane using a consistent output layout and labels
- added `scripts/swap-rocm64-upgrade-python-from-latest.sh` so the first planned Python/PyTorch swap from the extracted `latest` lane is an explicit reproducible step rather than a manual copy
- added `scripts/swap-rocm64-upgrade-support-libs-from-latest.sh`, `scripts/swap-rocm64-upgrade-math-libs-from-latest.sh`, and `scripts/sync-rocm64-upgrade-lib-compat-from-latest.sh` so the upgrade lane can absorb newer ROCm userspace in the same staged order used during this bring-up
- updated `scripts/publish-ollama-and-extracted-artifacts-to-cachix.sh` so `artifacts/rocm64-upgrade/` is part of the default artifact publication set
- cloned the current extracted `6.4` runtime into `artifacts/rocm64-upgrade/` and confirmed that the dedicated runner imports `torch 2.6.0+gitdae14f9` and reports `torch.cuda.is_available() == True`
- captured the first frozen minimal repro bundles for both the `6.4` control lane and the cloned `6.4`-upgrade lane:
  - `out/leech-min-repros/rocm64-upgrade/2026-03-22T13-01-09`
  - `out/leech-min-repros/rocm64-control/2026-03-22T13-02-21`
- fixed the latest extraction path for `rocm/pytorch:latest` by teaching the generic artifact extractor to pull `/opt/venv` in addition to the older `ComfyUI/venv` and `/opt/conda` layouts
- updated the latest and upgrade host runners so venv-based extracted runtimes do not incorrectly set `PYTHONHOME`, which had been breaking Python startup
- confirmed that the pure extracted latest lane now imports `torch 2.10.0+rocm7.2.0.gitb6ee5fde`, but it reports `torch.cuda.is_available() == False` on this Polaris host
- exercised the first full `6.4`-upgrade swap sequence:
  - latest Python on top of old `6.4` libs failed on missing `ROCR_1` symbols from `libamdhip64`
  - adding newer non-math support libs moved the import failure into the sparse math stack
  - adding newer math libs and then syncing the full latest `lib-compat` removed import-time linker failures
  - final result still matched pure latest: torch imports, but `torch.cuda.is_available() == False`
- updated `README.md`, `docs/USER_GUIDE.md`, and `TODO.md` to describe the `6.4`-upgrade lane as the preferred reproducible path toward newer ROCm components on `gfx803`, with pure `ROCm latest` extraction treated as a component source rather than the primary runtime target

## 2026-03-21

- narrowed the `5.7` Leech repro further: the finer attention probe now shows stable `attn_probs`, stable `attn_weighted`, unstable `block0.attn_out_preproj_view`, and stable `permute(...).contiguous().reshape(...)` on the same tensor path
- updated the public docs and TODOs to reflect that more precise upstream-facing finding instead of the older `block3.attn_out_preproj` approximation
- tested the corresponding `permute(...).contiguous().reshape(...)` workaround in the real `LeechAttention` forward path and confirmed that it is not a sufficient end-to-end fix: repeated `5.7` first-step logits still drift across identical runs
- aligned the layerwise probe with the patched model path and found that, once the stable flatten path is used downstream, the remaining first actual drift is much smaller and starts after the attention output materialization rather than in `attn_probs`
- replaced the real Leech attention output projection with an explicit `torch.matmul(..., weight.t()) + bias` path for local testing; same-process repeated `5.7` first-step probes still drift, so the remaining bug is not only the original flatten/layout path
- added a block0-only repeat probe and a tensor-only attention-layout repro; the smaller repro shows repeated layout materialization can drift even on a fixed `attn_weighted` tensor
- confirmed that `HIP_LAUNCH_BLOCKING=1` removes that tensor-only layout drift entirely on the extracted `5.7` path, which sharply raises the value of an upstream async/ordering bug report
- corrected the public LeechTransformer status in `README.md`, `docs/USER_GUIDE.md`, and `TODO.md`: the extracted `6.4` host path can launch on GPU but is not numerically trustworthy, and the extracted `5.7` path is currently a diagnostic lane rather than a usable inference baseline
- recorded the current Leech correctness finding from the local probes: `6.4` diverges early around `block0.q_raw`, while `5.7` shows later repeated-run nondeterminism first detected around `block3.attn_out_preproj`
- removed the stale public framing that a measured `direct_only` token window implied trustworthy Leech inference output on Polaris
- documented that the extracted-runtime torch build used here does not expose a Vulkan backend, so Vulkan is not a practical fallback path for Leech under the present PyTorch environment
- updated `README.md` and `docs/USER_GUIDE.md` to match the current LeechTransformer reality on this machine: a short GPU smoke run still selects `device=cuda`, while longer runs remain a guarded ROCm compatibility lane rather than a declared stable baseline
- documented the current long-token mitigation in the public runbook: on this ROCm path, the active inference script disables `top_p` sampling above `36` generated tokens to avoid the faulting nucleus-sampling path
- updated `TODO.md` so the next LeechTransformer step is explicit: rerun the higher-token matrix with the current guardrails and then decide whether the public recommendation should move beyond `--max_tokens <= 36`
- fixed `scripts/debug-leech-high-token-instability.sh` fault classification so it no longer mistakes the devcoredump watcher banner for a GPU fault
- reran the focused `direct_only` LeechTransformer matrix on this machine and confirmed clean CUDA passes for `40`, `48`, and `64` generated tokens with both `kv_cache=off` and `kv_cache=on`
- updated the public LeechTransformer guidance to reflect that measured result: the currently documented `direct_only` path is now validated through `--max_tokens 64`, while `>64` and other profile families remain the next validation lane
- extended the same focused `direct_only` matrix further and confirmed clean CUDA passes for `80`, `96`, and `128` generated tokens with both `kv_cache=off` and `kv_cache=on`
- raised the documented `direct_only` LeechTransformer guidance again so the current measured ceiling is now `--max_tokens 128`; the next open boundary is `>128` or non-`direct_only` profiles

Why:

- the repo docs had fallen slightly behind the actual operational state of the LeechTransformer path
- the newer finer-grained probe changed the practical upstream debugging target from a generic "attention instability" claim to a specific flatten/layout path observation
- the follow-up implementation test showed that fixing the flatten/layout path changes the failure shape but does not eliminate it, so the docs needed to reflect both the useful narrowing and the failed local workaround
- the tensor-only repro plus the launch-blocking result are stronger than the earlier full-model symptom reports and are the most actionable upstream artifacts so far
- the newer CPU/GPU and GPU/GPU probe results show that crash-free execution is not the same thing as correct inference output
- short GPU runs are now good enough to document as working, but the longer-token path still needs measured re-baselining before it should be presented as solved

## 2026-03-30

- added a repo-local Silero VAD bootstrap path for the candidate normal WhisperX shell:
  - `.#whisperx` now exports `TORCH_HOME=$REPO_ROOT/.cache/torch`
  - added `scripts/bootstrap-silero-vad-cache.sh`
  - the script seeds `snakers4/silero-vad` into the exact `torch.hub` cache layout WhisperX expects (`..._main` plus `..._master`)
- updated the WhisperX docs so `silero` is documented as a local asset/bootstrap step rather than a live network fetch expectation
- tightened the documented status of the `gfx803_flake_v1` `.#whisperx` shell: it is still only a candidate normal path, not a verified short-file baseline
- recorded the new normal-path failure class explicitly: the non-RCA WhisperX CLI was mixing Nix ROCm device-libs from `/nix/store` (`LLVM 22`) with the extracted runtime toolchain (`LLVM 19` reader), which failed blit-kernel compilation and then segfaulted before transcription began
- updated the `.#whisperx` shell to stop injecting Nix ROCm toolchain packages (`clr`, `rocblas`, `miopen`) into the extracted host runtime path
- hardened `scripts/host-docker-python.sh` so it drops inherited Nix ROCm toolchain hints such as `ROCM_PATH`, `HIP_PATH`, `DEVICE_LIB_PATH`, and `HIP_DEVICE_LIB_PATH` when they point into `/nix/store`
- kept `HIP_LAUNCH_BLOCKING=1` and `JOBLIB_MULTIPROCESSING=0` as the practical Polaris-oriented defaults for the candidate normal WhisperX shell

Why:

- the new short-file normal WhisperX attempt failed for a different reason than the traced long-run WhisperX GPU hang lane
- the retained stderr identified a concrete ROCm/LLVM mixing problem rather than another ambiguous WhisperX crash
- the normal Nix shell needed to stop leaking incompatible Nix ROCm toolchain state into the extracted runtime before more short-file validation could be trusted
- once that was fixed, the next blocker became asset-locality rather than GPU/runtime correctness: `silero` was failing in `torch.hub` due to SSL trust / missing cache, so the repo now carries an explicit local-cache bootstrap path

## 2026-03-23

- tightened the old-ABI framework rebuild lane again after the Kineto-off torch build started failing in HIP-generated CUB objects under libstdc++ 15
- confirmed the failure is `__glibcxx_assert_fail` inside `std::array` in `__host__ __device__` code, not another `/opt/rocm` leakage or Kineto issue
- updated the rebuild driver to undefine `_GLIBCXX_ASSERTIONS` for the old-ABI lane so the next rebuild can test whether this is the last compile-time blocker before the torch smoke gate
- confirmed from the live build log that the first `_GLIBCXX_ASSERTIONS` workaround only hit host `CXX flags` and never reached the generated HIP compile commands
- updated the rebuild driver to export the same workaround through `HIPFLAGS` and `CMAKE_HIP_FLAGS` so the failing `torch_hip_generated_cub*.hip.o` path actually sees it
- confirmed the next failure is no longer the HIP/CUB assertion path itself: the bundled ROCm `lld` now fails to load `libxml2.so.2` during `amdgcn-link`
- updated the rebuild driver to discover a host `libxml2.so.2` provider and prepend that directory before the HIP toolchain runs
- confirmed from the next live command line that exporting `CMAKE_HIP_FLAGS` directly produced a malformed cmake invocation (`-DCMAKE_HIP_FLAGS=` followed by stray tokens)
- updated the rebuild driver to pass the HIP assertion workaround via `CMAKE_ARGS` as a single escaped `-DCMAKE_HIP_FLAGS:STRING=...` value instead

Why:

- the previous failures had already eliminated the packaging/runtime-path issues and the Kineto/roctracer header mismatch
- the remaining compile failure is now specific enough to justify a narrow compiler-flag workaround before trying broader source or toolchain changes

## 2026-03-20

- fixed `scripts/run_inference.py` compatibility with checkpoints that contain legacy pickled `LeechConfig` objects and added robust state-dict extraction for mixed checkpoint layouts
- added GPU-usage guardrails in `scripts/run_inference.py` for this path: warnings when requested token count exceeds known-stable range, and a safe default-disable for `--kv_cache` unless `LEECH_ALLOW_KVCACHE_GPU=1` is set
- expanded `docs/USER_GUIDE.md` with a practical LeechTransformer CUDA runbook (including exact wrapper invocation, working token limits, and crash mitigation notes)
- added `cachix-artifacts.manifest` plus `scripts/restore-cachix-artifacts.sh` so a fresh clone can relink the published extracted payloads from Cachix instead of rerunning the Docker extraction steps
- updated the publish helper so it refreshes the tracked manifest whenever artifact store paths are published
- added `docs/USER_GUIDE.md` as the single shareable setup, status, and contribution guide for non-specialist users
- updated `README.md` and `docs/START_HERE.md` so they point newcomers at the new guide first
- corrected the documented Ollama status: the extracted `artifacts/ollama_reference/` bundle now exists and is published through the artifact workflow, but host stability is still under investigation after a GPU reset / system crash during follow-up validation on this machine
- updated `TODO.md` so the next Ollama host-validation step is explicit after the recent extraction and launcher fixes
- improved `scripts/host-docker-python.sh` with optional GPU precheck warnings, optional automatic `devcoredump` watcher enablement, and explicit `/dev/kfd` visibility checks so users can capture crash evidence without manually polling device nodes
- expanded `docs/USER_GUIDE.md` with a plain-language clone-to-ready state onboarding path and a short crash capture workflow for non-technical readers

Why:

- the repo needed one document that could be handed to users without asking them to reconstruct the workflow from multiple notes
- a public Cachix cache is only half of the restore story unless the repo also tracks the exact store paths to relink on a fresh machine
- the previous docs overstated the current Ollama host status and needed to match observed reality before more users rely on that path

## 2026-03-19

- rewrote the top-level README to reflect the repo as a compatibility workspace, not just a graph demo
- added `docs/START_HERE.md` as a newcomer-friendly entrypoint
- added `TODO.md` to capture the immediate post-Docker-reset work, especially the `5.7` extraction and verification steps
- clarified `gfx803_flake_v1/README.md` so it documents the real prerequisites for `.#pytorch` and `.#rocmNative-franken`
- updated `scripts/extract-docker-libs.sh` so it can recover from a missing local `itir:latest` image by pulling it automatically
- added `scripts/extract-rocm57-artifacts.sh` as the explicit entrypoint for populating `artifacts/rocm57/`
- added the `artifacts/rocm57/` landing structure expected by the current flake workflow
- fixed `gfx803_flake_v1` runner assumptions so commands work from the flake subdirectory and can fall back to the extracted `docker-venv` runtime automatically
- extracted the `5.7` rocBLAS and MIOpen artifacts locally from `robertrosenbusch/rocm6_gfx803_comfyui:5.7`
- confirmed that the `rocmNative-franken` workload path still crashes before a full drift-matrix result is emitted
- added a shared benchmark schema and switched the drift workflow to emit standardized benchmark records and summaries
- taught `bug_report_mre.py` to emit machine-readable results while respecting externally supplied profile env vars
- added community bundle and release-manifest tooling plus initial GitHub Actions scaffolding for validation, Nix evaluation, and self-hosted GPU benchmark runs
- promoted the extracted `6.4` host wrapper to the measured zero-drift `direct_only` path for user-facing runs
- extended `5.7` extraction so it can pull compat libs and a Python environment in addition to rocBLAS/MIOpen payloads, and added `scripts/host-rocm57-python.sh` for host-side comparison runs
- documented that supported extraction targets are repo-local by default, and that any external output path is an explicit override rather than part of the baseline workflow
- confirmed that the extracted `6.4` host path now covers torch, WhisperX, and ComfyUI without requiring the old full Docker at runtime
- clarified that GPU Ollama is still the one remaining surface tied to the patched Robert container lineage, because the stock host `ollama` binary still falls back to CPU under the extracted `6.4` runtime
- added the public `gfx803-rocm` Cachix cache to the documented workflow and recorded that the extracted `6.4` and `5.7` artifact sets are now intended to be distributed through it
- extracted the patched Ollama `6.4.3/0.11.5` reference bundle to `artifacts/ollama_reference/`, validated GPU detection on host, and added `scripts/host-ollama-bundle.sh` plus a flake `.#ollama-bundle` shell for running it without the full container
- documented the short-term Ollama decision: re-downloading the already-working Robert image is still the practical fallback, while rebuilding and porting that path remains the longer-term Nix/extracted task

Why:

- the local Docker reset invalidated older assumptions that the source images and extracted artifacts were already present
- the repository had drifted away from accessible onboarding
- the `5.7` path was referenced in code but not presented as a concrete, user-facing workflow
- the Ollama situation had become easy to misstate: the repo now has broad host-side `6.4` coverage, but not a host-side GPU Ollama replacement yet
- the artifact workflow now has a real binary distribution path, so the repo docs and Nix entrypoints need to mention the shared cache explicitly
- the Ollama tradeoff also needed to be explicit: today the working image download is still cheaper than rebuilding the patched stack locally, even though the project direction is to remove that dependency
- the Ollama reference bundle is now host-validated, so a lightweight non-container path exists while a pure Nix rebuild is still pending
