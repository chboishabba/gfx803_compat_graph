# Changelog

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
