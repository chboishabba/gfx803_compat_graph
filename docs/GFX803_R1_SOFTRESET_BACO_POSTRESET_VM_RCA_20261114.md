# R1 / A1–A2: GFX8 soft reset, BACO and transient post-reset ring success (14 Nov 2026)

**Source:** Linux `v7.3` original `gfx_v8_0.c`, `amdgpu_device.c`, `vi.c`, `gmc_v8_0.c`. Incident: [immutable 14 Nov kernel journal](receipts/gfx803_topk_pr8_review_safe_20261114/kernel-previous-boot.log). This is **offline RCA of a physically failed recovery**, not a newly tested hardware fix.

## 1. Actual reset state machine

| Source boundary | State transition and explicit result | Recovery assurance |
| --- | --- | --- |
| Initial gfx scheduler timeout | User context reported as `kwin_wayland`; does not prove initial workload or first failing device instruction | **GPU forward progress already lost** |
| `gfx_v8_0_hw_fini` (v7.3 ~4868) | Calls `gfx_v8_0_kcq_disable(adev)` (v7.3 ~4880), **discards its return**. This function submits KIQ `PACKET3_UNMAP_QUEUES` and tests the KIQ ring; emits `KCQ disable failed` if it returns nonzero | A failed KIQ queue disable can coexist with apparent successful GFX teardown; not proof queue-safe memory state |
| `gfx_v8_0_soft_reset` (~4909–5004) | Deactivates compute HQDs, calls IP suspend, toggles GRBM/SRBM reset bits, then calls IP resume and late-init; `suspend` return is not checked | **`Successful gfx_v8_0 IP block soft reset` means source function returned 0**, not that future queues can execute |
| Following full GPU reset | `vi.c::vi_asic_reset_method` chooses BACO for Polaris if supported; `vi_asic_reset` reports `BACO reset` | The observed 12:39:29 reset was BACO, not unrecorded PCI fallback |
| `amdgpu_device_reinit_after_reset` (~5116) | `GPU reset succeeded, trying to resume` is printed immediately after `amdgpu_device_asic_init` succeeds, **before** IP resume phase1, firmware loading, phase2, phase3, late init, and DRM client resume | This log is explicitly **not** completion |
| IP phase1 + firmware (~5152–5176) | COMMON/GMC/IH are resumed, GART is re-enabled, VRAM loss handled, `amdgpu_device_fw_loading` called | GART enable and firmware loader success alone do not prove user VM mapping validity |
| IP phase2 (~5177) | Resumes GFX8: `gfx_v8_0_cp_resume` initializes KIQ, gfx CP, KCQ, then `gfx_v8_0_cp_test_all_rings` tests **gfx → KIQ → compute** and returns nonzero on failed basic ring test. Phase2 forwards the error; reinit exits on error | A clean outer `GPU reset(n) succeeded!` after this full-reset route is **strong source-level evidence that basic ring tests passed at that instant**, assuming GFX block valid and not already marked HW initialized. It is **not a durable real-workload or KFD user VM test** |
| Later DRM scheduler + KFD post-reset | DRM scheduler resumes before `amdgpu_amdkfd_post_reset`, whose return is ignored. `kgd2kfd_post_reset` early return can retain `kfd_locked`. | A later `GPU reset(n) succeeded!` is not proof of KFD/device functional recovery |

Original-source pointers:
- [GFX8 teardown, soft reset, KIQ/KCQ and ring tests](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c)
- [Full ASIC reset and IP reinitialization](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_device.c)
- [Polaris BACO/PCI reset branch](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/vi.c)
- [GMC8 GART resume path](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/gmc_v8_0.c)

## 2. First November wave, with stronger phase separation

| Time (original kernel-log local time) | Observed | What it establishes |
| --- | --- | --- |
| **12:39:28** | `ring gfx timeout`, GFX8 soft reset started, unsuccessful queues preemption and `Failed to quiesce KFD` | Engine/queue execution failure precedes any logged BACO operation |
| **12:39:29** | KIQ ring test `-110`, `KCQ disable failed` | **Earliest explicitly proven nonprogress of KIQ in the incident.** Source call returns error discarded by `gfx_v8_0_hw_fini` |
| **12:39:29** | `Successful gfx_v8_0 IP block soft reset` and `device wedged` | Soft reset completed per caller, but not a functional recovery |
| **12:39:29** | `GPU reset begin`, BACO, `GPU reset succeeded, trying to resume`, `PCIE GART ... enabled`, VRAM loss | Full reset and restart of memory/GART reinitialization; *not* yet end-to-end recovery |
| **12:39:30** | `GPU reset(2) succeeded!` | The full reset/reinit path returned success; GFX8 basic ring tests probably passed **transiently**, conditional on normal IP block status |
| **12:39:32** | `ring gfx timeout, but soft recovered`; `GPU fault detected`; `VM fault (0x01, vmid 7, pasid 7)` from `TC3` in KWin context | **Within two seconds after reported full reset success, real graphics work suffered a timeout and GPUVM fault.** This is currently the highest-information *post-BACO* boundary |
| **12:39:33 onward** | Compute timeouts, further GFX timeouts and repeated soft-reset successes | Not durable recovery |
| **12:40:55** | `qcm fence wait loop timeout expired`, failed KFD quiescence; BACO; `GPU reset(62) succeeded!` | Later explicit `-ETIME` source branch; no evidence of restored desktop after repeated full resets |

