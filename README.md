# gfx803 / Polaris compatibility workspace

This repository is the working area for getting AMD Polaris cards such as the RX 580 usable with modern ROCm-era ML tooling, then recording what actually works in a graph and repeatable test outputs.

If you are new here, start with [docs/USER_GUIDE.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/USER_GUIDE.md). If you want the shorter repo-orientation version after that, read [docs/START_HERE.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/START_HERE.md).

## What this repo is for

This repo currently combines four kinds of work in one place:

- practical runtime bring-up for `gfx803` / Polaris on Linux
- drift and determinism probes for PyTorch / MIOpen / rocBLAS
- a Nix-based attempt to replace a pile of hand-built containers with clearer entrypoints
- a compatibility graph that turns findings into machine-readable artifacts

## Current state

As of `2026-03-22`, the repo state is:

- the repo now has a public Cachix binary cache for the extracted artifact sets: `https://gfx803-rocm.cachix.org`
- `itir:latest` is still the expected source image for the extracted `6.4` compatibility runtime, but it may need to be re-pulled locally after a Docker reset
- `lib-compat/` and `docker-venv/` are present in this working tree as previously extracted artifacts
- `gfx803_flake_v1/` is the clearest reproducible entrypoint for the current Nix-based workflow
- the extracted `6.4` host path remains the baseline runtime for torch and ComfyUI, while WhisperX is usable as a GPU RCA/reproducer surface but is not yet promoted as host-stable under real GPU workload
- the `gfx803_flake_v1` `.#whisperx` shell is currently only a candidate normal path: a short-file non-RCA run surfaced a separate Nix/extracted-runtime mixing bug where `/nix/store` ROCm device-libs (`LLVM 22`) leaked into the extracted runtime (`LLVM 19` reader), failed blit-kernel compilation, and then segfaulted before normal transcription could begin
- the next normal-path blocker after that shell fix is now explicit too: `--vad_method silero` depends on a `torch.hub` repo cache, so the repo now carries a local-cache bootstrap path instead of relying on live GitHub fetches at runtime
- the latest WhisperX split is now sharper:
  - without profiler, the reduced `stage=align` repro completed `transcribe`, entered `align`, and then hit a retained `GPU Hang` followed by an `amdgpu` reset / VRAM-loss wave around `2026-03-30 01:13:28`
  - with `rocprofv3`, the same reduced path completed successfully and emitted real profiler traces, but `rocprofiler-sdk` later segfaulted during teardown after writing result files
- the first named `blocking` matrix lane now also has a long-file summary-level
  success under `out/whisperx-rca-matrix/2026-03-30T16-45-56/summary.csv`,
  which strengthens `HIP_LAUNCH_BLOCKING=1` as a practical stabilizing lever
- that `blocking` success was not retained as a trace bundle
  (`kept_bundle=0`), so stronger log-level claims still need a rerun with
  `KEEP_SUCCESS_TRACE=1`
- this is enough definition to influence adjacent compat work:
  - prefer blocking-first defaults for fragile runtime-facing workflows
  - prefer short real workloads over synthetic-only smokes when checking a new
    compat lane
  - keep long async GPU workloads in the RCA-needed bucket instead of treating
    them as baseline-stable
