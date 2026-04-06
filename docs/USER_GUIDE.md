# User Guide

This is the document to send to someone who just wants to know what this project does, how to get started, what currently works, and where to report results.

## What This Project Is

This repository is a practical compatibility workspace for older AMD Polaris GPUs such as the RX 470, RX 480, RX 570, RX 580, and RX 590.

Those GPUs use the `gfx803` architecture. Modern ROCm releases no longer support `gfx803` cleanly, so this project keeps track of working runtime combinations, extracted artifact bundles, safety flags, and benchmark results.

The short version:

- `torch` works on the extracted `ROCm 6.4` host path
- `WhisperX` and related Python workflows can launch on the same extracted host runtime, but on this machine they remain RCA/reproducer surfaces rather than promoted host-stable GPU workflows
- `ComfyUI` is available through the extracted host runtime, with Polaris safety flags strongly recommended
- `Ollama` has a working patched reference bundle extracted from `robertrosenbusch/rocm6_gfx803_ollama:6.4.3_0.11.5`, but host stability is still under investigation on this machine
- the path toward a reproducible newer ROCm-class stack is now a cloned `6.4` upgrade lane, not a direct jump to pure `latest`


## New-machine onboarding in one pass

If you want a setup you can hand to anyone (including people who do not usually use Nix), use this sequence exactly:

1. Install Nix (or make sure your Nix is healthy):

```bash
curl -L https://nixos.org/nix/install | sh
```

2. Enable the project cache:

```bash
cachix use gfx803-rocm
```

3. Clone and restore payloads from Cachix:

```bash
git clone https://github.com/chboishabba/gfx803_compat_graph.git
td=$(mktemp -d)
cd "$td/gfx803_compat_graph"
bash scripts/restore-cachix-artifacts.sh
```

4. Enter the maintained flake and run the GPU verification step:

```bash
cd gfx803_flake_v1
nix develop .#pytorch
verify-gfx803-host
```

If verification shows a healthy GPU, the practical surfaces should all work from this same checkout:

- `torch` via extracted runtime
- `WhisperX` via extracted runtime as an RCA/reproducer surface, not a promoted stable workflow
- for normal WhisperX transcription attempts on this host, prefer the Nix
  `.#whisperx` shell with `HIP_LAUNCH_BLOCKING=1` before using the heavier RCA
  tracing wrappers
- `ComfyUI` via extracted runtime
- extracted Ollama reference bundle for local `ollama` experiments (still marked unstable on some workloads)

If you cannot access the GPU, run:

```bash
bash scripts/capture-amdgpu-crash-artifacts.sh '20 minutes ago'
```

and include `out/crashlogs/...` in your report.

For Python runs where you want live crash capture during the command, set:

```bash
WATCH_AMDGPU_DEVCOREDUMP=1 bash scripts/host-docker-python.sh tests/bug_report_mre.py
```

## What you can use today

- `torch` via the extracted `6.4` host runtime
- `WhisperX` via the extracted `6.4` host runtime as an RCA/reproducer surface
- `ComfyUI` via the extracted `6.4` host runtime
- extracted `5.7` artifacts for comparison and mixed-runtime experiments
- a separate `ROCm 7+` experiment lane for newer upstream attempts
- a `6.4`-derived upgrade lane for incrementally testing newer components while preserving the current working runtime shape
- an extracted patched `Ollama` reference bundle for investigation and packaging work

## Current Reality

Please use this project with the following expectations:

- the extracted `6.4` host path is the current baseline for torch import and the broader extracted userspace
- the public binary cache is `https://gfx803-rocm.cachix.org`
- the `5.7` and `ROCm 7+` paths are experiment lanes, not the default recommendation
- the preferred route toward a more current reproducible stack is now a cloned `6.4` upgrade lane rather than a direct switch to pure `ROCm latest`
- the extracted `Ollama` reference bundle now extracts correctly and is published to Cachix, but it is not yet a settled "safe daily driver" host path
- on this host, the extracted `Ollama` bundle can start and then trigger a GPU reset / system instability; that investigation is still open
- if you need GPU `Ollama` immediately, the already-working Robert container lineage is still the safer fallback than the host bundle
- the latest reduced WhisperX split is:
  - no profiler: `transcribe` completed, `align` started, then the run retained `GPU Hang` and the host entered an `amdgpu` reset / VRAM-loss wave
  - `rocprofv3`: the same reduced path completed and wrote profiler artifacts, but `rocprofiler-sdk` later segfaulted during teardown
