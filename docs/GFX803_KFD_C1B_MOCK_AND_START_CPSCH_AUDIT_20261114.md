# C1b: standalone C failure-injection model + GFX8 startup branch audit (2026-11-14)

**Purpose:** test one important recovery failure-propagation contract **without touching a live GPU**. This is a behavioural mock, **not Linux source, a proven upstream patch, or a test of physical reset durability**.

Source: Linux v7.3 original files:
- [amdgpu_device.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_device.c) — `amdgpu_device_gpu_recover` and `amdgpu_device_gpu_resume`
- [amdgpu_amdkfd.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_amdkfd.c) — returns error from `kgd2kfd_post_reset`
- [kfd_device.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_device.c) — `kfd_resume`, `kgd2kfd_post_reset`, reset lock count
- [kfd_device_queue_manager.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_device_queue_manager.c) — `start_cpsch`, `start_nocpsch`, startup fail labels, `execute_queues_cpsch`
- [kfd_device_queue_manager_vi.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_device_queue_manager_vi.c) — VI-specific callbacks, **not** the startup function

## Audit conclusions

For `CHIP_POLARIS10` with default `KFD_SCHED_POLICY_HWS`, the queue manager uses shared `start_cpsch`. `CHIP_TONGA` and `CHIP_HAWAII` have explicit no-HWS policy exceptions; do not infer that from the VI file name or mix a Tonga hardware scheduler policy with Polaris.

`start_cpsch` has four explicit failure boundaries:

| Stage | Source action | Error path |
| --- | --- | --- |
| S1 | `pm_init` | `fail_packet_manager_init` |
| S2 | `set_sched_resources` | `fail_set_sched_resources` / `pm_uninit` |
| S3 | `kfd_gtt_sa_allocate` fence | `fail_allocate_vidmem` / `pm_uninit` |
| S4 | `kzalloc` hang-detection buffer | `fail_detect_hang_buffer` / free fence / `pm_uninit` |

**Independent high-alpha defect candidate:** `start_cpsch` sets `dqm->sched_running = true` **before** calling `execute_queues_cpsch(dqm,...)` at approximately line 2124, **without capturing its return**. It later returns `0` even if the internal queue mapping command reported nonzero. Also, if S4 allocation fails after `sched_running` became true, the failure labels clean up allocations but do **not visibly set `sched_running = false`**. That is a source-level state-invariant concern; it does not prove a real November queue-manager startup error.

`kfd_resume(node)` returns `dqm->ops.start()`'s status. On error, `kgd2kfd_post_reset` returns before `--kfd_locked`. The wrapper `amdgpu_amdkfd_post_reset` returns the status, but the AMDGPU caller discards it. `GPU reset succeeded!` may therefore reflect a prior ASIC-reset stage, not successful KFD restart.

The candidate error contract **does not decrement KFD lock on failure**. An uninitialized queue manager must not be opened merely to make `/dev/kfd` return success. The contract instead makes the error visible, prevents the graphics scheduler from being restarted prematurely, and guarantees balanced reset-domain unlock. A real driver patch must account for KFD's global lock accounting and for any partially started nodes.

## Run (CPU only)

```bash
cc -std=c11 -Wall -Wextra -Werror -pedantic -O2 \
  -o /tmp/gfx803_c1b scripts/gfx803_kfd_c1b_mock.c
/tmp/gfx803_c1b
python3 -m unittest -v tests.test_gfx803_kfd_c1b_mock
```

Test cases in the model:
1. Legacy failure is ignored and DRM scheduler can start while KFD is locked.
2. All-node success drains KFD lock and opens scheduler once after callback.
3. First-node startup failure propagates, leaves KFD fail-closed, and releases reset-domain lock.
4. Each of S1–S4 is injected separately into the common failure contract.
5. Second-node failure after partial startup keeps scheduler closed and reveals required real-driver cleanup.
6. Unchecked `execute_queues_cpsch` failure demonstrates that **outer return checking alone is insufficient**.
7. No accidental automatic retry or double scheduler start after failure.

The C model's four stages share the same injected nonzero return path; this is a bounded **control-flow model**, not compilation of original `pm_init`, `kfd_gtt_sa_allocate` or `execute_queues_cpsch` under stubs. The Python unittest compiles and runs the committed C model in CI.

## Next source-level implementation cut

**P1 (directly actionable):** propose a minimal, upstream-reviewable fix for `start_cpsch`'s unchecked `execute_queues_cpsch` status; audit whether `pm_init`, resource setup and `sched_running` rollback are safe on failure. A simple `goto` to the existing failure path is **not** automatically safe after `sched_running = true`: it may require unmapping/cleanup, and post-reset hardware may already be unresponsive.

**P2:** patch `amdgpu_device_gpu_resume` / `amdgpu_device_gpu_recover` error return and lock/scheduler ordering using a kernel test/mock that exercises nonzero KFD startup and partial node state. Ensure no stranded DRM reset lock or partially resumed graphics queue. Log the KFD return explicitly; do not call it physical recovery.

**P3:** on non-display independently recoverable gfx803 hardware only, validate after an induced fault: new `/dev/kfd` open, new KFD queue dispatch, gfx/KIQ/KCQ ring health and a fresh DRM/Wayland context. No destructive testing on the sole RX580 display machine.

**Disposition:** C1b semantic contract is implementable and source-backed; a production kernel fix and measured physical recovery are still open.