- LeechTransformer remains an active GPU correctness investigation, not a finished runbook: the extracted `6.4` host path selects `device=cuda` but produces incorrect results, while the extracted `5.7` path is better only as a diagnostic baseline and is still not trustworthy for inference output
- the current LeechTransformer evidence points to a ROCm correctness issue on Polaris/gfx803: `6.4` shows early corruption from `block0.q_raw`, and the finer `5.7` probe now shows the first repeated-run instability at the attention flatten step `block0.attn_out_preproj_view`
- on the current `5.7` repro, `attn_probs`, `attn_weighted`, and `attn_heads_transposed` stay stable while `transpose(...).reshape(B, T, -1)` drifts; `permute(...).contiguous().reshape(...)` is stable on the same tensor, which makes the flatten/layout path a strong upstream debugging target
- a smaller tensor-only repro now exists: once `attn_weighted` is fixed, repeated layout materialization on GPU still drifts, but setting `HIP_LAUNCH_BLOCKING=1` removes that drift entirely, which points at an async/ordering-style ROCm bug rather than only bad model math
- the stock host `ollama` binary still falls back to CPU
- the extracted `artifacts/ollama_reference/` bundle is now available and publishable through Cachix, but host stability is still under investigation after a GPU reset/system crash during follow-up validation on this machine
- for short-term Ollama use, re-downloading the already-working Robert image is currently the pragmatic path; rebuilding or host-porting that patched stack locally remains slower and less settled
- `artifacts/rocm57/` is now a separately usable extracted `5.7` host artifact set alongside the top-level extracted `6.4` set
- `scripts/host-rocm57-python.sh` now imports torch successfully from the extracted `5.7` host artifact path
- `artifacts/rocm-latest/` is the dedicated landing area for `ROCm 7+` extraction attempts so latest experiments stay isolated from the `6.4` and `5.7` baselines
- a new `6.4`-derived upgrade lane is now the preferred path toward a reproducible newer stack for `gfx803`: instead of replacing the current `6.4` runtime outright, the project is moving toward cloning that lane and swapping newer components into it incrementally
- the cloned `6.4`-upgrade experiment still lives at `artifacts/rocm64-upgrade/`; its initial pre-swap capture is preserved there, but the broader full-sync latest-class form of that lane is now mainly a negative-control experiment because it becomes GPU-gated on Polaris
- the extracted `ROCm latest` lane now imports `torch 2.10.0+rocm7.2.0.gitb6ee5fde` after fixing the `/opt/venv` extraction path, but it reports `torch.cuda.is_available() == False` on this Polaris host
- the first full `6.4`-upgrade swap sequence is now classified: latest Python alone failed on ROCR/HIP symbol mismatches, adding newer support libs moved the failure into the sparse math stack, and syncing the full latest `lib-compat` removed import-time linker failures but still left `torch.cuda.is_available() == False`
- the first accepted `6.4`-upgrade shell is now narrower than the full latest-class lane: `artifacts/rocm64-upgrade-safe-support/` overlays only upgraded low-risk support libs (`libamd_comgr`, `librocm-core`, `libelf`, `libnuma`, and `libdrm*`) onto the control `6.4` userspace, and this keeps the frozen framework importing with `torch.cuda.is_available() == True`
- the primary short-term upgrade lane is now explicit as `artifacts/rocm64-upgrade-oldabi/`: it preserves the old HSA/HIP ABI from the control lane and upgrades only selected newer support libs around it
- `gfx803_flake_v1` now exposes two explicit PyTorch-stack shells:
  - control: `.#gfx803-pytorch-stack`
  - upgrade: `.#gfx803-pytorch-stack-upgrade`
- the next Nix-owned step is now explicit as well: a framework rebuild driver that attempts to rebuild `torch`, `torchvision`, and `torchaudio` against the preserved old-ABI lane, but the build now also needs a coherent old-ABI ROCm SDK root instead of only a runtime-lib overlay
- that rebuild driver is now exposed in `gfx803_flake_v1` as:
  - app: `nix run .#framework-rebuild`
  - shell: `nix develop .#gfx803-pytorch-framework-rebuild`
- the control shell still maps to the frozen extracted `6.4` Python/framework lane and corresponding control libs, while the upgrade shell now points at that first safe-support upgrade lane under the same frozen framework
- the fully upgraded userspace remains an explicit negative-control experiment, not the default upgrade shell: once the frozen framework sees the newer HIP/HSA ABI (`libamdhip64.so.7` and friends), imports or GPU visibility fail
- the rebuilt torch wheel now imports with the correct wheel-local `libtorch_*` libraries after tightening the rebuild driver’s runtime-path handling, but the first old-ABI-targeted smoke still leaked latest `/opt/rocm` sonames; the rebuild driver is therefore being tightened to require an extracted old-ABI ROCm SDK root and to reject silent runtime leakage before any further smoke results are trusted
- the runtime gate is now isolated below torch:
  - full latest-class userspace makes `rocminfo` fail with `HSA_STATUS_ERROR`
  - latest `libhsa-runtime64` alone is enough to trigger that failure on top of the working base
  - latest HIP userspace alone is not
- the repo now has reproducible HSA-side hybrid probe lanes that restore `rocminfo` by mixing the latest userspace with selected old HSA-side libraries, but rebuilt torch still fails there because latest `libamdhip64.so.7` expects newer ROCR/HSA symbols than the restored old runtime provides
- practical RCA split:
  - use `gdb` / `mcp-gdb` when the target is a host userspace failure such as `rocminfo` returning `HSA_STATUS_ERROR` or crashing inside the HSA stack
  - use `rocprofv3` plus kernel/devcoredump evidence when the target is a GPU hang, KFD reset, or pre-reset kernel/queue attribution