- that means profiler attachment is now a known confounder for this RCA lane: it can change timing or pressure enough to let the workload survive
- the newer named `blocking` lane adds one more practical constraint:
  - `HIP_LAUNCH_BLOCKING=1` is now the first summary-confirmed stabilizing
    lever on the long-file WhisperX repro
  - that does not promote long-form WhisperX as fully solved, but it is enough
    to shape adjacent compat defaults on this host
- practical carryover for other compat work on this machine:
  - blocking-first defaults are reasonable for fragile runtime-facing workflows
  - short real workloads are more informative than synthetic-only smokes
  - long async GPU workloads still belong in the RCA-needed bucket

## Quick Setup

If you already use Nix, this is the fastest low-friction start:

```bash
cachix use gfx803-rocm
git clone https://github.com/chboishabba/gfx803_compat_graph.git
cd gfx803_compat_graph
bash scripts/restore-cachix-artifacts.sh
cd gfx803_flake_v1
nix develop .#base
verify-gfx803-host
```

If the verification step succeeds, move to the `pytorch` shell:

```bash
nix develop .#pytorch
run-drift-matrix
```

That is the cleanest maintained entrypoint for people who want a reproducible workflow.

## Quick Setup Without Rebuilding Everything

If you want the extracted host runtime directly from this repo:

```bash
git clone https://github.com/chboishabba/gfx803_compat_graph.git
cd gfx803_compat_graph
bash scripts/restore-cachix-artifacts.sh
source scripts/polaris-env.sh
./scripts/host-docker-python.sh tests/bug_report_mre.py
```

That path is the practical host entrypoint for:

- `torch`
- `WhisperX` as an RCA/reproducer surface
- `ComfyUI`

## Persisted Ollama container mode (for less repeated fetch/setup)

If you want to avoid repeating web/UI fetches and model downloads when using the Robert image directly, run:

```bash
bash scripts/run-gfx803-ollama-container.sh
OLLAMA_HOST=http://127.0.0.1:11434 ollama pull mistral:7b
OLLAMA_HOST=http://127.0.0.1:11434 ollama run mistral:7b "Once upon a time Lila"
```

This starts the container with:

- persistent model cache mount at:
  - default: `~/.cache/gfx803-ollama/.ollama`
  - can be overridden with `--root` / `OLLAMA_CACHE_ROOT`
- `OLLAMA_MODELS=/workspace/.ollama/models` inside the container
- `ollama` binary launch only (no Open WebUI startup path by default)

To avoid port collisions in a second terminal, the launcher is idempotent:

```bash
bash scripts/run-gfx803-ollama-container.sh
# if container is already running, this prints and reuses it
bash scripts/run-gfx803-ollama-container.sh --restart
```

To use a different host port (for example while tracing), pass `--port`:

```bash
bash scripts/run-gfx803-ollama-container.sh --port 11435 --root ~/.cache/gfx803-ollama-port11435
OLLAMA_HOST=http://127.0.0.1:11435 ollama pull mistral:7b
```

Stop with:

```bash
bash scripts/run-gfx803-ollama-container.sh --stop
```

If you need Open WebUI behavior in the same image, add `--with-webui`.

## LeechTransformer Status (CUDA/PyTorch path)

If you use the extracted host runtime, LeechTransformer can still be launched directly for debugging:

```bash
cd /home/c/Documents/code/__OTHER/gfx803_compat_graph
HOST_DOCKER_PYTHON_GPU_PRECHECK=1 bash scripts/host-docker-python.sh \
  /home/c/Documents/code/DASHIg/LeechTransformer/scripts/run_inference.py \
  --checkpoint /home/c/Documents/code/DASHIg/LeechTransformer/data/best_model.pt \
  --prompt "Once upon a time Lila" \
  --max_tokens 32
```

What is currently true on this setup:

- script selects `device=cuda`
- checkpoint loads without the `__main__.LeechConfig` unpickle error
- short and long prompts can complete on GPU without an immediate crash
- the extracted `6.4` host path is not numerically trustworthy for Leech output on this machine, even though it selects `device=cuda`
- the extracted `5.7` path is useful for comparison and diagnostics, but it is also not yet trustworthy for inference output

What the current debugging says:

- `ROCm 6.4` diverges from CPU almost immediately, with the first large corruption detected around `block0.q_raw`
- `ROCm 5.7` avoids that early `6.4` failure mode, but repeated identical GPU runs still diverge; the finer probe now finds the first repeated-run instability at `block0.attn_out_preproj_view`
- on the current `5.7` repro, `attn_probs`, `attn_weighted`, and `attn_heads_transposed` stay stable while the flattening step `transpose(...).reshape(B, T, -1)` drifts; the alternative `permute(...).contiguous().reshape(...)` path is stable on the same tensor
- a local attempt to apply that `permute(...).contiguous().reshape(...)` materialization in the actual Leech attention code did not stabilize end-to-end first-step logits on this machine, so that finding is useful for upstream debugging but is not yet a sufficient fix
- after that local attention patch, a same-process repeated-run probe still shows large intra-GPU first-step drift, which means the flatten/layout issue is only one part of the remaining ROCm correctness problem
- a newer tensor-only layout repro now shows that even repeated materialization of a fixed `attn_weighted` tensor can drift on the extracted `5.7` runtime, while the same repro becomes stable under `HIP_LAUNCH_BLOCKING=1`; that makes launch ordering / synchronization a concrete upstream lead
- this means the present Leech path is a ROCm correctness investigation, not a validated end-user workflow
- the `temperature=0` greedy-decoding bug in upstream LeechTransformer was fixed separately, so the remaining bad output here should be treated as a runtime/math issue rather than a decode-logic bug
- for `--max_tokens > 36`, the current inference script still forces `top_p=1.0` on ROCm because the tested nucleus-sampling path was a repeatable crash trigger on this host; that guard remains useful for crash avoidance, but it does not make the output trustworthy
- if you specifically want to test `--kv_cache` as part of the ongoing debugging, do it with:

```bash
LEECH_ALLOW_KVCACHE_GPU=1 HOST_DOCKER_PYTHON_GPU_PRECHECK=1 bash scripts/host-docker-python.sh \
  ... --kv_cache ...
```

- If you want to triage higher-token instability with a full matrix (tokens × kv-cache × profiles),
  run:

```bash
bash scripts/debug-leech-high-token-instability.sh \
  --checkpoint /home/c/Documents/code/DASHIg/LeechTransformer/data/best_model.pt \
  --prompt "Once upon a time Lila" \
  --tokens "8,16,24,32,40,48,64" \
  --kv-cache off,on \
  --profiles baseline,direct_only,gemm_only \
  --repeats 3 \
  --quiet
```

- Harness outputs:
  - `out/leech-debug-high-tokens/<timestamp>/summary.csv`
  - per-case run logs: `out/leech-debug-high-tokens/<timestamp>/<case>/run.log`
  - per-case kernel/journal snapshots and capture artifacts under each case directory

- there is currently no public "known-good" Leech GPU recommendation in this repo for Polaris hosts; CPU remains the only trustworthy output path here until the ROCm correctness issue is isolated or worked around.
- the focused `direct_only` token matrices are still useful as crash-behavior data, but they should not be read as proof of inference correctness.
- the current upstream-quality repro direction is no longer just "attention is unstable"; it is specifically "the attention flatten/layout path becomes nondeterministic on the extracted `5.7` ROCm stack while equivalent alternate layout materialization stays stable."
- if you hit an immediate fault, rerun with a shorter `--max_tokens`, and capture logs with:

```bash
WATCH_AMDGPU_DEVCOREDUMP=1 bash scripts/host-docker-python.sh \
  /home/c/Documents/code/DASHIg/LeechTransformer/scripts/run_inference.py ...
```

## Cachix Details

The current public cache settings are:

- cache URL: `https://gfx803-rocm.cachix.org`
- public key: `gfx803-rocm.cachix.org-1:UTaIREqPZa9yjY7hiMBYG556OrGR6WEhWPjqX4Us3us=`

If you use Nix, run this once:

```bash
cachix use gfx803-rocm
```

## Normal WhisperX transcription

If you want to try WhisperX directly without the RCA logging stack:

```bash
cd /home/c/Documents/code/__OTHER/gfx803_compat_graph/gfx803_flake_v1
nix develop .#whisperx
bash "$REPO_ROOT/scripts/host-docker-python.sh" -m whisperx /path/to/audio --model small --compute_type int8 --language en
```

That shell now defaults to:

