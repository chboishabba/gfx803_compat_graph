# Incident: 2026-03-27 WhisperX Reset During Active GPU Work

This note captures the retained evidence from the reduced WhisperX RCA run that
preceded the short crash boot on `2026-03-27`.

## Why this matters

This incident is stronger than a generic "WhisperX crashed" note because the
retained bundle shows the run had already entered real GPU work before the host
reset class landed.

It does **not** prove that `align` is the first bad stage.

## Correlated evidence

- retained RCA bundle root:
  - `out/whisperx-rca-matrix/2026-03-27T22-56-54/`
- retained harness events:
  - `out/whisperx-rca-matrix/2026-03-27T22-56-54/stage=align__compute=int8__blocking=0/traces/2026-03-27T22-56-54/harness/events.jsonl`
- retained run summary:
  - `out/whisperx-rca-matrix/2026-03-27T22-56-54/summary.csv`

User-reported host-side evidence from the same failure window:

- fresh system dump:
  - `/var/log/amdgpu-devcoredumps/card1-devcoredump-20260327-231042.bin`
- short crash boot:
  - `2026-03-27 23:08:00 AEST` to `2026-03-27 23:11:04 AEST`

## Narrowest safe current reading

From the retained `events.jsonl`:

- `run_start` at `2026-03-27T22:57:05+1000`
- `load_model` started at `22:57:05` and ended at `22:57:20`
- `load_audio` started at `22:57:20` and ended at `22:57:37`
- `transcribe` started at `22:57:37`

What is missing is also important:

- no later `stage_end` for `transcribe`
- no later `run_end`
- no recorded `align` start event in the retained bundle

## Implications

This lets us say:

- the reduced WhisperX repro can still trigger the same host reset/crash class
- the run had already moved past startup/import and audio loading
- the earliest retained bad boundary for this run is **after `transcribe`
  begins**

This does **not** let us say:

- that `align` specifically is the first bad stage
- that the root cause is isolated to one WhisperX substage rather than broader
  ROCm / KFD / memory-pressure instability

## Current working model

The stronger current model is:

- WhisperX is a reliable GPU-workload reproducer for the host reset class
- the failure is not just startup noise or pure decode overhead
- the host can survive into active transcription work and still later hit the
  reset path
- the real unresolved question is what ROCm kernel / queue activity is in
  flight immediately before the reset

## Consequence for repo claims

Repo-facing wording should currently distinguish:

- `torch` import / GPU visibility
- WhisperX can launch and use the GPU
- WhisperX is **not yet** a promoted stable host workflow
- earliest retained bad boundary from this run: after `transcribe` starts

## Next action

Use the profiler-enabled WhisperX path to answer the next-level question:

- get a retained run with real `rocprofv3` or repaired legacy `rocprof`
  artifacts
- correlate those profiler artifacts with ROCTX stage markers and any
  `amdgpu` / devcoredump evidence

Until that lands, the safe claim remains:

- WhisperX is a useful RCA/reproducer surface
- not a proven stage-specific fault
- not a promoted host-stable GPU workflow