- the first debugger-backed `rocminfo` note is now captured too:
  - under `LD_LIBRARY_PATH=$PWD/artifacts/rocm-latest/lib-compat`, `rocminfo` resolves the latest `libhsa-runtime64.so.1.18.70200`
  - `hsa_init()` itself returns `4096` before agent enumeration starts
  - the retained artifact is `out/rocminfo-gdb/2026-03-29T21-59-30/gdb-hsa-flow.txt`
- the practical next target is therefore to preserve the old HSA/HIP ABI where needed and upgrade around it deliberately, not to assume a simple `latest HIP on old HSA` hybrid will work
- the `rocmNative-franken` shell still needs follow-up after the standalone `5.7` host artifact work; the next active experiments are incremental newer-component swaps into the `6.4`-upgrade lane, with pure `ROCm 7+` extraction treated as a component source rather than the main runtime target
- the repo now includes an initial GitHub Actions workflow for shell checks, unit tests, Nix evaluation, and an optional self-hosted GPU benchmark lane; full publish automation still remains future work
- the default user-facing extracted `6.4` host wrapper is now the zero-drift `direct_only` path
- the current extracted-runtime torch build has no Vulkan backend (`torch.backends.vulkan -> None`), so Vulkan is not a usable fallback path for Leech under the present PyTorch runtime

## Start here

Choose the path that matches what you need:

- I just want the high-level orientation:
  Read [docs/USER_GUIDE.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/USER_GUIDE.md)
- I want the short repo-oriented summary:
  Read [docs/START_HERE.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/START_HERE.md)
- I want the current Nix entrypoints:
  Read [gfx803_flake_v1/README.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/gfx803_flake_v1/README.md)
- I want the Docker-to-Nix migration plan for the known working gfx803 PyTorch stack:
  Read [docs/NIX_MIGRATION_CHECKLIST.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/NIX_MIGRATION_CHECKLIST.md)
- I want the Polaris safety settings:
  Read [POLARIS_STABILITY_BLUEPRINT.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/POLARIS_STABILITY_BLUEPRINT.md)
- I want the immediate work queue:
  Read [TODO.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/TODO.md)

## Canonical benchmark outputs

The repo now standardizes local comparison runs into:

- `out/drift/benchmark-results.jsonl`
- `out/drift/benchmark-summary.json`
- `out/compat-graph-results.json`
- `out/drift/release-manifest.json`

The primary benchmark entrypoint is:

```bash
bash scripts/run-drift-matrix
```

That benchmark currently confirms the extracted `6.4` host baseline behaves as follows on this machine:

- `default`: `partial`
- `direct_only`: `pass`
- `gemm_only`: `partial`
- `stable_profile`: `partial`

## Extraction output locations

The supported extraction workflow writes into this repository by default:

- `bash scripts/extract-docker-libs.sh` populates `lib-compat/` and `docker-venv/`
- `bash scripts/extract-rocm57-artifacts.sh` populates `artifacts/rocm57/`
- `bash scripts/extract-rocm-latest-artifacts.sh` populates `artifacts/rocm-latest/`
- `bash scripts/create-rocm-latest-hsa-hybrid-lanes.sh` populates `artifacts/rocm-runtime-hybrids/`
- `bash scripts/create-rocm64-upgrade-oldabi-lane.sh` populates `artifacts/rocm64-upgrade-oldabi/`
- `bash scripts/extract-rocm64-oldabi-sdk.sh` populates `artifacts/rocm64-oldabi-sdk/`
- `bash scripts/extract-ollama-reference-artifacts.sh` populates `artifacts/ollama_reference/`
- `bash scripts/clone-rocm64-upgrade-lane.sh` clones the current extracted `6.4` compat libs and Python env into `artifacts/rocm64-upgrade/` as the starting point for newer-component swaps
- `bash scripts/create-rocm64-upgrade-safe-support-lane.sh` creates `artifacts/rocm64-upgrade-safe-support/` as the first accepted upgrade lane that keeps the frozen framework ABI intact

