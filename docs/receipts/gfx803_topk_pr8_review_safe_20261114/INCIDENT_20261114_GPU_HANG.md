# RX 580 / Wayland incident — 2026-11-14

## Trigger

The cached, pre-review TopK wheel was run through
`scripts/gfx803_topk_pr8_benchmark.py` with 10 warmup and 50 timed iterations
per case.  It completed `float32 [1, 151936], k=50`, then the next case,
`float32 [32, 151936], k=50`, exited with `GPU Hang` (`exit -6`).

This cached wheel is **not** the reviewed `isGPUArch` plus fail-closed driver
wheel.  It must not be treated as evidence for that reviewed source revision.

## Kernel sequence

- 12:39:28: AMDGPU reported a `ring gfx timeout` while KWin Wayland was
  submitting work, followed by a gfx_v8_0 reset.
- The reset failed to quiesce/resume KFD queues: `Failed to quiesce KFD`,
  `Failed to restore process queues`, and `Failed to resume KFD`.
- The driver then logged `device wedged`, `VRAM is lost due to GPU reset`,
  and a VM protection fault (`VM_CONTEXT1_PROTECTION_FAULT_ADDR 0x0C000200`).
- Further compositor (`kwin_wayland` and then `plasmashell`) submissions caused
  repeated gfx/compute-ring timeouts and device coredumps.

## User-visible impact

The Plasma Wayland session on `tty1` became unusable.  SDDM itself stayed
active, but a new autologin attempt crashed because the GPU remained wedged.
The broken GUI session was terminated from `tty2`; a full reboot is required
to restore a usable GPU-backed Wayland session.

## Evidence

The persistent kernel journal for this boot contains the original records:

```bash
journalctl -k -b --since '2026-11-14 12:38:00' --until '2026-11-14 12:43:10' \
  --no-pager
```

After the reboot, the captured previous-boot log was retained as
`kernel-previous-boot.log` (SHA-256
`be965c117fc7fd2a815a843b63b3ad807d9e88ae43ffff33495cb82043fc70f6`).
The transient `/sys/class/drm/card1/device/devcoredump/data` was unavailable
after reboot, so no claim is made that the binary coredump was retained.

The unpatched-safe benchmark CSV remains in this directory.  It explicitly
skips the already reproduced faulty unpatched cases and is independent of this
cached-wheel fault.
