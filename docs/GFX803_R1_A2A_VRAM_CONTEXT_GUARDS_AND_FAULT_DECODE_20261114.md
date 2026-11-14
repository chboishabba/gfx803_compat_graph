# R1/A2a follow-up — context generation, VM fault decode, external incident controls

**Date:** 2026-11-14. **Scope:** exact Linux v7.3 source, original November RX580 journal, two external GitHub issue primary sources. **No physical GPU run or driver patch applied.**

## Causal hierarchy: initiating sustained compute hang stays first

The November TopK heavy workload and historical WhisperX/Ollama incidents indicate GPU execution stalls under demanding compute/inference; their *shared* characteristic is hardware queue/ring nonprogress followed by an unsuccessful or non-durable reset. The **first recorded November kernel timeout** is gfx/KWin at 12:39:28; original TopK launch/first blocked kernel/queue remain unproven. Therefore: compute-associated trigger is the most important **pre-reset** lead, while 12:39:32 KWin VM fault is a **post-reset consequence or independent cascading failure**, not proof of the initiating cause.

Keep independent investigative tracks: **R1-T** pre-reset sustained compute ring/firmware/queue forward progress; **R1-R** post-reset CP/GFX/KIQ/KFD/GPUVM recovery. Don't block the former on a post-reset KWin mapping hypothesis.

## A2a exact in-kernel VRAM-loss guards (negative controls)

Original Linux v7.3:
- [`amdgpu_vm.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_vm.c) ~554: `amdgpu_vm_generation` starts with `(u64)atomic_read(&adev->vram_lost_counter) << 32`, adds VM generation, and increments for an errored delayed VM entity.
- [`amdgpu_ctx.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_ctx.c) ~331: each context stores creation `ctx->generation`; ~586–590: `amdgpu_ctx_query2` emits RESET and VRAMLOST flags when the current counters/generation differ. This is a **query**, not necessarily a proactive compositor event.
- [`amdgpu_job.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_job.c) ~231 and ~451: each allocated job captures generation, and `amdgpu_job_run` marks mismatched-generation jobs `-ECANCELED` before scheduling a new IB. This excludes a simplistic *stale job always gets replayed* theory.
- [`amdgpu_cs.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_cs.c) ~320–323: pass 1 rejects `p->ctx->generation != p->gang_leader->generation` with `-ECANCELED`; ~1431–1478: IOCTL parser, pass1, buffer validation, GPUVM handling, sync and scheduling in sequence.
- `amdgpu_vm.c::amdgpu_vm_validate` ~590–600 regenerates VM entities / resets VM BO state machine if the generation changes, and marks evicted BOs for updates; `amdgpu_cs.c::amdgpu_cs_vm_handling` ~1134–1189 refreshes freed/moved/validated mappings and PDEs.

**Strong negative control:** the v7.3 source does not lack a VRAM-loss guard. A theory that KWin blindly replays old commands has to demonstrate a specific bypass, in-flight job/reset timing, invalid fresh context or a GPU-side stale TLB/VM state after valid software updates. The incident journal does not record those branch outcomes, so none is proven.

## GFX8 fault register: `0x01` is a bitfield, not a unique missing PTE diagnosis

`gmc_v8_0_process_interrupt` reads `VM_CONTEXT1_PROTECTION_FAULT_ADDR`, `STATUS` and `MCCLIENT`; `gmc_v8_0_vm_decode_fault` extracts `PROTECTIONS`, `VMID`, `MEMORY_CLIENT_RW` and the ASCII memory client. Relevant masks from [`gmc_8_1_sh_mask.h`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/include/asic_reg/gmc/gmc_8_1_sh_mask.h): PROTECTIONS `0xff`, VMID `0x1e000000` >> 25, MEMORY_CLIENT_ID `0x1ff000` >> 12, MEMORY_CLIENT_RW `0x01000000`.

The original November `STATUS=0x0E0C4001` yields VMID 7, protection-bit field `0x01`, a **read**, and (from the separate client register `0x54433300`) client `TC3`. It documents a graphics-path memory translation/protection fault. It does **not** independently prove which PTE was invalid, whether the fault was stale after BACO, or whether it was the primary compute hang. The address/register values must be joined to actual BO/VM tables to determine that.