`scripts/extract-rocm57-artifacts.sh` also accepts `ROCM57_OUTDIR` or a positional output path, but that is an explicit override. External scratch locations are not part of the documented baseline workflow and should only be used deliberately for large temporary test runs.

## Binary cache

The extracted artifact sets are now publishable through the repo Cachix cache:

- cache URL: `https://gfx803-rocm.cachix.org`
- public key: `gfx803-rocm.cachix.org-1:UTaIREqPZa9yjY7hiMBYG556OrGR6WEhWPjqX4Us3us=`

The intended cached artifact sets are:

- extracted `6.4` host compat libs
- extracted `6.4` Python environment
- extracted `6.4`-upgrade experimental lane
- extracted `6.4`-upgrade old-ABI lane
- extracted `6.4`-upgrade safe-support lane
- extracted `5.7` artifact tree
- extracted `Ollama` reference bundle

Both flakes now advertise this cache in `nixConfig` so `nix develop` and related commands can discover the published binaries automatically once the paths are available upstream.

The migration target for those artifacts is documented in [docs/NIX_MIGRATION_CHECKLIST.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/NIX_MIGRATION_CHECKLIST.md): preserve the original working gfx803 Docker recipe, but split it into reusable Nix-owned runtime, math, framework, and app layers.

The current migration order is now explicit there as well: PyTorch first, Ollama later.
The next flake shape is also explicit there: one frozen control PyTorch stack and one upgrade stack that keeps the same Python/framework layer while swapping only the ROCm/runtime side.
The next runtime split is explicit too: HSA-hybrid latest-class lanes are now reproducible probe artifacts, but they are diagnostic only until the HIP/HSA ABI seam is resolved.

For a fresh clone, restore the extracted payloads back into the working tree with:

```bash
bash scripts/restore-cachix-artifacts.sh
```

That uses the tracked `cachix-artifacts.manifest` file to relink the published store paths into `lib-compat/`, `docker-venv/`, and the supported `artifacts/` directories.

## Recommended workflows

### 1. Reuse the extracted `6.4` userspace on the host

This is the most direct path when `itir:latest` is available.

```bash
bash scripts/extract-docker-libs.sh
source scripts/polaris-env.sh
./scripts/host-docker-python.sh tests/bug_report_mre.py
```

What this does:

- reuses the known-good ROCm `6.4` userspace from `itir:latest`
- applies the Polaris compatibility environment
- runs the extracted Python environment on the host
- now covers the host-side torch and ComfyUI surfaces that were previously validated inside the `6.4` Docker lineage
- WhisperX can launch and use the GPU on this extracted host runtime, but it remains an RCA/reproducer surface because real runs can still trigger KFD / reset instability
- the strongest current no-profiler boundary is now:
  - `transcribe` completed
  - `align` started
  - then the run hit `GPU Hang` and the host entered an `amdgpu` reset / VRAM-loss wave
- `rocprofv3` is now proven usable enough to emit real kernel and marker traces here, but its own teardown can segfault after the workload succeeds
- defaults to the `direct_only` zero-drift solver path for end users

### 2. Use the Nix flake entrypoints

This is the preferred direction for a more maintainable setup.

```bash
cd gfx803_flake_v1
nix develop .#base
verify-gfx803-host
```

For drift testing:

```bash
cd gfx803_flake_v1
nix develop .#pytorch
run-drift-matrix
```

If `docker-venv/` exists, the flake runner now falls back to that extracted Python runtime automatically.

### 3. Prepare the `5.7` payload path

The repo now supports two separate `5.7` uses:

- standalone extracted host runtime via `scripts/host-rocm57-python.sh`
- the `gfx803_flake_v1` `rocmNative-franken` shell that reuses the extracted `5.7` payload

Populate them with:

```bash
bash scripts/extract-rocm57-artifacts.sh
```

That writes into:

- `artifacts/rocm57/rocblas-library`
- `artifacts/rocm57/miopen-db`
- `artifacts/rocm57/lib-compat`
- `artifacts/rocm57/docker-venv`
- `artifacts/rocm57/meta`

After that:

```bash
bash scripts/host-rocm57-python.sh -c 'import torch; print(torch.cuda.is_available())'
```

Or for the mixed shell:

```bash
cd gfx803_flake_v1
nix develop .#rocmNative-franken
run-drift-matrix
```

### 4. Attempt a separate `ROCm 7+` extracted host path

