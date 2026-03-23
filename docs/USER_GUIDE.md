# User Guide

This is the document to send to someone who just wants to know what this project does, how to get started, what currently works, and where to report results.

## What This Project Is

This repository is a practical compatibility workspace for older AMD Polaris GPUs such as the RX 470, RX 480, RX 570, RX 580, and RX 590.

Those GPUs use the `gfx803` architecture. Modern ROCm releases no longer support `gfx803` cleanly, so this project keeps track of working runtime combinations, extracted artifact bundles, safety flags, and benchmark results.

The short version:

- `torch` works on the extracted `ROCm 6.4` host path
- `WhisperX` and related Python workflows are available through the same extracted host runtime
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
- `WhisperX` via extracted runtime
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
- `WhisperX` via the extracted `6.4` host runtime
- `ComfyUI` via the extracted `6.4` host runtime
- extracted `5.7` artifacts for comparison and mixed-runtime experiments
- a separate `ROCm 7+` experiment lane for newer upstream attempts
- a `6.4`-derived upgrade lane for incrementally testing newer components while preserving the current working runtime shape
- an extracted patched `Ollama` reference bundle for investigation and packaging work

## Current Reality

Please use this project with the following expectations:

- the extracted `6.4` host path is the current baseline
- the public binary cache is `https://gfx803-rocm.cachix.org`
- the `5.7` and `ROCm 7+` paths are experiment lanes, not the default recommendation
- the preferred route toward a more current reproducible stack is now a cloned `6.4` upgrade lane rather than a direct switch to pure `ROCm latest`
- the extracted `Ollama` reference bundle now extracts correctly and is published to Cachix, but it is not yet a settled "safe daily driver" host path
- on this host, the extracted `Ollama` bundle can start and then trigger a GPU reset / system instability; that investigation is still open
- if you need GPU `Ollama` immediately, the already-working Robert container lineage is still the safer fallback than the host bundle

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
- `WhisperX`
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
