# Changelog

## 2026-03-21

- updated `README.md` and `docs/USER_GUIDE.md` to match the current LeechTransformer reality on this machine: a short GPU smoke run still selects `device=cuda`, while longer runs remain a guarded ROCm compatibility lane rather than a declared stable baseline
- documented the current long-token mitigation in the public runbook: on this ROCm path, the active inference script disables `top_p` sampling above `36` generated tokens to avoid the faulting nucleus-sampling path
- updated `TODO.md` so the next LeechTransformer step is explicit: rerun the higher-token matrix with the current guardrails and then decide whether the public recommendation should move beyond `--max_tokens <= 36`

Why:

- the repo docs had fallen slightly behind the actual operational state of the LeechTransformer path
- short GPU runs are now good enough to document as working, but the longer-token path still needs measured re-baselining before it should be presented as solved

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