This is the current experiment lane for trying a newer runtime without disturbing the `6.4` or `5.7` artifacts.

```bash
bash scripts/extract-rocm-latest-artifacts.sh
bash scripts/host-rocm-latest-python.sh -c 'import torch; print(torch.__version__)'
```

As of March 19, 2026, Docker Hub shows `rocm/pytorch:latest` tracking a `7.2` release image, so this path should be treated as a moving target and recorded carefully when a run succeeds.

### 5. Build a `6.4`-derived upgrade lane toward newer ROCm components

This is now the preferred path for trying to reach a newer reproducible stack on Polaris without throwing away the known `6.4` runtime shape.

```bash
bash scripts/clone-rocm64-upgrade-lane.sh
bash scripts/create-rocm64-upgrade-safe-support-lane.sh
bash scripts/host-rocm64-upgrade-safe-support-python.sh -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'
```

That first upgrade shell is intentionally narrow:

- frozen extracted `6.4` Python/framework layer
- control HIP/HSA ABI
- newer low-risk support libs only

The full latest-class upgrade experiments remain available, but they are not the default shell because they currently lose Polaris GPU visibility.

```bash
bash scripts/host-rocm64-upgrade-python.sh -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'
bash scripts/swap-rocm64-upgrade-python-from-latest.sh
bash scripts/swap-rocm64-upgrade-support-libs-from-latest.sh
bash scripts/swap-rocm64-upgrade-math-libs-from-latest.sh
bash scripts/sync-rocm64-upgrade-lib-compat-from-latest.sh
bash scripts/capture-leech-minimal-repros.sh --runner scripts/host-rocm64-upgrade-python.sh --label rocm64-upgrade
```

The intended workflow is:

- clone the current extracted `6.4` runtime into `artifacts/rocm64-upgrade/`
- make the first Python/PyTorch swap explicit once `artifacts/rocm-latest/docker-venv/` is available
- swap newer components into that cloned lane one group at a time
- use the minimal Leech repro scripts as the gate after each swap
- publish the upgraded lane through the same Cachix workflow once it proves reproducible

Current measured result:

- `artifacts/rocm64-upgrade-safe-support/` keeps the frozen framework importing with `torch.cuda.is_available() == True`
- pure latest imports `torch 2.10.0+rocm7.2.0.gitb6ee5fde` but reports `torch.cuda.is_available() == False`
- the fully synced `artifacts/rocm64-upgrade/` lane reaches the same latest-class result once its Python layer and full `lib-compat` are synced from latest
- so the first real upgrade shell is the safe-support lane, while the full latest-class lane remains useful mainly for ABI and device-gating investigation

### 6. Inspect or test the extracted Ollama reference payload outside Docker

The patched `6.4.3/0.11.5` Ollama GPU path is extracted to `artifacts/ollama_reference/` and published with the rest of the extracted payloads. Treat it as an active host-port investigation, not a finished daily-driver workflow.

```bash
# from repo root
source scripts/polaris-env.sh
export LD_LIBRARY_PATH="$PWD/artifacts/ollama_reference/rocm-6.4.3/lib:${LD_LIBRARY_PATH:-}"
OLLAMA_HOST=http://127.0.0.1:11434 scripts/host-ollama-bundle.sh serve

# shortcut: one-step server launcher
./scripts/serve-ollama-gfx803.sh
```

Or via flake shell:

```bash
cd gfx803_flake_v1
nix develop .#ollama-bundle
OLLAMA_HOST=http://127.0.0.1:11434 ../scripts/host-ollama-bundle.sh serve
```

If you want to persist model/data fetches in the Robert container path instead of re-downloading each run, use:

```bash
bash scripts/run-gfx803-ollama-container.sh
OLLAMA_HOST=http://127.0.0.1:11434 ollama pull mistral:7b
OLLAMA_HOST=http://127.0.0.1:11434 ollama run mistral:7b "Once upon a time Lila"
```

The script starts the container with:
- persistent cache mount for models/manifests (default: `~/.cache/gfx803-ollama/.ollama`)
- `OLLAMA_MODELS=/workspace/.ollama/models` inside the container
- no Open WebUI startup path (so no UI migration/fetch on each run)

To stop it:

```bash
bash scripts/run-gfx803-ollama-container.sh --stop
```

If you need the full image behavior (including Open WebUI), pass `--with-webui`:

