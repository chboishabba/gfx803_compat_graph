# Changelog

## 2026-03-20

- added `docs/USER_GUIDE.md` as the single shareable setup, status, and contribution guide for non-specialist users
- updated `README.md` and `docs/START_HERE.md` so they point newcomers at the new guide first
- corrected the documented Ollama status: the extracted `artifacts/ollama_reference/` bundle now exists and is published through the artifact workflow, but host stability is still under investigation after a GPU reset / system crash during follow-up validation on this machine
- updated `TODO.md` so the next Ollama host-validation step is explicit after the recent extraction and launcher fixes

Why:

- the repo needed one document that could be handed to users without asking them to reconstruct the workflow from multiple notes
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
