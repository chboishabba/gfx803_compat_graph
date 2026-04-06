# Start Here

This page is for someone who has just opened the project and wants the shortest possible path to understanding what matters.

If you need one document to send to another person, start with [docs/USER_GUIDE.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/USER_GUIDE.md).

## What problem this project is solving

AMD Polaris cards such as the RX 580 use `gfx803`. Modern ROCm releases no longer treat that hardware as a normal supported target, so getting useful ML workloads running means combining:

- compatibility shims
- older working runtime pieces
- stability flags
- careful validation

This repo is where those pieces are being tested and documented.

## What is already true

- The repo contains previously extracted `6.4` runtime artifacts in `lib-compat/`
- The repo contains a previously extracted Python environment in `docker-venv/`
- The more current reproducible workflow is in `gfx803_flake_v1/`
- The repo now has a public Cachix binary cache at `https://gfx803-rocm.cachix.org` for the extracted artifact sets
- The extracted `6.4` host path now covers torch and ComfyUI without needing the old full Docker at runtime
- WhisperX can launch on the same runtime and use the GPU, but on this machine it should currently be treated as an RCA/reproducer surface because real runs can still trigger KFD / reset instability
- The patched Ollama GPU path is extracted to `artifacts/ollama_reference/` and published with the other extracted artifacts, but host stability is still under investigation
- The stock host `ollama` binary still falls back to CPU; the upstream Robert image remains the safer practical GPU option until the extracted host bundle is fully stabilized
- The `5.7` payload artifacts are now extracted into `artifacts/rocm57/` and are usable as a standalone host artifact path via `scripts/host-rocm57-python.sh`
- A separate `ROCm 7+` experiment lane now writes into `artifacts/rocm-latest/` so newer-runtime tests do not overwrite the `6.4` or `5.7` baselines
- The repo now has initial CI validation scaffolding, but not a finished publish pipeline yet

## If you only do one thing

Run the host verification step first:

```bash
cd gfx803_flake_v1
nix develop .#base
verify-gfx803-host
```

That tells you whether the machine can see the GPU and ROCm stack at all.

## The three practical paths

### Path A: Reuse the extracted `6.4` environment

Use this if you want the path closest to the currently known-good setup.

```bash
bash scripts/extract-docker-libs.sh
source scripts/polaris-env.sh
./scripts/host-docker-python.sh tests/bug_report_mre.py
```

This path now defaults to the zero-drift `direct_only` solver profile.
It also covers the currently validated host-side torch and ComfyUI surfaces.
WhisperX is available for RCA on the same runtime, but it is not yet promoted as a stable host GPU workflow.

### Path B: Use the Nix entrypoints

Use this if you want the clearest maintained workflow.

```bash
cd gfx803_flake_v1
nix develop .#pytorch
run-drift-matrix
```

If the repo already has `docker-venv/`, the runner can use that extracted Python runtime automatically.

The resulting benchmark records land in:

- `out/drift/benchmark-results.jsonl`
- `out/drift/benchmark-summary.json`

### Path C: Prepare the `5.7` math payload

Use this if you want either a standalone extracted `5.7` host runtime or the mixed setup where newer runtime pieces are combined with extracted `5.7` math artifacts.

```bash
bash scripts/extract-rocm57-artifacts.sh
bash scripts/host-rocm57-python.sh -c 'import torch; print(torch.cuda.is_available())'
cd gfx803_flake_v1
nix develop .#rocmNative-franken
run-drift-matrix
```

By default, this writes only under [artifacts/rocm57](/home/c/Documents/code/__OTHER/gfx803_compat_graph/artifacts/rocm57). If you override the output path with `ROCM57_OUTDIR` or a positional directory argument, that is an explicit non-default choice and you are responsible for cleaning that location afterward.

### Path D: Try a separate `ROCm 7+` host extraction

Use this if you want to probe a newer upstream ROCm/PyTorch image without disturbing the current `6.4` or `5.7` artifacts.

```bash
bash scripts/extract-rocm-latest-artifacts.sh
bash scripts/host-rocm-latest-python.sh -c 'import torch; print(torch.__version__)'
```

## Important caveat

If you specifically need GPU Ollama today, do not assume the stock host `ollama` binary is equivalent to the old Robert Docker path.
The stock host binary starts under the extracted `6.4` runtime, but it currently discovers only CPU.
The extracted patched reference bundle exists, but on this host it has also triggered GPU reset / system instability during follow-up validation.
That means Ollama is still the main remaining runtime surface that does not yet have a fully settled host replacement for the patched Robert container.
In practical terms, re-downloading the already-built Robert Ollama image is still the safer path than relying on the host bundle if you need GPU Ollama immediately.

## Cache note

If you are using Nix on another machine, enable the repo cache first:

```bash
cachix use gfx803-rocm
```

That allows Nix to fetch published extracted artifacts from Cachix instead of requiring them to be recreated locally.

## Files worth reading next

- [docs/USER_GUIDE.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/USER_GUIDE.md)
- [README.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/README.md)
- [gfx803_flake_v1/README.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/gfx803_flake_v1/README.md)
- [POLARIS_STABILITY_BLUEPRINT.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/POLARIS_STABILITY_BLUEPRINT.md)
- [TODO.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/TODO.md)
