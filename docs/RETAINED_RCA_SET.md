# Retained RCA Set

This is the smallest current retained reference set for the gfx803 patcher/RCA
thread. It keeps one working control case, one HIP/HSA failure case, and one
WhisperX crash case, each tied back to the repo's existing claim/evidence
surfaces.

This retained set is intentionally centered on the runtime-boundary and
reset-boundary lanes. It does not try to fully retain the older
workload-correctness RCA for ComfyUI drift/noise; that historical line is
tracked separately through the archive-backed notes referenced below.

Use this set when deleting bulk probe trees, rebuild workdirs, or repeated
trace bundles. It is intentionally narrow: causal diversity over volumetric
redundancy.

Historical note:

- an archive-backed older RCA thread also exists under the local ChatGPT
  archive as `ROCm RX580 noise issue`
  (`online_thread_id = 69b74f65-2644-8399-8842-7126424643e3`)
- that thread is relevant for ComfyUI noise, stateful drift, solver flapping,
  and first-corrupted-tensor methodology
- it does mention `bf16` / `bfloat16`, but only as minor side leads rather
  than a primary RCA lane
- the dominant historical signal there is numerical drift / corruption, not a
  standalone `bf16` compatibility story

## 1. Working Control Case

- case label: `control-6.4`
- purpose: current promoted working baseline for extracted ROCm userspace
- canonical claim:
  - `out/lane_claims/control-6.4.compatibility_claim.json`
- supporting observation:
  - `out/lane_claims/control-6.4.execution_observation.json`
- primary runtime refs:
  - `lib-compat/`
  - `docker-venv/`

Safe reading:

- this is the current practical baseline for torch import, ComfyUI, and
  extracted userspace bring-up on this machine
- `import_ok == true`
- `gpu_visible == true`

Do not over-read:

- this does not promote WhisperX as host-stable
- this does not promote Ollama host stability
- this does not prove end-to-end ROCm correctness for all workloads

## 2. HIP/HSA Failure Case

- case label: `rocminfo-latest-hsa-init-failure`
- purpose: retained userspace-debug anchor for the HIP/HSA ABI seam
- canonical incident note:
  - `docs/INCIDENT_2026-03-29_ROCMINFO_HSA_INIT_FAILURE.md`
- canonical execution-path claim:
  - `artifacts/execution_path_claims/examples/rocminfo-latest-hsa-init-failure.json`
- primary debugger artifact:
  - `out/rocminfo-gdb/2026-03-29T21-59-30/gdb-hsa-flow.txt`

Safe reading:

- latest-class HSA breaks Polaris `rocminfo` enumeration at or before
  `hsa_init` on this machine
- the failure is present under userspace initialization before agent iteration

Do not over-read:

- this does not identify the internal ROCR/HSA root cause inside `hsa_init`
- this does not prove torch GPU usability is restored by fixing only this fault
- this is not a GPU reset claim

## 3. WhisperX Crash Case

- case label: `whisperx-transcribe-reset-boundary`
- purpose: retained reset-boundary anchor for the WhisperX host-reset class
- canonical incident note:
  - `docs/INCIDENT_2026-03-27_WHISPERX_TRANSCRIBE_RESET.md`
- canonical execution-path claim:
  - `artifacts/execution_path_claims/examples/whisperx-transcribe-reset-boundary.json`
- primary retained trace:
  - `out/whisperx-rca-matrix/2026-03-27T22-56-54/stage=align__compute=int8__blocking=0/traces/2026-03-27T22-56-54/harness/events.jsonl`
- summary surface:
  - `out/whisperx-rca-matrix/2026-03-27T22-56-54/summary.csv`

Safe reading:

- the reduced WhisperX repro reaches active GPU work
- `load_model` and `load_audio` complete
- `transcribe` starts before the reset/crash boundary

Do not over-read:

- this does not isolate `align` as the first bad stage
- this does not identify the specific kernel or queue activity that triggers the
  reset
- this is reset-boundary evidence, not a stable workflow claim

## Retention Rule

If bulk cleanup is needed, retain at least these three case anchors plus the
runtime directories referenced by the working control case. Everything else
should justify itself as a distinct failure class, not merely another run of
the same class.
