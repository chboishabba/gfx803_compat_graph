# Incident: 2026-03-20 Ollama Mistral GPU Reset

This note captures the kernel-side evidence from the `ollama run mistral` crash observed on `2026-03-20`.

## Observed behavior

- `ollama run mistral` produced a good reply
- near the end of output, the desktop glitched into a pink/green checkerboard pattern
- the machine recovered, but the GPU went through a reset path

## Saved artifacts

The immediate capture for this incident is in:

- `out/crashlogs/2026-03-20T13-55-29/kernel-journal.txt`
- `out/crashlogs/2026-03-20T13-55-29/devcoredump-status.txt`

The live `devcoredump/data` node was already gone by the time capture ran, so only the journal survived for this event.

## Key kernel lines

The most relevant sequence from the saved journal is:

- repeated `amdgpu: init_user_pages: Failed to get user pages: -1`
- `amdgpu: [drm] AMDGPU device coredump file has been created`
- `Check your /sys/class/drm/card1/device/devcoredump/data`
- `ring comp_1.3.1 timeout, signaled seq=1833, emitted seq=1835`
- `Process plasmashell pid 2211`
- `GPU reset begin!. Source: 1`
- `ring kiq_0.2.1.0 test failed (-110)`
- `BACO reset`
- `GPU reset succeeded, trying to resume`
- `VRAM is lost due to GPU reset!`
- `GPU reset(1) succeeded!`
- `device wedged, but recovered through reset`
- repeated follow-up `ring gfx timeout, but soft recovered`

## Working theory

This looks like a real amdgpu reset path, not just an application crash:

- compute ring timeout first
- full GPU reset and VRAM loss
- desktop compositor fallout after recovery
- repeated soft-recovered gfx timeouts after the main reset

## Next capture step

If this happens again, run this as soon as the machine is usable:

```bash
bash scripts/capture-amdgpu-crash-artifacts.sh '10 minutes ago'
```

That helper saves the kernel journal first and then copies `/sys/class/drm/*/device/devcoredump/data` once if it still exists.