- `HIP_LAUNCH_BLOCKING=1`
- `JOBLIB_MULTIPROCESSING=0`
- `TORCH_HOME=$REPO_ROOT/.cache/torch`

This is still not promoted as a host-stable workflow on long files, and it is
not yet a verified short-file baseline either. The newest normal-path failure
is a different class from the earlier RCA hang lane: the `.#whisperx` shell
was exposing Nix ROCm device-libs from `/nix/store` into the extracted host
runtime, which produced an `LLVM22` producer vs `LLVM19` reader mismatch while
building blit kernels. Treat this as a candidate normal path until a short-file
smoke passes cleanly after the shell surface is repaired.

If you want `--vad_method silero`, bootstrap the local `torch.hub` cache first:

```bash
cd /home/c/Documents/code/__OTHER/gfx803_compat_graph/gfx803_flake_v1
nix develop .#whisperx -c bash -lc 'bash "$REPO_ROOT/scripts/bootstrap-silero-vad-cache.sh"'
```

That seeds `snakers4/silero-vad` into the exact cache directories that
`torch.hub` checks (`$TORCH_HOME/hub/snakers4_silero-vad_main` and
`..._master`), so later WhisperX runs can use `--vad_method silero` without
trying to fetch the repo live from GitHub.

That allows Nix to fetch published extracted artifacts instead of recreating them locally.

Then restore the tracked extracted payloads into the clone:

```bash
bash scripts/restore-cachix-artifacts.sh
```

## Which Path To Choose

Choose the workflow based on your goal:

- if you want the clearest current setup: use `gfx803_flake_v1`
- if you want the most direct host runtime reuse: use `scripts/extract-docker-libs.sh` and `scripts/host-docker-python.sh`
- if you want to help test older math/runtime combinations: use `artifacts/rocm57/`
- if you want to help build a shareable path toward newer ROCm components without discarding the current working runtime shape: use `artifacts/rocm64-upgrade/`
- if you want to help test newer upstream ROCm attempts: use `artifacts/rocm-latest/`
- if you want to help on `Ollama`: use `artifacts/ollama_reference/`, but treat it as an active investigation rather than a finished host product
- if you want correct LeechTransformer text today: use CPU, not the current extracted ROCm host paths

## `6.4` Upgrade Lane

The current project direction for a reproducible newer stack is:

- keep the extracted `6.4` runtime as the control
- clone it into `artifacts/rocm64-upgrade/`
- swap newer components into that cloned lane incrementally
- run the smallest Leech repros after each swap instead of relying on large end-to-end runs

Initialize the lane with:

```bash
bash scripts/clone-rocm64-upgrade-lane.sh
```

Smoke-test the cloned lane with:

```bash
bash scripts/host-rocm64-upgrade-python.sh -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'
```

Current result on this machine:

- the cloned lane imports `torch 2.6.0+gitdae14f9`
- `torch.cuda.is_available()` returns `True`

Capture the current minimal repro set for a lane with:

```bash
bash scripts/capture-leech-minimal-repros.sh \
  --runner scripts/host-rocm64-upgrade-python.sh \
  --label rocm64-upgrade
```

That capture script records:

- live-process layout repro
- live-process layout repro with `HIP_LAUNCH_BLOCKING=1`
- saved-tensor standalone repro
- first-step logits probe

When `artifacts/rocm-latest/docker-venv/` is ready, the first planned swap is:

```bash
bash scripts/swap-rocm64-upgrade-python-from-latest.sh
bash scripts/swap-rocm64-upgrade-support-libs-from-latest.sh
bash scripts/swap-rocm64-upgrade-math-libs-from-latest.sh
bash scripts/sync-rocm64-upgrade-lib-compat-from-latest.sh
```

Then rerun the same capture command for `rocm64-upgrade`.

Current frozen captures:

- control `6.4`: `out/leech-min-repros/rocm64-control/2026-03-22T13-02-21`
- cloned `6.4`-upgrade pre-swap baseline: `out/leech-min-repros/rocm64-upgrade/2026-03-22T13-01-09`

Current swap status:

- pure `ROCm latest` now imports `torch 2.10.0+rocm7.2.0.gitb6ee5fde`
- that pure latest lane reports `torch.cuda.is_available() == False` on this Polaris host
- the cloned `6.4`-upgrade lane behaves the same way once its Python layer and full `lib-compat` are synced from latest
- intermediate failures were informative:
  - latest Python on top of old `6.4` libs failed on missing `ROCR_1` symbols
  - adding newer non-math support libs moved the failure into `hipsparse/rocsparse`
  - full latest `lib-compat` removed import-time linker failures, but not the GPU gate

