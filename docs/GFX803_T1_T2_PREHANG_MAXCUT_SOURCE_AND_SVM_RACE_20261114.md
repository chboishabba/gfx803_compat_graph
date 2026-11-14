# T1/T2 max-cut: pre-hang graphics corruption, compute progress, KFD SVM eviction race and falsification

**14 November 2026.** Source-verified against upstream `torvalds/linux` tag `v7.3`, original repository March and November incident notes, and primary AMD-GFX correspondence. **This is an offline engineering audit and draft backport, not a proven physical root-cause repair.** It supersedes generic speculation that a random missing TTM fence or post-reset KWin replay caused the *initiating* hang.

## 1. First-failure matrix (time provenance matters)

| Incident | Last supported good workload / pre-timeout observation | First **recorded** kernel or runtime failure | Follow-up, not necessarily initiating fault | Missing decisive evidence |
| --- | --- | --- | --- | --- |
| **20 Mar Ollama / Mistral** | Good inference response; **pink/green checkerboard** at end of output, before or around crash (user observation, no independent exact artifact timestamp) | Repeated `init_user_pages -1`; first cited ring timeout **`comp_1.3.1`** | KIQ `-110`, BACO, VRAM loss, repeated gfx soft recovery | Actual compute/graphics faulting IB; original page/signal state; telemetry |
| **25 Mar Wayland** | Earlier mixed GPU activity; pre-timeout cause not recorded | **21:42:41** KWin **gfx** ring timeout (not KWin guilty verdict) | KIQ `-110`, BACO, VRAM loss; reset success + failed parser `-125`, repeated gfx resets | Contemporaneous compute kernel, memory state, first corruption timestamp |
| **27 Mar WhisperX** | Real `transcribe` started at **22:57:37**; no `stage_end` | Host crash/reset class; stage-boundary only | Coredump and subsequent reboot | First failing kernel/queue absent; cannot attribute `align` |
| **30 Mar WhisperX** | One no-profiler run completed `transcribe` and started `align` **00:41:27**; profiler run completed same staged path and later crashed in profiler teardown | No-profiler `GPU Hang`; around **01:13:28**, host first reported gfx ring timeout | BACO, VRAM loss, subsequent gfx timeouts; tracing changes outcome | Whether copy, GEMM, allocator, SVM, wave progress or pressure caused first hang; other runs can fail earlier in `transcribe` |
| **14 Nov TopK** | Cached pre-review wheel passed `[1,151936], k=50`; `[32,151936], k=50` hung; user reports **visible corruption just before crashing** | **12:39:28** first logged **gfx/KWin** timeout; KFD queues fail to quiesce; exact first TopK HSACO dispatch unproven | **12:39:29** KIQ `-110`, KCQ disable failure, BACO/VRAM loss; 88 reported GFX8 soft resets in retained journal and KWin TC3 VMID7 fault after reset | Pretimeout device clock/VRAM telemetry, original first stalled compute wave, run queue/PASID, exact browser PID/coredump |

Original notes: [Ollama](INCIDENT_2026-03-20_OLLAMA_MISTRAL_KFD_RESET.md), [Wayland](INCIDENT_2026-03-25_WAYLAND_GFX_TIMEOUT_RESET.md), [WhisperX 27 Mar](INCIDENT_2026-03-27_WHISPERX_TRANSCRIBE_RESET.md), [WhisperX 30 Mar](INCIDENT_2026-03-30_WHISPERX_ALIGN_GPU_HANG_AND_ROCPROFV3_SUCCESS.md), [TopK](GFX803_TOPK_KFD_RESET_FORENSICS_20261114.md), and [November raw kernel journal](receipts/gfx803_topk_pr8_review_safe_20261114/kernel-previous-boot.log).

**Observation hierarchy:** the user's pre-hang graphics corruption is real as reported; no retained frame capture gives its pixel mechanism or absolute timestamp. The first kernel timeout may occur after the first hardware loss of progress. Chrome/Firefox termination is an additional anecdotal symptom; no retained signal, `systemd-oomd` or GPU-process death record proves its cause. Neither browsers nor KWin are to be blamed by default.

## 2. T2 exact source edges checked against v7.3

