# T2 — GFX8 KFD SVM/userptr, queue-preemption and TTM/GPUVM synchronization audit

**14 November 2026.** This consolidates B1–B4 into one exact source gate. Existing [T1 first-failure provenance](GFX803_T1_DISPATCH_MEMORY_PROVENANCE.md), [source ledger](GFX803_EXTERNAL_REFERENCE_LEDGER_20261114.md), [machine gate report](receipts/gfx803_t1_t2_gate_matrix.json) and [v7.3 SVM RFC](../patches/linux/gfx803-t1-svm-concurrent-eviction-v73-rfc.patch) are dependencies. **Kernel source-reachable ≠ original incident-executed.** User-confirmed corruption occurs *before* the GPU hang; do not assign it to post-BACO VRAM loss.

## B1 — SVM concurrent invalidation and quiesce-before-return

Source: Linux `v7.3` [`kfd_svm.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_svm.c) ~2047–2099, ~2666–2704, [`kfd_priv.h`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_priv.h) `struct svm_range_list`.

1. `svm_range_cpu_invalidate_pagetables` chooses `svm_range_unmap_from_cpu` for `MMU_NOTIFY_UNMAP`; other MMU invalidations reach `svm_range_evict`.
2. With XNACK off / GPU_ALWAYS_MAPPED, the first relevant invalidator increments `evicted_ranges` to one then calls `kgd2kfd_quiesce_mm`.
3. **Original v7.3 defect:** a concurrent second invalidator increments `evicted_ranges` above one and returns *before* the first quiesce finishes, despite GPU pages possibly still accessed.
4. AMD's [9 Nov 2026 reviewed fix](https://lore-kernel.gnuweeb.org/amd-gfx/9ea351fa-982b-4d9c-8471-03e168852c83@amd.com/T/) introduces a process-scoped `evict_lock` over increment and quiescence; our **four-hunk v7.3-context RFC patch** in PR #7 implements the same intended ordering.
5. Executed simplified two-invalidator exploration: original 35 states with an early-return counterexample; lock case 25 states and no early return when quiesce succeeds; lock case still unsafe when quiesce itself fails. [Exact JSON receipt](receipts/gfx803_t2_svm_two_notifier_exhaustive_model_20261114.json).

**Required activation evidence:** failing process PASID, `svm_range` registration, notifier event *other than plain UNMAP*, two overlapping notifications, first quiescence start/end/return code, second return, and a concurrently active GPU queue. The AMD patch notes a possible pageable `hipMemcpy` / `hsa_amd_memory_lock` route; mere `hipMalloc`, HSA agent enumeration, XNACK-off or `GPU Hang` does not prove this condition occurred. No active probe or observed overlap exists in the original retained TopK journal.

**RFC limits:** lock does not repair CP/MEC that cannot quiesce, and no kernel build, lockdep, exact CachyOS build integration or physical acceptance is claimed. Do not deploy it to the one display RX580.

## B2 — Userptr/HMM pinning and invalidation is *not* the same path

Source: Linux v7.3 [`amdgpu_amdkfd_gpuvm.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_amdkfd_gpuvm.c) ~1049–1112, ~1850–1855, ~2517–2548; [`amdgpu_ttm.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_ttm.c) ~746–800.

- `init_user_pages` is reached when a KFD BO has a user-provided host address; sets up the userptr, registers an HMM MMU notifier, calls `amdgpu_ttm_tt_get_user_pages`, and logs the errno on failed get pages.
- March Ollama's original quoted `init_user_pages: Failed to get user pages: -1` is evidence the **userptr page-acquisition callsite** failed. `-1` is typically EPERM in Linux errno numbering, but source/journal alone do not establish *why* the page acquisition returned it (process access / HMM page walk / invalidation / permission / backing VMA). No caller flags/VA/PASID/valid mmap at the failure moment survive in the cited note.
- `amdgpu_amdkfd_evict_userptr` holds `process_info->notifier_lock` from invalid increment through first `kgd2kfd_quiesce_mm` and delayed restore scheduling; this is not the same missing serialization as the separate SVM range path.
- `restore_userptr_work` and KFD queue restoration produce additional failure symptoms **after** a GPU is already nonresponsive; they are neither automatically the original bad operation nor exculpatory.

**Required original witness:** matched raw March journal/user BO flags and addresses (not just summary), HMM page range return, CPU VMA permissions and target GPU PASID, interleaved MMU invalidations and KFD quiesce status; establish temporal relation to the first `comp_1.3.1` timeout. If the first failure was before the get-pages message, that is recovery-related rather than initiating.

## B3 — Non-MES MEC/HIQ queue preemption, fence and exact errno

Source: [`kfd_device_queue_manager.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_device_queue_manager.c) ~2357–2385, ~2645–2670, ~2673–2748.

