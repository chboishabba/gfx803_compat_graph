# TODO

## Immediate

- Keep a single shareable user guide current for setup, cache usage, available surfaces, and contribution/reporting instructions ✅
- Keep a plain-language clone-to-ready onboarding section in the public guide for non-technical users ✅
- Record the extracted `6.4` host path as covering torch, WhisperX, and ComfyUI, but not host GPU Ollama ✅
- Verify that the published `gfx803-rocm` Cachix entries can be consumed cleanly from another machine or a clean local profile
- Treat the Robert `6.4` Ollama image as the short-term practical GPU fallback until the Ollama-specific port is reproduced outside the full container ✅ (reference bundle extracted and published at `artifacts/ollama_reference/`, host stability still under investigation)
- Port the previously working Robert `6.4` Ollama GPU path into a smaller extracted or Nix-managed workflow so the full Robert container is no longer required for Ollama (in progress: reference bundle + host launcher + flake shell exist)
- Re-test the extracted `artifacts/ollama_reference/` host path after the AMDGPU `libdrm` copy fix and `HSA_ENABLE_SDMA=0` host launcher change, because the last host run triggered a GPU reset / PC crash
- Preserve the current `5.7` extracted host path as a separate reusable artifact alongside the top-level extracted `6.4` baseline
- Fix LeechTransformer inference checkpoint loading on ROCm hosts (`__main__.LeechConfig` unpickle path) and document operational GPU limits for stable runs ✅
- Re-run the LeechTransformer higher-token matrix after the ROCm `top_p` guardrail and harness fault-classification fix, then update the documented stable token window from measured results ✅
- Decide whether guarded long-token runs (`top_p` forced off on ROCm above `36` tokens) are good enough for the public default, or whether the runbook should remain capped at `--max_tokens <= 36` ✅ (current direct-only measured guidance is now `<= 64`)
- Commit and push the helper scripts already referenced by the docs (`scripts/debug-leech-high-token-instability.sh`, `scripts/run-gfx803-ollama-container.sh`, `scripts/watch-amdgpu-devcoredump.sh`, and the tracing wrappers) so a fresh clone actually contains the documented workflows ✅
- Extend the LeechTransformer matrix beyond `64` tokens and across additional prompts/profile families before broadening the public guidance beyond the currently measured `direct_only` path
- Run several `ROCm 7+` extracted-host smoke attempts under `artifacts/rocm-latest/` before resuming `5.7` drift/noise work
- Re-pull `itir:latest` locally so the `6.4` extraction flow is runnable again after the Docker reset
- Verify `gfx803_flake_v1` entrypoints on the current host after the Docker reset
- Investigate the `rocmNative-franken` segmentation fault that occurs before the drift matrix can emit results
- Capture a minimal repro for the franken-shell crash with the extracted `5.7` payload
- Run the same standardized benchmark matrix through `scripts/host-rocm57-python.sh` after the `ROCm 7+` attempt window is complete
- Expand the benchmark record schema to include ComfyUI workflow/image bundle fields directly once the first community workflow is finalized

## Documentation

- Keep `6.4`, `5.7`, and `ROCm 7+` artifact paths clearly separated in newcomer docs and scripts
- Keep the Cachix cache name, URL, and public key documented anywhere Nix entrypoints are presented
- Document explicitly that Ollama GPU is still the one remaining surface tied to the Robert container lineage while the host `6.4` extraction now covers torch, WhisperX, and ComfyUI
- Document explicitly that, for now, re-downloading the known-good Robert Ollama image is still the faster practical route than rebuilding that patched stack locally
- Keep the new shareable user guide aligned with README and START_HERE whenever the status of Ollama host stability changes
- Keep the top-level README focused on newcomer orientation instead of mixing old and new workflows
- Record which image and tag were used for the latest `5.7` extraction in `artifacts/rocm57/meta/info.txt`
- Add a short results note once the first `ROCm 7+` smoke attempt completes and once the refreshed `5.7` drift run completes
- Document the first accepted community benchmark workflow IDs and required artifact set
- Add/maintain a LeechTransformer runbook with exact command line, known-good token window, and kv-cache warning for Polaris hosts ✅

## Deferred

- Decide whether the top-level `flake.nix` should be updated to match `gfx803_flake_v1` or explicitly marked legacy
- Add repo-level CI once there is a stable GPU-backed execution target
- Promote the compatibility graph outputs into a more obvious summary view for non-technical readers
