# Incident: 2026-03-25 Wayland GFX Timeout Reset

This note captures the `amdgpu` reset sequence that ended the previous boot at `2026-03-25 21:45:08 AEST`.

## Observed behavior

- the previous boot (`journalctl -b -1`) entered repeated `gfx` timeout and reset handling at `2026-03-25 21:42:41`
- the active process named in the kernel timeout lines was `kwin_wayland`
- the kernel created multiple `devcoredump` payloads for `card1`
- the machine did not merely lose one user process; it entered repeated BACO reset / VRAM-loss recovery and then shut down shortly after

## Correlated evidence

### Kernel

The critical sequence from `journalctl -k -b -1 --since '2026-03-25 21:42:00' --until '2026-03-25 21:45:30'` is:

- `21:42:41` `ring gfx timeout, signaled seq=67988059, emitted seq=67988061`
- `21:42:41` `Process kwin_wayland pid 1839`
- `21:42:41` `GPU reset begin!. Source: 1`
- `21:42:41` `ring kiq_0.2.1.0 test failed (-110)`
- `21:42:42` `BACO reset`
- `21:42:42` `GPU reset succeeded, trying to resume`
- `21:42:42` `VRAM is lost due to GPU reset!`
- `21:42:42` `GPU reset(1) succeeded!`
- `21:42:42` `[drm] *ERROR* Failed to initialize parser -125!`
- `21:42:42` `[drm] device wedged, but recovered through reset`
- `21:42:44` `ring gfx timeout, but soft recovered`
- `21:42:47` second `ring gfx timeout` followed by another `GPU reset begin!`
- `21:42:50` third `ring gfx timeout` followed by another `GPU reset begin!`
- `21:45:08` shutdown starts on the same boot

### Devcoredump service

The system service was a follower, not the originator:

- `21:42:42` service starts immediately after the first kernel coredump creation
- `21:43:12` first run times out after `30s`
- `21:43:12`, `21:43:40`, `21:44:07`, `21:44:33`, `21:45:01` later runs repeat as more coredumps appear

### Captured dump files

Files under `/var/log/amdgpu-devcoredumps` align with the same window:

- `card1-devcoredump-20260325-214242.bin`
- `card1-devcoredump-20260325-214312.bin`
- `card1-devcoredump-20260325-214340.bin`
- `card1-devcoredump-20260325-214407.bin`
- `card1-devcoredump-20260325-214433.bin`
- `card1-devcoredump-20260325-214501.bin`

## ZKP Frame

O:
- decision surface: this repo, the host machine, the `amdgpu` kernel stack, and the out-of-repo `amdgpu-devcoredump.service`
- operators: user and Codex can change repo capture workflow; only host-level configuration changes can alter the system service or kernel parameters

R:
- distinguish root event from evidence collection
- preserve enough provenance to compare future crashes without re-deriving the timeline by hand
- avoid treating the systemd collector as the cause when it is only reacting to kernel-created dumps

C:
- host journal for boot `-1`
- `/var/log/amdgpu-devcoredumps`
- repo incident notes in `docs/`
- correlation helper in `scripts/`

S:
- observed: the first hard event is a `kwin_wayland`-attributed `ring gfx timeout` at `21:42:41`, followed by repeated BACO resets and VRAM loss
- observed: the service starts after the first coredump exists and continues harvesting subsequent dumps
- uncertain: whether `kwin_wayland` is the initiator, the first visible victim, or just the first context blamed after a deeper GPU/driver fault
- uncertain: whether the concurrent NFS stalls are unrelated background pain or part of the conditions that made shutdown messier

L:
- unclear cause -> timestamp-correlated evidence -> governed reproduction plan -> isolated reproducer -> validated mitigation

P:
- proposal A: treat this incident as a real `amdgpu`/display-path reset, not a collector-service bug
- proposal B: use the new correlation helper before writing future incident notes so kernel, service, and dump-file timelines stay aligned
- proposal C: next reproduction should reduce compositor ambiguity by comparing a display-active path against the most isolated practical workload available in this repo

G:
- promotion requires a reproduction that either isolates a narrower trigger or demonstrates a mitigation
- repo-side claims should be backed by journal lines and timestamped dump files
- host-level changes outside the repo should not be recommended as fixes until a narrower reproducer exists

F:
- no isolated reproducer yet for this exact `gfx`/Wayland reset window
- no parser for the binary devcoredumps yet
- no side-by-side comparison yet between compositor-active and compositor-minimized runs for this failure class

## Synthesis

The event to solve is the repeated `amdgpu` `gfx` reset sequence beginning at `2026-03-25 21:42:41`, not the devcoredump service. The service is confirmed to be an evidence collector that sometimes times out while copying a live dump.

## Failure model and implications

- there is no current evidence of a kernel panic in this incident window; the machine remained alive long enough for `systemd` to keep starting `amdgpu-devcoredump.service`
- `kwin_wayland` is the context named in the timeout lines, but that is more likely the first visible graphics victim than the root cause
- the stronger working theory is the known Polaris-era `amdgpu` / `amdkfd` reset instability under compute or mixed compute-plus-graphics pressure, with the compositor blamed because it continues submitting graphics work into an already-sick device
- the user's report that emergency shell can remain readable while returning to KDE re-produces the glitch is consistent with a partially recovered text-console path and a still-poisoned accelerated desktop path after VRAM-loss reset
- until a narrower reproducer exists, repo notes should distinguish:
  - root fault hypothesis: shared GPU reset instability
  - blamed user-visible context: `kwin_wayland`
  - evidence collector: `amdgpu-devcoredump.service`

## Adequacy

Adequate for the next move. The frame identifies the real failure surface, distinguishes observation from uncertainty, and defines the evidence needed for promotion.

## Next action

1. Use the correlation helper first for any future crash window:

```bash
bash scripts/correlate-amdgpu-reset-window.sh \
  --since "2026-03-25 21:42:00" \
  --until "2026-03-25 21:45:30" \
  --boot -1
```

2. Run the next reproduction in a way that records whether the failing surface is still display-driven, or whether a non-compositor workload can trigger the same reset sequence.