```text
evict_process_queues_cpsch
    → unmap_queues_cpsch
      → reset-domain read trylock (failure -EIO)
      → pm_send_unmap_queue
      → dqm->fence_addr = KFD_FENCE_INIT
      → pm_send_query_status(..., KFD_FENCE_COMPLETED)
      → amdkfd_fence_wait_timeout
           -EIO if fatal GPU condition/reset observed
           -ETIME if wall timeout expires (qcm fence wait loop timeout expired)
      → on successful fence, HIQ MQD check_preemption_failed
      → possible per-queue recovery or SDMA reset
```

The November **first** preemption line occurs at 12:39:28; no `qcm fence wait loop timeout expired` printed until 12:40:55. Therefore retroactively labeling the original 12:39:28 KFD return **`-ETIME` is unsupported**; the generic `unsuccessful queues preemption` message is emitted for multiple nonzero returns. At 12:39:29 the independent GFX8 KIQ ring test fails `-110`. **HIQ/MEC and KIQ are not interchangeable hardware ring tests.**

We have a source-level Polaris GC8 reference for non-MES KFD scheduling and a postboot module Build ID from [KFD handoff receipt](receipts/gfx803_kfd_kernel_source_handoff_20261114.json). The exact original source-to-module build provenance and recorded incident-time `retval` remain open; do not infer the original queue's doorbell or failed GPU packet from a late report.

**Required witness:** first stuck queue ID, PASID/VMID and actual copy/compute ring, MQD doorbell and HIQ preemption-failed marker, before/after KFD fence value, return site and **time relative to visible graphics corruption**. A KWin gfx timeout is a *reported* scheduler timeout, not exclusive proof graphics work was the initiating shader hang.

## B4 — TTM BO move, SDMA and graphics PTE fence dependencies

Sources: [`amdgpu_ttm.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_ttm.c) ~306–387, ~396–456; [`amdgpu_vm.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_vm.c) ~1284–1398; [`amdgpu_cs.c`](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_cs.c) ~1105–1202.

- `amdgpu_ttm_copy_mem_to_mem` maps original/destination windows and submits `amdgpu_copy_buffer` with the BO reservation, returning the last move fence. `amdgpu_move_blit` calls `ttm_bo_move_accel_cleanup` with that fence, with explicit kernel-BO wait and error-handling wait.
- For mapping, `amdgpu_vm_bo_update` syncs to BO reservation / move fences; for clearing, it syncs to same-VM submissions and KFD BO fences. It schedules new PTE changes and saves `last_pt_update` or `vm->last_update`.
- `amdgpu_cs_vm_handling` adds PRT, CSA, explicit BO PT and final VM update fences to graphics submission dependencies, updates moved objects/PDEs, and returns errors on failure. The source comment notes a per-BO update loop retained because removing it caused test regressions.
- This makes an unqualified claim of **“SDMA eviction has no fences” false** for the audited normal paths. A real missing-edge fix requires identifying an **actual** BO/fence/VMID/IB that bypassed or misordered a dependency.

**Required witness:** same GPU BO identity, migration from/to domains and physical backing, move `dma_fence` seq/signaling, GPUVM PTE/PDE producer update fence, graphics consumer IB submit/sync and TLB sequence. If these edges are all fulfilled before corruption, normal TTM missing-fence speculation is weakened; inspect CWSR/CP, GPU memory controller, DPM/clock/firmware instead.

## C0 — T3 safe falsification sequence / controls