**New offline code:** `scripts/gfx803_gmc8_vm_fault_decode.py` with `tests/test_gfx803_gmc8_vm_fault_decode.py`, four direct CPU-only regression cases. Run:
```bash
python3 -m unittest discover -s tests -p 'test_gfx803_gmc8_vm_fault_decode.py' -v
python3 scripts/gfx803_gmc8_vm_fault_decode.py --status 0x0E0C4001 --client 0x54433300
```
These test files are committed; **no CI pass is asserted without a returned run**.

## Module parameters: distinguish printing and isolation from repairs

Linux v7.3's [`amdgpu_drv.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c) ~452–464 documents:
- `vm_fault_stop=0`: never stop on fault (default); `=1`: **print first**; `=2`: **always**. The claim that `=1` safely halts the GPU at first fault is **false**.
- `vm_update_mode=3`: CPU-side graphics and compute VM page-table updates. This may distinguish update transport, but if it changes fault rate, it **does not uniquely prove SDMA/PT update causality**: timings, allocations, pressure and queue ordering also change. Use it only as one controlled A/B arm on independently recoverable non-display equipment, not the only display card.

## External issue comparison — primary reports, not proof of identical initiating bug

1. [RPCS3/rpcs3#16844](https://github.com/RPCS3/rpcs3/issues/16844) (10 Mar 2025 log, Clear Linux 6.6): authentic **GFX8-style** `kiq_0.2.1.0 test failed (-110)` → `KCQ disable failed` → `BACO reset` → GART and VRAM loss; additionally `comp_1.0.1` and `comp_1.0.6` ring tests fail `-110` **after** BACO, despite a subsequent `GPU reset(6) succeeded!` log. The triggering workload is RPCS3, not sustained HIP. This demonstrates a similar *upstream fault/recovery signature* on older kernel and distinct workload; not proof of same first microarchitectural fault.
2. [pop-os/pop#4132](https://github.com/pop-os/pop/issues/4132) (Oct 2026): reported gfxhub VM faults, gfx timeout, BACO/VRAM loss and compositor restart, but hardware is **Navi 10 RX 5600 XT**, not Polaris10. This corroborates general AMDGPU graphics recovery symptoms but is **not** an exact GFX8 case and must not be counted as a Polaris10 regression match.

## Next exact gates (none yet closed by code alone)

| Gate | High-information discriminating target | Status |
| --- | --- | --- |
| **T1** | Original TopK kernel dispatch/queue and 1st fence never advancing; matched historical WhisperX/Ollama pre-reset CP/MEC/SDMA path | OPEN (incident-time dispatch not captured) |
| **R1** | Capture true GFX8 per-ring state immediately **after** BACO vs next real graphics/compute IB, and compare with control where fresh context works | OPEN (historical log lacks this granularity) |
| **V1** | Demonstrate KWin CS `ctx->generation`, `job->generation`, `amdgpu_vm_generation`, VM update and TLB flush order at first post-reset submission | OPEN (guards are SOURCE-CONFIRMED; **actual incident path unknown**) |
| **V2** | Map VM fault address/PROTECTIONS to real PTE/PDE/BO evidence; reproduce with original vs new context | OPEN |
| **P1** | CPU-only source audit and maintainer review of any instrumentation/driver fix before non-display physical test | SOURCE AUDIT ADVANCED, DRIVER FIX OPEN |

**Disposition:** keep the sustained-compute/queue hang as leading initiating hypothesis, GFX8 failure to recover as separate decisive defect, and KWin VMID7 fault as a post-reset discriminator rather than a proven original root cause. Existing [PR #7](https://github.com/chboishabba/gfx803_compat_graph/pull/7) remains the single recovery rollup.

## Source register for cross-incident comparisons

See [GFX803_EXTERNAL_REFERENCE_LEDGER_20261114.md](GFX803_EXTERNAL_REFERENCE_LEDGER_20261114.md) for original URLs, verification class, actual hardware identity, and exclusions. Manjaro Firefox case is RX480 X11, Pop!_OS #4132 Navi10, not identical Polaris RX580/Wayland sources. The pre-hang graphics corruption observation belongs to T1; the later KWin VMID7 TC3 fault remains R1 recovery evidence.