| Gate | Linux source and exact site | What the code actually ensures | Does **not** prove |
| --- | --- | --- | --- |
| **A1** | `kfd_device_queue_manager.c` ~2673–2748, `unmap_queues_cpsch` | Checks running runlist/reset reader lock, emits unmap/query-status, waits for `KFD_FENCE_COMPLETED`, checks preemption/SDMA hang on successful fence | It can force a nonresponsive CP/MEC to finish; a hardware `-ETIME` is not a PTE-corruption diagnosis |
| **A2** | `kfd_device_queue_manager.c` ~2357–2385, `amdkfd_fence_wait_timeout` | Distinguishes reset/fatal `-EIO` from expiry `-ETIME` (`qcm fence wait loop timeout expired`); `halt_if_hws_hang` is a debugging halt | Incident-time original return code from the generic failed-quiesce message (not printed) |
| **B1** | `amdgpu_ttm.c` ~306–387 and 396–456 | Memory move emits `amdgpu_copy_buffer` DMA fence; `ttm_bo_move_accel_cleanup` performs async accounting and kernel-page-table wait; errors wait for outstanding fence | Zero missed dependencies in every allocator/SDMA interleaving |
| **B2** | `amdgpu_vm.c` ~1284–1398 | `clear` synchronizes same-VM previous work and KFD BO fence; mapping synchronizes BO move reservations before PTE update; `vm->last_update` and `bo_va->last_pt_update` track resulting fences | A specific KWin/ROCm hardware VM fault was caused by this path |
| **B3** | `amdgpu_cs.c` ~979–989, 1105–1202 | Validates VM/BOs, adds PRT/CSA/BO PT update fences and final VM update fence to submission sync | A graphics IB can bypass all required producer fences without showing which actual branch |
| **B4 — NEW concrete race** | `kfd_svm.c` **2047–2099** | XNACK-off SVM invalidations **do not serialize** the second range's notifier return with completion of first range's `kgd2kfd_quiesce_mm` | That the original November `hipMalloc`/TopK path used SVM ranges or this interleaving |
| **B5** | `amdgpu_amdkfd_gpuvm.c` ~2517–2546 | Userptr invalidation **does** hold per-process `notifier_lock` over the first `kgd2kfd_quiesce_mm` | That the separate SVM range path inherited the same protection |
| **C1** | Historical journal and archived notes | No matched pre-hang `sclk/mclk`, DPM, voltage, VRAM pressure or ECC counters found in the cited material | DPM/VRAM electrical instability; no metadata implies a healthy board |

Source blobs:
- [Linux v7.3 `kfd_svm.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_svm.c), blob `d7f2ff5c8f024ad71c1fd9b6d074fb548ae078ab`
- [`kfd_priv.h`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_priv.h), blob `435bf26929680c8a6e5e730de45427f377948add`
- [`kfd_device_queue_manager.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_device_queue_manager.c), blob `4594824985e1eff3cb1cde0726553b25ad1bab3e`
- [`amdgpu_ttm.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_ttm.c), blob `83968886c29a644c734f87dcccb6bd2e8b7a94f3`
- [`amdgpu_vm.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_vm.c), blob `4a63b472f68ec8e6497813bb94baaddc2a37e0cf`

### B4 counterexample interleaving — real kernel logic

The verified source has:
```c
evicted_ranges = atomic_inc_return(&svms->evicted_ranges);
if (evicted_ranges != 1)
    return r;  /* second invalidator can leave before first quiesces */
r = kgd2kfd_quiesce_mm(mm, KFD_QUEUE_EVICTION_TRIGGER_SVM);
```

A first MMU notifier **A** increments from zero to one and begins blocking queue quiescence. Before it completes, another mapped SVM range's notifier **B** increments to two and returns immediately, permitting the CPU MM to reuse pages even if GPU work is not stopped. This violates the desired *quiesce-before-invalidation-return* ordering. AMD independently described the same race for XNACK-off and posted a per-process `evict_lock` fix on **9 November 2026**, **Reviewed-by Felix Kuehling**: [AMD-GFX upstream thread](https://lore-kernel.gnuweeb.org/amd-gfx/9ea351fa-982b-4d9c-8471-03e168852c83@amd.com/T/). The proposed mechanism includes host pageable `hipMemcpy` invalidation under memory pressure.

**Staged now:** [`patches/linux/gfx803-t1-svm-concurrent-eviction-v73-rfc.patch`](../patches/linux/gfx803-t1-svm-concurrent-eviction-v73-rfc.patch), a **v7.3-context port** of the upstream reviewed proposal. It adds per-process `evict_lock` field/init/fini and holds it across the first queue quiesce. All four unified hunks were structurally checked against the exact two v7.3 source blobs; the proposed patch changes no running kernel. [CPU-only deterministic interleavings](../tests/test_gfx803_svm_evict_interleavings.py) and [patch-application tests](../tests/test_gfx803_svm_patch_context.py) are committed but not yet confirmed through a kernel build or CI.

**Limitations:** the lock serializes notification returns only if the first `kgd2kfd_quiesce_mm` actually finishes successfully. A failed MEC preemption leaves a separate hardware hazard and **does not become safe because of this mutex**. A full kernel compile, lockdep/MMU notifier review and kernel-version check precede any upstream/backport release. Presence of the source race does not prove it was taken by TopK/WhisperX/Ollama, or that their graphics artifacts originated from an SVM buffer.

## 3. External controls — corrected applicability