| Scenario | Allowed without wedging display GPU | Prediction / decisive interpretation |
| --- | --- | --- |
| Retrospective dump/journal/profiler parse | **Yes**: file reads, sha, checksums, original code-source mapping | Evidence can establish pretimeout order; missing trace is unknown |
| List available ftrace tracepoints/symbols and installed runtime flags | **Read-only listing** with access permissions; no tracing configuration writes | Select passive capture feasibility; not historical evidence |
| Single known-safe small TopK/WhisperX workload | Only with specific previous accepted physical health and minimal bounds; **not run here** | Runtime SVM allocation event, if captured, supports reachability but not dual invalidator race |
| Explicit SVM notifier probes | **Not passive:** enabling probes changes kernel tracing and timing; independently recoverable host preferred | Two distinct invalidators + quiesce overlap supports B1 incident analogue |
| `HSA_ENABLE_SDMA=0`, `cwsr_enable=0`, DPM clock cap | Configuration changing; requires independent hardware protocol | Sensitivity alone not unique causality |
| `vm_update_mode=3` | CPU-side VM updates, not unique SDMA-exclusion proof | One control arm only; affects timing/pressure |
| `reset_method=1` for legacy | **Incorrect**: v7.3 `0=legacy`, `1=mode0`, `4=BACO` | Reject misconfiguration |
| Original `[32,151936]` f32 TopK on display RX580 | **Never** | Known device-wedging hazard |

## Exit gates and deliverables

| Gate | Accepted now | Open proof / mandatory next artifact |
| --- | --- | --- |
| B1 original v7.3 SVM two-notifier race | Source + 35/25-state model + 4-hunk RFC | Original running PASID SVM registration and overlapping invalidation / quiesce witness; actual kernel compile |
| B2 March userptr callsite | Original message and exact source branch | Raw page-acquisition errno context, userptr BO/mmap and ordering vs timeout |
| B3 queue status | GFX8 non-MES source and first recorded failure string | Original fence value/errno, first stalled queue and dispatch |
| B4 ordinary memory fences | Move/PT/CS producer→consumer chain source-mapped | Real broken edge or complete observed fence graph (not present in retained data) |
| T3 DPM/hardware | Observed pre-hang corruption | Original `sclk/mclk`, voltage, VRAM pressure or safe matched physical data, not anecdotal underclock response |
| T4 actual fix | RFC candidate only | Correct branch activated, compile/lockdep, no-regression and physical acceptance |

**No live GPU work, no kernel source write, no reset run and no successful kernel build claimed.**


## B1.1 — strict SVM notifier and KFD quiesce offline correlator

The implementation at [scripts/gfx803_kfd_event_correlation.py](../scripts/gfx803_kfd_event_correlation.py) consumes newline-delimited structured JSON events. It performs **no kernel tracing, GPU execution, driver writes or reset**. [Regression cases](../tests/test_gfx803_kfd_event_correlation.py) cover a positive two-range overlap and rejection of missing registration, missing return, wrong PASID, wrong mm, wrong boot, XNACK-on, plain MMU_NOTIFY_UNMAP and duplicate/invalid events.

**Required event keys:** capture_id, boot_id, mm_id, pasid, monotonic_ns, event. Event names are svm_range_register, svm_invalidate_enter, svm_invalidate_return, kfd_quiesce_begin, kfd_quiesce_end, userptr_get_pages_failed, hsa_memory_lock, hip_dispatch and gpu_ring_timeout. SVM events also require range_id, invalidation_id, notifier_event and xnack_off; quiesce events require quiesce_id and an end return_code if known.

An accepted ordering witness needs two **actually registered, distinct** SVM range identifiers in the same mm/PASID and boot, the first non-UNMAP/XNACK-off invalidation entering before quiesce, the second non-UNMAP/XNACK-off invalidation returning while quiesce remains outstanding, and the first quiesce end. Even such a witness remains an **ordering observation**, not automatically the original graphics corruption cause. Quiesce failure is never interpreted as a recovered GPU.

Use previously captured JSONL on a healthy host:

    python3 -m unittest discover -s tests -p 'test_gfx803_kfd_event_correlation.py' -v
    python3 scripts/gfx803_kfd_event_correlation.py --events /path/to/existing-events.jsonl --out /tmp/gfx803_svm_witness_new.json

**No such event stream survived the November GPU crash.** These inputs must be created with separately reviewed trace configuration on a recoverable host, then checked for completeness/drops and consistent monotonic clock domain. Listing available tracepoints is read-only; **enabling** ftrace is not. Missing events do not prove a negative when trace coverage is incomplete. Existing tests are committed, not claimed to have passed a Python or kernel test run.
