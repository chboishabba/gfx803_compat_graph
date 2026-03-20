# gfx803 Nix flake v1

This is the clearest current Nix entrypoint for the repository.

It is intended to replace ad hoc container juggling with a smaller set of reproducible shells and apps, while still acknowledging that some runtime pieces currently come from extracted artifacts rather than a pure Nix build.

## What this flake gives you

- `.#base`: host visibility and ROCm sanity checks
- `.#pytorch`: drift-testing shell
- `.#rocmNative-franken`: newer runtime plus extracted `5.7` math payload
- `.#comfyui`: app shell with low-VRAM defaults
- `.#whisperx`: app shell with WhisperX-oriented defaults
- `nix run .#verify-host`
- `nix run .#drift-matrix`
- `nix run .#community-bundle`
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