```bash
bash scripts/run-gfx803-ollama-container.sh --with-webui
```

## Important limitations

- Newer native ROCm stacks still gate Polaris aggressively
- `6.4` remains the known practical runtime baseline in this repo for torch import and the broader extracted userspace bring-up story
- For Ollama GPU, the stock host binary still falls back to CPU
- The extracted reference bundle (patched `6.4.3/0.11.5`) now exists and is distributed through the repo artifact workflow, but it has not yet earned "safe host replacement" status because follow-up validation on this machine triggered GPU reset/system instability
- The upstream Robert image remains the safer working path until the extracted host bundle is stabilized or replaced with a cleaner Nix build
- the separate `5.7` host artifact now imports torch successfully, but current Leech debugging shows it as a diagnostic path only, not a trustworthy inference baseline
- the `ROCm 7+` extracted path is experimental and may break as upstream images move
- the top-level `flake.nix` is an older shell definition; the more current flake work is under `gfx803_flake_v1/`
- CI/CD is not implemented here yet, so the repo is still driven manually
- the extracted-runtime PyTorch build used here does not expose Vulkan support, so installing Vulkan-capable user-space through Steam does not by itself make Leech runnable on Vulkan
- the old-ABI framework rebuild driver now forces `FRAMEWORK_REBUILD_ROOT=artifacts/pytorch-framework-rebuild-oldabi-kinetooff`, injects `_GLIBCXX_ASSERTIONS` through `HIPFLAGS/CMAKE_ARGS`, and prepends the host `libxml2.so.2` path before running `amdgcn-link`, so the next run under that directory is the authoritative torch-smoke signal

## WhisperX-WebUI on gfx803

The gfx803-specific Nix entrypoint for `WhisperX-WebUI` now lives in this repo's top-level flake.

Use it from this repo root:

```bash
nix develop .#whisperx-webui-gfx803
start-whisperx-webui-gfx803 --server_name 0.0.0.0 --server_port 7860
```

Or directly:

```bash
nix run .#whisperx-webui-gfx803 -- --server_name 0.0.0.0 --server_port 7860
```

That shell/app:

- launches `/home/c/Documents/code/ITIR-suite/WhisperX-WebUI/app.py`
- uses this repo's extracted `lib-compat/` and `docker-venv/` runtime
- keeps the Polaris env defaults (`HSA_OVERRIDE_GFX_VERSION=8.0.3`, `ROC_ENABLE_PRE_VEGA=1`, `HIP_LAUNCH_BLOCKING=1`)
- writes cache/model output under the WebUI repo so the app still behaves like a normal project checkout

Quick check:

```bash
nix run .#verify-whisperx-webui-runtime
```

The `WhisperX-WebUI` repo may still carry its own local wrapper flake for convenience, but the canonical gfx803-specific compatibility entrypoint is now this repo.

## Crash capture

If the GPU glitches, resets, or the desktop shows checkerboard corruption after a run, capture the kernel-side evidence immediately:

```bash
bash scripts/capture-amdgpu-crash-artifacts.sh '10 minutes ago'
```

That writes a timestamped folder under `out/crashlogs/` and attempts to copy the live amdgpu `devcoredump` payload before it disappears.

For WhisperX-specific RCA on this host, there is now a narrower tracing path:

```bash
bash scripts/run-whisperx-rca-matrix.sh /path/to/sample.wav --language en
```

That runner defaults to the likely fault surfaces (`align` and `diarize`), compares `int8` against `float16`, sweeps `HIP_LAUNCH_BLOCKING=0/1`, and only keeps trace bundles for suspicious runs. For one focused case, use:

```bash
STAGE=align WHISPERX_COMPUTE_TYPE=int8 \
bash scripts/trace-whisperx-rocprof.sh /path/to/sample.wav --language en
```

The wrapper now prefers `rocprofv3` automatically when it is available. To force a specific backend:

```bash
WHISPERX_PROFILER_BACKEND=rocprofv3 bash scripts/trace-whisperx-rocprof.sh /path/to/sample.wav --language en
WHISPERX_PROFILER_BACKEND=rocprof bash scripts/trace-whisperx-rocprof.sh /path/to/sample.wav --language en
```

For crashy profiler runs, prefer the reduced crash-capture mode:

```bash
WHISPERX_PROFILER_MODE=crash-capture \
WHISPERX_PROFILER_BACKEND=rocprofv3 \
bash scripts/trace-whisperx-rocprof.sh /path/to/sample.wav --language en
```

