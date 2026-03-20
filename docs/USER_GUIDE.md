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

## What You Can Use Today

These are the practical surfaces currently exposed by the repo:

- `torch` via the extracted `6.4` host runtime
- `WhisperX` via the extracted `6.4` host runtime
- `ComfyUI` via the extracted `6.4` host runtime
- extracted `5.7` artifacts for comparison and mixed-runtime experiments
- a separate `ROCm 7+` experiment lane for newer upstream attempts
- an extracted patched `Ollama` reference bundle for investigation and packaging work

## Current Reality

Please use this project with the following expectations:

- the extracted `6.4` host path is the current baseline
- the public binary cache is `https://gfx803-rocm.cachix.org`
- the `5.7` and `ROCm 7+` paths are experiment lanes, not the default recommendation
- the extracted `Ollama` reference bundle now extracts correctly and is published to Cachix, but it is not yet a settled "safe daily driver" host path
- on this host, the extracted `Ollama` bundle can start and then trigger a GPU reset / system instability; that investigation is still open
- if you need GPU `Ollama` immediately, the already-working Robert container lineage is still the safer fallback than the host bundle

## Quick Setup

If you already use Nix, this is the fastest low-friction start:

```bash
cachix use gfx803-rocm
git clone https://github.com/chboishabba/gfx803_compat_graph.git
cd gfx803_compat_graph/gfx803_flake_v1
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
bash scripts/extract-docker-libs.sh
source scripts/polaris-env.sh
./scripts/host-docker-python.sh tests/bug_report_mre.py
```

That path is the practical host entrypoint for:

- `torch`
- `WhisperX`
- `ComfyUI`

## Cachix Details

The current public cache settings are:

- cache URL: `https://gfx803-rocm.cachix.org`
- public key: `gfx803-rocm.cachix.org-1:UTaIREqPZa9yjY7hiMBYG556OrGR6WEhWPjqX4Us3us=`

If you use Nix, run this once:

```bash
cachix use gfx803-rocm
```

That allows Nix to fetch published extracted artifacts instead of recreating them locally.

## Which Path To Choose

Choose the workflow based on your goal:

- if you want the clearest current setup: use `gfx803_flake_v1`
- if you want the most direct host runtime reuse: use `scripts/extract-docker-libs.sh` and `scripts/host-docker-python.sh`
- if you want to help test older math/runtime combinations: use `artifacts/rocm57/`
- if you want to help test newer upstream ROCm attempts: use `artifacts/rocm-latest/`
- if you want to help on `Ollama`: use `artifacts/ollama_reference/`, but treat it as an active investigation rather than a finished host product

## Ollama Status

`Ollama` needs special wording because it is easy to overstate.

What is true:

- the reference source image is `robertrosenbusch/rocm6_gfx803_ollama:6.4.3_0.11.5`
- the patched `Ollama` binary and required runtime pieces are extracted into `artifacts/ollama_reference/`
- those extracted artifacts can be published to Cachix with the rest of the repo's extracted payloads

What is not yet true:

- the extracted host bundle is not yet a universally safe replacement for the Robert container
- this host has already shown a GPU reset / system crash while exercising the extracted host bundle

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