| Source | Verified original scope | Use for gfx803 |
| --- | --- | --- |
| [2025 LKML RX580 regression report](https://lists.openwall.net/linux-kernel/2025/06/25/2176) | Original user-reported Arch RX580 stability after reverting `de84484c6f8b` and `bac38ca057fe`, plus AMD request for a follow-up patch | Historical **reported** KFD bisect and queue-reset candidate; independent v7.3 kernel cause not established |
| [July 2026 multi-GPU SDMA drain RFC](https://www.mail-archive.com/search?f=1&l=amd-gfx@lists.freedesktop.org&o=newest&q=subject%3A%22%5C%5BPATCH%5C%5D+drm%5C/amdgpu%5C:+drain+SDMA+before+process+eviction+during+GPU+reset%22) | Several GPU devices in a reset list; SDMA on *other devices* still running. Maintainer questioned whether draining before signal can complete | Illustrates race class, **not** single-Polaris first-error proof |
| [Sept 2026 SDMA DCC patch](https://lists.openwall.net/linux-kernel/2026/09/24/1984) | `gfx12` DCC, SDMA7.0.0/7.0.1 moving BOs with multiple entities | **Not GFX8-applicable** as-is |
| [Nov 9 2026 reviewed SVM notifier fix](https://lore-kernel.gnuweeb.org/amd-gfx/9ea351fa-982b-4d9c-8471-03e168852c83@amd.com/T/) | Non-MES-independent KFD SVM path, XNACK-off, concurrent MMU invalidations | **High-alpha**, exact v7.3 source shape confirmed, real hardware incidence not proven |
| [RPCS3 #16844](https://github.com/RPCS3/rpcs3/issues/16844) | Older KIQ/KCQ/BACO signature and post-reset compute-ring test failures | Shared reset **signature**, different initial game workload |
| [Bazzite #3383](https://github.com/ublue-os/bazzite/issues/3383) | Actual **RX580**, artifacts/blank display and gfx timeout | Independent observation of similar symptom, no causal bisect |
| [CachyOS #930](https://github.com/CachyOS/linux-cachyos/issues/930) | **RX590 Polaris**, PRT/sparse texture/VAAPI | Separate PRT regression; not equivalent to TopK HIP |
| [ROCm legacy #4919](https://github.com/ROCm/legacy-rocm-build/issues/4919) | **RX6800 XT**, Nobara HIP | Not an RX580/WhisperX incident; exclude |
| [ROCm legacy #6386](https://github.com/ROCm/legacy-rocm-build/issues/6386) | **Radeon 780M gfx1103 / MES SVM** | Modern MES negative control; exclude from GFX8 patch evidence |
| [CachyOS #1091](https://github.com/CachyOS/linux-cachyos/issues/1091) | RX580 **VCE encoding** ring align-mask, fixed v7.3 | Separate hardware IP, not initiating gfx/compute hang |

**Do not apply misnumbered reset knobs:** Linux v7.3 `amdgpu.reset_method=0` means legacy; `1` is mode0, `4` is BACO. `amdgpu.baco=0` is not a verified v7.3 module parameter. `cwsr_enable=0`, `HSA_ENABLE_SDMA=0` and CPU VM table updates are *hypothesis-changing experimental controls*, not guaranteed fixes. Avoid all disruptive controls on the one display RX580.

## 4. Falsification matrix — exact next decisive work

| Hypothesis | Would support it | Would weaken/refute it | Evidence still required |
| --- | --- | --- | --- |
| **A CP/MEC queue starvation / CWSR** | First compute fence stops while gfx submit backlog grows, evict query-status never completes, HIQ MQD records failed preemption | Both rings still make progress and image corruption occurs with no dispatch wait or preemption | First actual TopK HSACO dispatch, HQD/MQD, CP preempt state, per-ring fence values and bounded workload duration |
| **B1 normal TTM move / PTE fence missing** | Specific graphics IB executes before its producer move/PT fence (capture producer-fence → consumer-IB graph) | A valid waited dependency for every implicated BO and PTE, plus correct TLB flush | Actual BO reservation, DMA fence, VM update and IB submission trace—not general talk of large VRAM allocations |
| **B2 concurrent KFD SVM eviction** | Distinct SVM MMU notifiers overlap first quiesce; second returns before it completes, under XNACK-off | No SVM-range mapping in failing workload, or no overlapping notifier windows | SVM range presence, event timestamps, `evicted_ranges`, notifier/queue quiesce begin/end for failing PASID |
| **C DPM/GDDR5/power margin** | Clock/temp/power excursions precede same pre-hang visual corruption at matched workload; failures change under controlled **safe-host** clock cap | Identical failures independent of clock/VRAM pressure, coupled with a directly identified race/IB error | Actual `sclk/mclk`, temperature, memory occupancy, PCIe/power readouts during matched conditions |
| **R post-reset corruption** | First post-BACO new graphics/compute IB fails despite earlier scratch ring pass | Fresh DRM + KFD contexts and genuine work succeed without reboot | Already separate R1 programme; do not use post-BACO fault to assign T1 blame |

**Maximum cut:** T1 identify first GPU command with lost forward progress; T2 inspect actual concurrent SVM notifier presence/ordering and TTM/VM fence dependency, then T3 safe falsification; T4 port kernel correction only after mechanism activation confirmed (B2 RFC currently source-only); T5 independent device physical acceptance. The display RX580 must not be deliberately re-wedged by replaying `[32,151936], k=50` or large uncontrolled memory churn.

**Status:** First-failure cross-incident matrix DONE from retained notes; kernel source and concrete B2 concurrency defect DONE at source level; physical attribution to RX580 incident, kernel compile and no-reboot recovery still OPEN. No observed browser crash was adjudicated as OOM or device loss in this pass.
