# gfx803 Nix flake v1

This is the clearest current Nix entrypoint for the repository.

It is intended to replace ad hoc container juggling with a smaller set of reproducible shells and apps, while still acknowledging that some runtime pieces currently come from extracted artifacts rather than a pure Nix build.

## What this flake gives you

- `.#base`: host visibility and ROCm sanity checks
- `.#pytorch`: drift-testing shell
- `.#gfx803-pytorch-stack`: frozen control PyTorch stack
- `.#gfx803-pytorch-stack-upgrade`: primary short-term upgrade PyTorch stack with the same frozen Python/framework layer and a preserved old-HSA/HIP ABI lane underneath
- `.#gfx803-pytorch-framework-rebuild`: first Nix-owned framework rebuild shell
- `.#rocmNative-franken`: newer runtime plus extracted `5.7` math payload
- `.#comfyui`: app shell with low-VRAM defaults
- `.#whisperx`: app shell for the extracted host WhisperX path, with `HIP_LAUNCH_BLOCKING=1` and a reduced Nix ROCm surface so the shell does not leak incompatible `/nix/store` device-libs into the extracted runtime
- `nix run .#verify-host`
- `nix run .#drift-matrix`
- `nix run .#community-bundle`
- `nix run .#framework-rebuild`
- `nix run .#release-manifest`
- `nix run .#update-graph`

## Current expectations

- This flake is the preferred direction for the repo
- It is not yet the entire project state in one command
- The flake now advertises the public `gfx803-rocm` Cachix cache for published extracted artifact sets
- The `rocmNative-franken` shell depends on extracted `5.7` artifacts living at `../artifacts/rocm57/`
- The runners look for torch in this order: `TORCH_PYTHON`, the extracted `../docker-venv/` path via `../scripts/host-docker-python.sh`, `../.venv/bin/python`, then `../venv/bin/python`
- The standalone extracted `5.7` host path now imports torch correctly via `../scripts/host-rocm57-python.sh`
- The `rocmNative-franken` shell still needs follow-up because the workload crashes before a full drift-matrix result is emitted
- Separate `ROCm 7+` extracted-host experiments should live under `../artifacts/rocm-latest/`, outside the flake shells, until one proves stable enough to promote
- The extracted `6.4` host path now covers torch, WhisperX, and ComfyUI, but it is still not a GPU Ollama replacement
- The intended next shell split is:
  - `.#gfx803-pytorch-stack` as the untouched control lane
  - `.#gfx803-pytorch-stack-upgrade` as the first practical ROCm-upgrade lane using the same frozen extracted Python/framework layer
- Current measured status:
  - `.#gfx803-pytorch-stack` follows the known-working extracted `6.4` Python/framework path
  - `.#gfx803-pytorch-stack-upgrade` now points at the preserved old-HSA/HIP ABI lane and treats the earlier safe-support lane as an implementation detail of that direction
  - the fully upgraded latest-class userspace is still a separate experiment because Polaris breaks at the newer HSA/HIP seam before rebuilt torch can use it
  - `.#framework-rebuild` / `.#gfx803-pytorch-framework-rebuild` now default to the preserved old-ABI upgrade lane and should use an extracted old-ABI ROCm SDK root rather than leaking `/opt/rocm` latest libs

## Fastest checks

Verify the host first:

```bash
nix develop .#base
verify-gfx803-host
```

Run the drift matrix:

```bash
nix develop .#pytorch
run-drift-matrix
update-compat-graph
```

The benchmark runner now emits standardized records to `../out/drift/benchmark-results.jsonl`.

## Normal WhisperX use

For plain transcription rather than RCA tracing, use the WhisperX shell:

```bash
nix develop .#whisperx
bash "$REPO_ROOT/scripts/host-docker-python.sh" -m whisperx /path/to/audio --model small --compute_type int8 --language en
```

That shell currently defaults to:

- `JOBLIB_MULTIPROCESSING=0`
- `HIP_LAUNCH_BLOCKING=1`
- `TORCH_HOME=$REPO_ROOT/.cache/torch`

The intent is pragmatic stability on Polaris, not maximum throughput.

This path is still only a candidate normal path until a short-file smoke passes
cleanly on the current host. The immediate failure we just isolated was not the
earlier WhisperX RCA hang class; it was a Nix/extracted-runtime mix where the
shell exposed `/nix/store` ROCm device-libs (`LLVM 22`) to the extracted
runtime (`LLVM 19` reader), which then failed while building blit kernels.

If you want `--vad_method silero`, seed the local `torch.hub` cache first:

```bash
bash "$REPO_ROOT/scripts/bootstrap-silero-vad-cache.sh"
```

That bootstrap script populates the exact `torch.hub` cache directories that
WhisperX expects for `snakers4/silero-vad`, so later runs do not need live
GitHub access or Python SSL trust to fetch the VAD repo at runtime.

## `5.7` payload workflow

Before using `.#rocmNative-franken`, populate the extracted artifacts:

```bash
bash ../scripts/extract-rocm57-artifacts.sh
```

That should create:

- `../artifacts/rocm57/rocblas-library`
- `../artifacts/rocm57/miopen-db`
- `../artifacts/rocm57/meta/info.txt`

Then:

```bash
nix develop .#rocmNative-franken
run-drift-matrix
```

The purpose of this shell is to test whether extracted `5.7` math payloads improve behavior when combined with the newer runtime-oriented environment.

If you want to compare against a fuller extracted `5.7` host runtime instead of the franken shell, use `../scripts/extract-rocm57-artifacts.sh` and then `../scripts/host-rocm57-python.sh`.

If you want to probe a separate moving-target `ROCm 7+` host extraction, use `../scripts/extract-rocm-latest-artifacts.sh` and then `../scripts/host-rocm-latest-python.sh`.

## Why the flake still looks hybrid

The current practical constraint is that ROCm-enabled PyTorch from `nixpkgs` has been brittle for this hardware path. The repo therefore separates:

- runtime and validation tooling in Nix
- torch and some known-good artifacts from extracted environments

At the moment, the missing piece is Ollama:

- the stock host `ollama` binary starts under the extracted `6.4` runtime but still discovers only CPU
- the previously known-good GPU path still comes from the patched Robert container lineage
- a real Nix-first replacement therefore still needs an Ollama-specific port, not just the general PyTorch-side extracted runtime

If you want the checklist for turning the original working Docker recipe into a modular Nix-owned graph, read [docs/NIX_MIGRATION_CHECKLIST.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/NIX_MIGRATION_CHECKLIST.md).

## Cachix

The repo binary cache is:

- `https://gfx803-rocm.cachix.org`
- key: `gfx803-rocm.cachix.org-1:UTaIREqPZa9yjY7hiMBYG556OrGR6WEhWPjqX4Us3us=`

Use it directly with:

```bash
cachix use gfx803-rocm
```

That is deliberate. Stabilizing the test loop is more important than forcing purity too early.

## Not implemented here yet

- automatic artifact extraction as part of flake evaluation
- a finished publish pipeline for latest patched environments
- a full generated ROCm-version-by-framework matrix

Those are discussed in the wider project context, but they are not complete in this flake today.