So the current classification of the `6.4`-upgrade lane is:

- importable
- reproducible
- still GPU-gated on Polaris with the current latest userspace
- cloned `6.4`-upgrade: `out/leech-min-repros/rocm64-upgrade/2026-03-22T13-01-09`

The goal of this lane is reproducibility for others:

- repo-local artifact layout
- compatible with the existing Cachix publish/restore workflow
- explicit runner script instead of ad hoc local shell state

## Ollama Status

`Ollama` needs special wording because it is easy to overstate.

What is true:

- the reference source image is `robertrosenbusch/rocm6_gfx803_ollama:6.4.3_0.11.5`
- the patched `Ollama` binary and required runtime pieces are extracted into `artifacts/ollama_reference/`
- those extracted artifacts can be published to Cachix with the rest of the repo's extracted payloads

What is not yet true:

- the extracted host bundle is not yet a universally safe replacement for the Robert container
- this host has already shown a GPU reset / system crash while exercising the extracted host bundle

## Vulkan Note

The current extracted-runtime PyTorch build used in this repo does not expose a Vulkan backend:

- `torch 2.6.0+gitdae14f9`
- `torch.backends.vulkan -> None`

That means Vulkan is not a practical fallback compute path for LeechTransformer under the current PyTorch setup. Installing Vulkan-capable user-space through Steam may help other Vulkan applications, but it does not add a Vulkan execution backend to this torch runtime.

So if someone asks, "What is the safest GPU Ollama path today?" the answer is still:

- use the known-good Robert container if you need GPU `Ollama` right now
- use the extracted bundle only if you are helping validate and debug the host-port effort

## What To Report

Feedback is useful when it is specific. The most useful reports include:

- your GPU model
- Linux distribution
- kernel version
- whether you used the flake path, extracted `6.4` host path, `5.7` path, `ROCm 7+` path, or the extracted `Ollama` bundle
- whether the result was `works`, `partial`, `CPU fallback`, `hang`, `segfault`, or `full system reset`
- exact command run
- the last useful log lines you captured

If the GPU resets or the desktop corrupts after a run, capture evidence first:

```bash
bash scripts/capture-amdgpu-crash-artifacts.sh '10 minutes ago'
```

If the suspect surface is WhisperX itself, use the narrower RCA runner instead of only collecting a post-fact journal snapshot:

```bash
bash scripts/run-whisperx-rca-matrix.sh /path/to/sample.wav --language en
```

Default behavior:

- stages: `align`, `diarize`
- compute types: `int8`, `float16`
- `HIP_LAUNCH_BLOCKING`: `0`, `1`
- clean runs are discarded automatically
- suspicious runs keep their timestamped trace bundle

For one focused case, run:

```bash
STAGE=align WHISPERX_COMPUTE_TYPE=int8 \
bash scripts/trace-whisperx-rocprof.sh /path/to/sample.wav --language en
```

The wrapper now prefers `rocprofv3` automatically when it is available. To force a specific backend:

```bash
WHISPERX_PROFILER_BACKEND=rocprofv3 bash scripts/trace-whisperx-rocprof.sh /path/to/sample.wav --language en
WHISPERX_PROFILER_BACKEND=rocprof bash scripts/trace-whisperx-rocprof.sh /path/to/sample.wav --language en
```

For a reduced crash-capture run, prefer:

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

Exact-stage selection is still available for comparison runs, but it is no
longer the primary crash-lane recommendation for the long file.

Use `WHISPERX_ROCPROFV3_ENABLE_MEMORY_COPY_TRACE=1` when the active question is
whether the crash boundary is landing in a copy-heavy subwindow. Leave it off
for the lightest possible crash-capture run.

If stage-gated profiling is not sufficient, the wrapper still supports a
bounded fallback collection window through `WHISPERX_ROCPROFV3_COLLECTION_PERIOD`
and `WHISPERX_ROCPROFV3_COLLECTION_PERIOD_UNIT`.

Use the profiler for GPU execution-path RCA. If the problem is a host userspace
failure instead, such as `rocminfo` returning `HSA_STATUS_ERROR` or crashing in
the HSA stack, switch to `gdb` / `mcp-gdb` so the failing call path and loaded
libraries can be inspected directly.