For the next crash-focused run on the main long file, prefer a compute-stage
policy instead of a fixed named stage:

```bash
WHISPERX_PROFILER_MODE=crash-capture \
WHISPERX_PROFILER_BACKEND=rocprofv3 \
WHISPERX_ROCPROFV3_OUTPUT_MODE=rocpd \
WHISPERX_ROCPROFV3_ENABLE_MEMORY_COPY_TRACE=1 \
WHISPERX_PROFILE_STAGE_POLICY=first_compute \
bash scripts/trace-whisperx-rocprof.sh /path/to/sample.wav --language en
```

Exact-stage selection is still available for comparison runs through
`WHISPERX_PROFILE_SELECTED_STAGE=align` or another explicit stage, but it is no
longer the primary crash-lane recommendation for the long file.

If copy-path suspicion is the current target, enable
`WHISPERX_ROCPROFV3_ENABLE_MEMORY_COPY_TRACE=1` on the `first_compute` lane so
the retained `rocpd` bundle captures memory-copy activity directly instead of
inferring it only from older heavier traces.

If stage-gated profiling is not sufficient, the wrapper still supports a
bounded fallback collection window through `WHISPERX_ROCPROFV3_COLLECTION_PERIOD`
and `WHISPERX_ROCPROFV3_COLLECTION_PERIOD_UNIT`.

The retained bundle correlates:

- profiler output from `rocprofv3` or legacy `rocprof`
- ROCTX stage markers from the WhisperX harness
- structured stage timing and GPU-memory snapshots
- host CPU hotspot snapshots, which are useful when the real bottleneck is media decode or CPU-only fallback rather than GPU work
- lightweight `heartbeat.log` snapshots so profiler mode and last retained stage evidence survive even if the host resets before profiler finalize
- `observer.log` snapshots with recent run output, recent stage events, profiler file sizes, and current-boot kernel tail
- any captured `amdgpu` devcoredump artifacts

Operational note:

- `zkperf` is relevant here as a pattern source for run orchestration and stage comparison, but it is not used directly for WhisperX RCA because it does not provide ROCm, `amdgpu`, or `devcoredump`-specific capture
- the repo now also has an execution-path admissibility registry surface under `schemas/execution_path_claim.schema.json` and `artifacts/execution_path_claims/examples/`
- if an `MP4` source pegs CPU, check `host-cpu.log` first; the common culprit is `ffmpeg` decoding/transcoding the input before WhisperX reaches the suspect GPU stage
- current WhisperX evidence should be read narrowly:
  - the workload can start, use the GPU, and progress into real work
  - the host can still hit a KFD / reset crash at an as-yet unknown point under real GPU pressure
  - the stronger current model is lower-level than a single WhisperX stage: pinned-page pressure, GPU VM faults, queue timeout, and reset behavior are all in play
  - the currently confirmed failure class is queue/ring forward-progress loss, because the kernel repeatedly reports `ring gfx timeout`
  - the current strongest promoted boundary is the exposure point: D2H copy plus host wait
  - the first `Host active wait ... for -1 ns` is now the earliest reliable pre-crash sentinel on the retained userspace path
  - pinned host memory likely sits on that DMA path, but the current evidence fits stalled copy completion much better than successful delivery of bad data into host userspace
  - the current leading trigger classes remain lower-level: GPU VM or pinned-page failure, or DMA/copy-path stall
  - the current leading ownership hypothesis is ROCm/amdgpu instability on `gfx803` / Polaris under this mixed compute+copy path
  - that still does not promote copy overflow or a host-only crash as the root cause
  - the current remediation view is also layered:
    - VM-pressure patch shapes aim to move the first `-1 ns` later or remove it
    - queue-visibility patch shapes aim to surface failure earlier and more cleanly
    - D2H-relief patch shapes aim to weaken the copy/wait boundary
    - backend-substitution patch shapes aim to expose a narrower ROCm/library/kernel ownership path
  - the pressure model is now tighter:
    - raw file length is only a proxy
    - segment size is a stronger direct control
    - the practical danger surface is closer to segment size × batch size × concurrency
    - smaller segment windows can be safer even when they create more total segments
  - the concrete existing tool surface is now documented too:
    - runtime/env controls such as `HIP_LAUNCH_BLOCKING=1`, shorter inputs, smaller segment windows, alternate compute type, and memory-copy trace off
    - API-level mitigation patterns such as sync fences, pinned-buffer reuse, chunked D2H, and dedicated copy streams if the path becomes editable
    - kernel/driver stabilizers such as `amdgpu.lockup_timeout=...` and `amdgpu.gpu_recovery=1`
  - desktop redraw or `alt-tab` activity may aggravate or expose the fault, but that is still a hypothesis rather than a promoted causal claim
  - so WhisperX is currently a useful reproducer and RCA surface, not a promoted host-stable workflow
