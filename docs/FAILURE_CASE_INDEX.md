# FAILURE_CASE_INDEX

## Purpose

Canonical list of distinct failure classes used to decide:

- what evidence must be retained
- what bulk can be safely deleted

## A. Minimal retained set (must keep)

### 1. `rocminfo-latest-hsa-init-failure`

- Latest HSA fails at or before `hsa_init` on Polaris.
- Track: `RCA_TRACK_1` (runtime-boundary)
- Refs:
  - `docs/INCIDENT_2026-03-29_ROCMINFO_HSA_INIT_FAILURE.md`
  - `docs/RETAINED_RCA_SET.md`
  - `artifacts/execution_path_claims/examples/rocminfo-latest-hsa-init-failure.json`

### 2. `control-6.4`

- Working baseline: coherent extracted ROCm `6.4` userspace.
- Track: `RCA_TRACK_1` (runtime-boundary)
- Refs:
  - `out/lane_claims/control-6.4.compatibility_claim.json`
  - `out/lane_claims/control-6.4.execution_observation.json`
  - `lib-compat/`
  - `docker-venv/`

### 3. `whisperx-transcribe-reset-boundary`

- Reaches active GPU work, then reset/crash boundary.
- Track: `RCA_TRACK_3` (load/stability)
- Refs:
  - `docs/INCIDENT_2026-03-27_WHISPERX_TRANSCRIBE_RESET.md`
  - `docs/RETAINED_RCA_SET.md`
  - `artifacts/execution_path_claims/examples/whisperx-transcribe-reset-boundary.json`

## B. Covered (keep references, not full bulk)

### 4. `latest-hsa-hybrid-gpu-visibility-gap`

- `rocminfo` can be restored, but Torch remains unusable.
- Track: `RCA_TRACK_1` (runtime-boundary)
- Refs:
  - `artifacts/execution_path_claims/examples/latest-hsa-hybrid-gpu-visibility-gap.json`
  - `out/lane_claims/diag-latest-hybrid.compatibility_claim.json`
  - `docs/PATCHER_RULE_V1.md`

### 5. `whisperx-align-gpu-hang-no-prof`

- GPU hang without profiler; profiler changes behavior.
- Track: `RCA_TRACK_3` (load/stability)
- Refs:
  - `docs/INCIDENT_2026-03-30_WHISPERX_ALIGN_GPU_HANG_AND_ROCPROFV3_SUCCESS.md`
  - `artifacts/execution_path_claims/examples/whisperx-align-gpu-hang-no-prof.json`

### 6. `comfyui-drift-noise-corruption`

- Stateful drift, solver flapping, and `fp16`/layout-related instability.
- Track: `RCA_TRACK_2` (workload-correctness)
- Refs:
  - `README.md`
  - `docs/START_HERE.md`
  - `docs/PATCHER_RULE_V1.md`
  - `docs/RETAINED_RCA_SET.md`
  - archive thread `69b74f65-2644-8399-8842-7126424643e3`

### 7. `ollama-kfd-reset`

- Host GPU reset under Ollama workloads.
- Track: `RCA_TRACK_3` (load/stability)
- Ref:
  - `docs/INCIDENT_2026-03-20_OLLAMA_MISTRAL_KFD_RESET.md`

## Cleanup rule

> A directory can be deleted if and only if it does **not** contain the sole retained evidence for any failure class listed above.

Practical interpretation:

- repeated probes and matrices can be deleted
- rebuild workdirs can be deleted
- duplicate traces can be deleted
- anything referenced above should be kept or distilled first

## Validation contract (`PATCHER_RULE_V1`)

A runtime is valid if:

- `rocminfo` succeeds
- `torch.cuda.is_available() == True`

This guarantees runtime coherence, not workload correctness.

## Why this matters

With this file in place, cleanup becomes:

> Does this path contribute unique evidence to a failure class?

- Yes: keep it.
- No: delete it.

That removes guesswork from later cleanup passes.