The first debugger-backed `rocminfo` artifact now shows the current latest-HSA
failure is already present at `hsa_init()`, not only later in agent
enumeration:

- `out/rocminfo-gdb/2026-03-29T21-59-30/gdb-hsa-flow.txt`

That retained bundle contains:

- profiler output from `rocprofv3` or legacy `rocprof`
- ROCTX-marked stage boundaries from the WhisperX harness
- `events.jsonl` with stage start/end/error records and GPU memory snapshots
- `host-cpu.log` with periodic top-CPU snapshots from the host
- `heartbeat.log` with cheap periodic bundle-state snapshots that survive better than end-of-run profiler finalize
- `observer.log` with stronger periodic snapshots of run output, recent events, profiler file sizes, and current-boot kernel lines
- any `amdgpu` devcoredump captures that occurred during the run

Notes:

- `zkperf` is useful as a design reference for stage comparison and artifact collation, but it is not the active WhisperX RCA engine because it lacks ROCm and `amdgpu` fault capture
- if CPU usage spikes unexpectedly on `MP4` input, inspect `host-cpu.log`; `ffmpeg` decode is often the first hotspot and can mask the actual GPU stage boundary
- current WhisperX interpretation on this host:
  - the workload can use the GPU and progress into real work
  - the machine can still hit a KFD / reset crash at an unknown point under real compute pressure
  - the stronger current model is lower-level than a single WhisperX stage:
    - pinned host pages or GPU VM mappings can fail
    - queue or kernel progress can stall
    - `amdgpu` / KFD can then reset the device and lose VRAM
  - the currently confirmed failure class is queue/ring forward-progress loss, because the kernel repeatedly reports `ring gfx timeout`
  - the current strongest promoted boundary is the exposure point: D2H copy plus host wait
  - the first `Host active wait ... for -1 ns` is now the earliest reliable pre-crash sentinel on the retained userspace path
  - pinned host memory likely sits on that DMA path, but the current evidence fits stalled copy completion much better than successful delivery of bad data into host userspace
  - the current leading trigger classes remain lower-level: GPU VM or pinned-page failure, or DMA/copy-path stall
  - the current leading ownership hypothesis is ROCm/amdgpu instability on `gfx803` / Polaris under this mixed compute+copy path
  - that still does not promote copy overflow or a host-only crash as the root cause
  - the current remediation model is also layered:
    - VM-pressure patch shapes should move the first `-1 ns` later or remove it
    - queue-visibility patch shapes should surface failure earlier and more cleanly
    - D2H-relief patch shapes should weaken the copy/wait boundary if D2H completion pressure is the trigger
    - backend-substitution patch shapes should produce a more binary path split if the bug is library/kernel specific
  - the pressure model is now tighter too:
    - raw file length is only a proxy
    - segment size is a stronger direct control
    - the practical danger surface is closer to:
      - segment size × batch size × concurrency
    - smaller segment windows can be safer even when they produce more segments
  - compositor redraw, `alt-tab`, or other desktop activity may aggravate the failure, but that is still a hypothesis rather than a proven trigger
  - so WhisperX is not yet promoted here as a host-stable GPU workflow
  - the retained `2026-03-27` reduced repro had already completed `load_model` and `load_audio` and had entered `transcribe` before the crash boundary, so the current evidence does not isolate `align` as the first bad stage
  - later `2026-03-30` follow-up validated selected-region `align` profiling on shorter successful runs, but the main long-file crash moved earlier and died during `transcribe` with a final retained `DeviceToHost` copy, so the next long-file repro should use a compute-stage policy instead of another fixed stage name
  - the harness now prefers `librocprofiler-sdk-roctx` and emits explicit `roctxMarkA` run/stage markers as well as pushed ranges
  - a light verification bundle under `out/whisperx-trace/2026-03-30T07-54-25/` now shows those labels directly in `whisperx_marker_api_trace.csv`

Minimal discriminating matrix for the current WhisperX crash lane:

- baseline:
  - long file
  - `first_compute`
  - memory-copy trace on
- lower memory pressure:
  - shorter slice or shorter file that still reaches the compute path
- lower per-segment pressure:
  - same long file, but force smaller segment windows and keep `batch_size=1`
- lower copy-path perturbation:
  - same long file, same lane, memory-copy trace off