- the retained `2026-03-27` reduced repro shows the run got through `load_model` and `load_audio` and had already entered `transcribe` before the crash boundary, so the current evidence is broader than "alignment specifically crashes it"
- the harness now prefers `librocprofiler-sdk-roctx` over legacy `libroctx64` and emits explicit `roctxMarkA` run/stage markers in addition to pushed ranges; a light `stage=load` verification bundle now shows `run_start`, `stage_start:load_model`, `stage_end:load_model`, `whisperx:load_model`, and `run_end:load_model` in `whisperx_marker_api_trace.csv`
- exact-stage `align` profiling is now validated on successful shorter runs, but the main long-file crash run on `2026-03-30T12-38-04` failed earlier during `transcribe`, so the next long-file crash attempt should use a compute-stage policy instead of another fixed stage name

## WhisperX RCA lane matrix

We now treat the RCA surface as five governed lanes whose tooling must move the live sentinels before we promote any root-cause claim:

1. Baseline crash lane (`first_compute + memory-copy-trace`) – anchors the current `-1 ns` timing and failure window.
2. Queue / async visibility lane (`HIP_LAUNCH_BLOCKING=1`, sync fences) – ensures the queue timeout is explicit and exposes if async progression alone triggers the failure.
3. Pressure-control lane (smaller segment windows, `batch_size=1`, chunk reuse) – keeps the per-segment working set bounded even on long files so we can test the pressure hypothesis directly.
4. DMA-light lane (memory-copy trace off, staged/streamed D2H when supported) – isolates the copy path as the only difference.
5. Backend / compute lane (alternate compute types / kernel mixes) – proves whether a library/runtime path owns the failure once pressure and queue effects are controlled.

Each lane describes the expected effect on `Host active wait ... for -1 ns` and the subsequent `ring gfx timeout`, and the full matrix is tracked in [docs/USER_GUIDE.md](docs/USER_GUIDE.md), [TODO.md](TODO.md), [docs/ADMISSIBILITY_CONE_TREE.md](docs/ADMISSIBILITY_CONE_TREE.md) and the Polaris toolbox in [POLARIS_STABILITY_BLUEPRINT.md](POLARIS_STABILITY_BLUEPRINT.md).

## Main files and directories

- `docs/START_HERE.md`: newcomer entrypoint
- `docs/USER_GUIDE.md`: shareable user-facing setup and contribution guide
- `gfx803_flake_v1/`: current Nix-first workflow
- `scripts/`: extraction and execution helpers
- `benchmark_schema.py`: shared benchmark/result contract
- `tests/`: reproducible drift probes
- `lib-compat/`: extracted ROCm `6.4` compatibility libraries
- `docker-venv/`: extracted Python environment from the working container flow
- `artifacts/rocm57/`: extracted `5.7` payload location
- `out/`: generated results
- `CONTEXT.md`: long-form project context and archived planning notes

## Compatibility graph quick start

The graph portion of the repo is still useful independently.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_demo.py
python experiment_planner.py
```

This writes:

- `out/gfx803_graph.json`
- `out/gfx803_graph.graphml`
- `out/known_knowns.json`
- `out/known_unknowns.json`
- `out/proposed_experiments.json`
- `out/ranked_experiment_plan.json`

## Community validation and release metadata

To package a community submission bundle from a benchmark record:

```bash
python scripts/create_community_bundle.py   --record-file out/drift/benchmark-results.jsonl   --record-id <record_id>   --bundle-dir out/community/example_bundle   --workflow-id comfyui_sd15_reference
```

To build a release manifest from benchmark results:

```bash
python scripts/build_release_manifest.py   --results out/drift/benchmark-results.jsonl   --out out/drift/release-manifest.json   --stack-id rocm64_extracted_host   --release-id local-dev
```
