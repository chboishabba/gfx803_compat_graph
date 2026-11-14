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

## Implemented source candidate: reset-aware `start_cpsch` RFC

**Committed patch:** [`patches/linux/gfx803-c1b-cpsch-startup-rfc.patch`](../patches/linux/gfx803-c1b-cpsch-startup-rfc.patch). This modifies the **actual Linux function** if applied to Linux v7.3; it is not a synthetic-only proposal, but it is **not installed, kernel-built or upstream-reviewed**.

The source-level causal distinction changes the implementation choice: `start_cpsch()` is invoked during reset **while the reset-domain write semaphore is held**. `execute_queues_cpsch()` attempts `down_read_trylock()` on the *same semaphore* and returns `-EIO` on a failed trylock. The previously ignored return can therefore be an **expected reset-phase lock conflict**, and blindly promoting every such return to fatal would regress reset.

The patch:

1. Explicitly **skips queue execution when `amdgpu_in_reset(adev)`**, preserving the effective no-map behavior of the reset-held trylock without reporting a false hardware failure.
2. Outside reset, **captures and propagates a real `execute_queues_cpsch` nonzero return** rather than returning startup success.
3. Clears `dqm->sched_running = false` in the shared late-startup failure label before releasing fence/packet-manager resources. This also corrects the previously visible hang-buffer allocation failure state.
4. Preserves the original KFD/AMDGPU outer call path; error propagation from `amdgpu_amdkfd_post_reset` remains a **separate future patch**.

**Exact source-context check:** both unified-diff hunks were compared line-for-line against `torvalds/linux` tag `v7.3` `kfd_device_queue_manager.c`, Git blob `4594824985e1eff3cb1cde0726553b25ad1bab3e`, with 0 context mismatches and correct old/new hunk counts. That confirms textual patch compatibility with this upstream source snapshot, not physical correctness. The new `test_gfx803_kfd_c1b_patch.py` also exercises `git apply` against a CPU-only upstream-context fixture; when `GFX803_KERNEL_SOURCE_ROOT` is supplied, it validates the full exact source tree.

**Review blocker before a production backport:** if the queue-management packet was already submitted and then failed mid-execution, freeing the packet manager/fence may race with hardware that is still consuming it. Likewise, after one node starts successfully and another fails, KFD post-reset retains the lock and previous nodes may need explicit teardown. A maintainer-reviewed lifecycle proof and kernel build are mandatory before installing this RFC; the C mock cannot establish that resource lifetime.

The C behavioural model now contains **nine** cases, including the reset-held expected skip, normal non-reset map failure, and legacy ignored-error negative control. This version's CI outcome is **not verified** in this document.

## Next source-level implementation cut

**P1 (RFC staged; kernel-build and lifecycle review open):** refine and upstream-review a minimal fix for `start_cpsch`'s unchecked `execute_queues_cpsch` status; audit whether `pm_init`, resource setup and `sched_running` rollback are safe on failure. A simple `goto` to the existing failure path is **not** automatically safe after `sched_running = true`: it may require unmapping/cleanup, and post-reset hardware may already be unresponsive.

**P2:** patch `amdgpu_device_gpu_resume` / `amdgpu_device_gpu_recover` error return and lock/scheduler ordering using a kernel test/mock that exercises nonzero KFD startup and partial node state. Ensure no stranded DRM reset lock or partially resumed graphics queue. Log the KFD return explicitly; do not call it physical recovery.

**P3:** on non-display independently recoverable gfx803 hardware only, validate after an induced fault: new `/dev/kfd` open, new KFD queue dispatch, gfx/KIQ/KCQ ring health and a fresh DRM/Wayland context. No destructive testing on the sole RX580 display machine.

**Disposition:** C1b semantic contract is implementable and source-backed; a production kernel fix and measured physical recovery are still open.