- alternate compute mix:
  - same long file and lane, different compute type if the stack supports it

Record per run:

- whether the first `-1 ns` host wait appears
- last concrete operation before that sentinel
- rough delay from first `-1 ns` to visible crash/reset
- whether `profiler/` retained anything
- whether kernel logs show timeout, BACO reset, VRAM loss, or VM fault

Read the matrix in layers:

- observed failure class:
  - does `ring gfx timeout` still appear?
- trigger class:
  - does lower memory pressure help?
  - do smaller segment windows on the same long file help?
  - does lower copy-path perturbation help?
- ownership hypothesis:
  - does changing compute type move the failure enough to implicate a specific
    ROCm/kernel/library path?

Read remediation attempts in the same layered way:

- VM-pressure patch shapes:
  - if they help, the first `-1 ns` should move later or disappear
- queue-visibility patch shapes:
  - if they help, failure may surface earlier but more explicitly
- D2H-relief patch shapes:
  - if they help, the copy/wait boundary should weaken
- backend-substitution patch shapes:
  - if they help, the ownership hypothesis narrows toward a specific
    ROCm/kernel/library path

## Lane matrix summary

The current RCA tooling is organized into five implementation lanes that must be tested before we promote a claim:

1. Baseline crash lane (`first_compute + memory-copy trace`) – anchors the retainable `-1 ns`/`ring gfx timeout` boundary.
2. Queue/visibility lane (`HIP_LAUNCH_BLOCKING=1`, explicit syncs) – surfaces queue forward-progress failure deterministically.
3. Pressure-control lane (shorter segment windows, `batch_size=1`, chunk reuse) – bounds per-segment working set even on long files.
4. DMA-light lane (copy trace disabled, staged or dedicated copy stream where possible) – isolates the copy path as the only variable.
5. Backend lane (alternate compute type or kernel mix) – constrains ownership to a specific ROCm/library path once pressure and queue effects are controlled.

Each lane records the same sentinels and metadata (`-1 ns`, timeout delta, last op, segment window, batch/concurrency) so the docs only promote the lane whose tooling visibly moves the sentinel behavior as expected.

Useful existing tools and controls for that layered read:

- runtime / env controls:
  - `HIP_LAUNCH_BLOCKING=1`
  - shorter or chunked input
  - smaller segment windows
  - alternate compute type
  - memory-copy trace off
- HIP / ROCm API patterns if the workload path becomes editable:
  - sync fences
  - event timing
  - pinned-buffer reuse
  - chunked D2H
  - dedicated copy stream
- kernel / driver controls:
  - `amdgpu.lockup_timeout=...`
  - `amdgpu.gpu_recovery=1`
  - previous-boot `journalctl -k`

For the full Polaris-oriented tool matrix, read:

- [POLARIS_STABILITY_BLUEPRINT.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/POLARIS_STABILITY_BLUEPRINT.md)

The repo now also carries a machine-readable execution-path admissibility
surface for bounded lower-level RCA claims:

- `schemas/execution_path_claim.schema.json`
- `artifacts/execution_path_claims/examples/`

For benchmark or drift reports, also include:

- `out/drift/benchmark-results.jsonl`
- `out/drift/benchmark-summary.json`

## Where To Send Feedback

Use the repository issue tracker:

- `https://github.com/chboishabba/gfx803_compat_graph/issues`

If you open an issue, describe:

- what you tried
- what hardware you used
- what happened
- what you expected to happen

## How To Contribute

Good contributions include:

- reproducing a setup on another Polaris machine
- confirming that a workflow works on another distro or kernel
- reporting a clean failure with logs and exact commands
- improving newcomer docs
- adding benchmark outputs
- helping isolate which runtime, kernel, or solver choice causes instability

If you want to contribute code or docs:

1. fork the repo
2. make the smallest focused change you can
3. include the commands you ran
4. include the exact machine or GPU you tested on
5. open a pull request against `main`

## Recommended Reading

If you need more detail after this guide:

- [README.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/README.md)
- [docs/START_HERE.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/START_HERE.md)
- [gfx803_flake_v1/README.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/gfx803_flake_v1/README.md)
- [POLARIS_STABILITY_BLUEPRINT.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/POLARIS_STABILITY_BLUEPRINT.md)
  - includes the current Polaris ROCm sanity checklist for ring-timeout /
    `-1 ns` / reset-class failures