The `VM fault` is **evidence of a faulting graphics memory access after reset**, not yet proof of a driver mapping bug: the address may have been legitimately invalid because userspace did not rebuild destroyed GPU buffers after VRAM loss. We must distinguish *driver failed to restore fresh valid mappings* from *compositor replayed an invalid old context* from *memory controller/TLB/firmware remained corrupt*.

**Critical revised RCA:** the source and timeline do not support the simplistic claim that KIQ never initialized after BACO. They instead support a possible **briefly successful basic ring-test → later real workload timeout/VM fault → recurrent device wedge**. The subsequent fault occurs in a user graphics context. The exact first invalid mapping and whether it existed before or was caused by reset remain open.

## 3. Three decisive root-cause hypotheses and evidence that discriminates

**H1 — residual CP/MEC/KIQ state after soft reset:** the pre-BACO KIQ test fails and KCQ disable is ignored, so queue state may remain poisoned. *Discriminator:* compare post-soft-reset KIQ/KCQ fence progress and post-BACO basic ring tests; check if the newly initialised KIQ works while the prior user VM later fails.

**H2 — graphics GPUVM/context state after VRAM loss:** reset reports GART enable/VRAM loss; then KWin's graphics queue faults in VMID 7/PASID 7 and stops making progress. *Discriminator:* inspect first KWin GPU buffer addresses, VM page-table restore/unmap, TLB invalidation, fence and user GPU VM state after VRAM loss. A fresh context is a much stronger test than retrying the poisoned prior KWin context.

**H3 — firmware/power-domain reset incomplete under realistic dispatch:** CP ring scratch tests pass momentarily but higher-level gfx memory/shader/compute work fails. *Discriminator:* distinct post-reset scratch-ring vs shader/IB/VM test outcomes and actual CP/MEC microcode reload, security state, PCI function and power state; a true cold restart versus a software/manual driver reload.

Currently the evidence **does not select one uniquely**. H2 becomes especially high-alpha for the *post-BACO* persistent graphics failure because the raw journal contains a concrete VM fault shortly after the first apparently successful full reset. H1 is proven as the pre-BACO KIQ failure boundary, not proven as still broken after BACO. H3 remains plausible.

## 4. Implemented safe evidence extraction

`scripts/gfx803_reset_wave_chronology.py` reads the original kernel journal, labels the KFD/soft reset/KIQ/KCQ/BACO/full reset and VM faults, and records faults within a bounded window after each `GPU reset(n) succeeded!`. It uses only standard-library file reads, **no GPU execution or system driver interaction**. `tests/test_gfx803_reset_wave_chronology.py` tests transient-success-followed-by-fault, absence of a hardware acceptance implication, timing window and overwrite refusal. **New committed tests have not been physically run on TrueNAS/CI in this step.**

Example (use the full original journal on a host with repo checkout):
```bash
python3 -m unittest discover -s tests -p 'test_gfx803_reset_wave_chronology.py' -v
python3 scripts/gfx803_reset_wave_chronology.py \
  --journal docs/receipts/gfx803_topk_pr8_review_safe_20261114/kernel-previous-boot.log \
  --output /tmp/gfx803_nov14_reset_waves.json --year 2026 --horizon 10
```

The receipt is explicitly retrospective; it cannot invent the incident-time first kernel dispatch, missing KFD internal return, a kernel build identifier, or a fresh hardware test.

## 5. Next code-level max-cut (not hardware stress)

1. **A2a — VM first fault source:** source-map `gmc_v8_0` VM fault decode and `amdgpu_vm` replay after GART reset. Determine the *semantic condition* for post-VRAM-loss user mappings to be valid. Derive one checkable invariant separating healthy new contexts from poisoned old mappings.
2. **A2b — GFX8 IP reinit receipt:** instrument *offline* source with a narrowly scoped debug patch proposal showing per-phase results (GMC/GART/IH, firmware, GFX/KIQ/KCQ ring retest) and changed-first-failure capture, without installing it on display hardware.
3. **A2c — physical falsification only when safe:** on independently recoverable non-display GFX8, compare cold-start basic ring and GFX VM tests, then a controlled reset and *fresh graphics/compute context*. Match loader, firmware, clocks and device identity. Do not reproduce known wedges on the display RX580.
4. **R4 correction:** target the first demonstrably defective restoration step, not merely suppress reset output. C1b KFD error return remains a separate containment patch under PR #7 and **does not close R1**.

**Not yet proven:** true hardware/firmware reset bug versus persistent userspace GPUVM replay bug versus missing host power-cycle step. The first post-BACO VM fault narrows what to test; it does not settle which subsystem is responsible.
