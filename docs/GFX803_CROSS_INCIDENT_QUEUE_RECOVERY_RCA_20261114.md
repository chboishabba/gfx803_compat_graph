# Cross-incident RCA: gfx803 ring/queue stall and non-durable GPU recovery

**Date:** 14 November 2026. **Status:** historical cross-incident signature established; common *underlying trigger* not established; repair candidate selection in progress. **Scope:** RX 580/Polaris, March 2026 and November 2026 incidents.

## 1. The problem is not merely TopK

The critical shared symptom is that an active compute or mixed compute/graphics workload is followed by a kernel GPU-ring timeout, incomplete or non-durable recovery, VRAM loss, and new graphics/compositor failures. Restarting Wayland is not equivalent to recovering hardware queues or graphics virtual-memory state. The desktop may need a host reboot even if a low-level reset stage reports success.

| Incident | First supported boundary | Queue/reset/recovery signature | Important missing detail |
| --- | --- | --- | --- |
| 20 Mar Ollama | Inference completed response then desktop artifact | `ring comp_1.3.1 timeout`, KIQ ring test `-110`, BACO, VRAM loss, repeated gfx timeouts | First bad command, original queue state, KFD fence return |
| 25 Mar Wayland | KWin named as timed-out submitter (not necessarily trigger) | `ring gfx timeout`, KIQ ring test `-110`, BACO, VRAM loss, repeated resets; shutdown shortly after | Whether graphics or concurrent compute caused original stall |
| 27 Mar WhisperX | `transcribe` started, no completion event | GPU reset/crash class | Exact device kernel and first failed KFD return |
| 30 Mar WhisperX | Some align failures; other long-file runs fail already in transcribe. One run: D2H/H2D waits followed by GPU hang; another: page-not-present and HIP event wait | `ring gfx timeout`, BACO, VRAM loss, repeated soft-recovered timeouts; profiler can alter outcome; blocking summary pass | No retained evidence that *this* run had KIQ `-110`, or the same internal KFD fence return as Nov |
| 14 Nov TopK | Pre-review wheel `[32,151936], k=50` hangs; `mbtopk` selected in retained source, not proven actual dispatch | First gfx timeout, explicit unsuccessful KFD queue preemption and `Failed to quiesce KFD`, KIQ `-110`, KCQ disable failure, BACO, VRAM loss, repeated gfx/comp timeouts; new Wayland session unusable | Original dispatched HSACO, KFD fence errno, pre-reset GPU VM condition |

Evidence:
- `docs/INCIDENT_2026-03-20_OLLAMA_MISTRAL_KFD_RESET.md`
- `docs/INCIDENT_2026-03-25_WAYLAND_GFX_TIMEOUT_RESET.md`
- `docs/INCIDENT_2026-03-27_WHISPERX_TRANSCRIBE_RESET.md`
- `docs/INCIDENT_2026-03-30_WHISPERX_ALIGN_GPU_HANG_AND_ROCPROFV3_SUCCESS.md`
- `docs/receipts/gfx803_topk_pr8_review_safe_20261114/kernel-previous-boot.log` and original incident note.

**This is not evidence of identical exact firmware or kernel fault across all incidents.** ROCm 6.x and staged 10.1 were involved in different periods; host kernels and userspace changed. It *does* make a single TopK algorithm bug or one user application an inadequate explanation of the recurring desktop-recovery failure class.

## 2. Failure tree / maximum common cut

```text
[Ollama GEMM | WhisperX copy/VM/compute | TopK source-selected mbtopk]
                      |
     first GPU kernel/VM/queue forward-progress loss     (cause differs or unknown)
                      |
     amdgpu ring timeout (gfx / compute; reported process may be victim)
                      |
     KFD/GFX8 non-MES queue preemption + GPU reset path
           |                       |
    unmap/query-status fence   KIQ/KCQ ring management
    (Nov: did not complete)    (Mar 20/25 + Nov: KIQ -110)
           \                       /
            GPU/queue recovery not durable
                      |
       BACO/soft-reset may report success
                      |
       VRAM lost; queue, VM, compositor state must recover
                      |
       stale/unusable graphics execution; repeats of gfx/comp timeouts
                      |
       restart display manager unsuccessful; full host reboot needed
```

The November exact CachyOS 7.3.0-2 source and module receipts establish the non-MES `unmap_queues_cpsch -> amdkfd_fence_wait_timeout` error-report path and both previously fixed gfx7/8 callbacks/queue validation. They **do not** establish an original return (`-ETIME` vs `-EIO` or other) or a universal KFD bug. The November first visible KFD quiesce failure *precedes* the logged KIQ -110; therefore KIQ failure should be examined as possible deeper shared hardware nonprogress or a downstream failure, not assumed initiating cause.

The older KFD doorbell callbacks return zero by design to protect an unconditional caller. They do not restore a stalled MEC/compute engine. Repatching their existence cannot explain the common symptom.

## 3. Three distinct root-cause questions

### T — Why does each workload stall originally?

- TopK: `mbtopk` is the strongest old-source candidate. The reviewed Schaka PR #8 forces sort-backed TopK, bypassing the selection families. This is a concrete **trigger workaround**, not a repair for the general recovery class.
- WhisperX: previously retained `hipMemcpyWithStream` / host `-1 ns` waits, page-not-present, asynchronous scheduling sensitivity and conditional improvement with `HIP_LAUNCH_BLOCKING=1`. These support GPU VM/queue progress and memory-transfer exposure but do not prove the copy itself caused the hang.
- Ollama/Wayland: repeated KIQ failure and gfx/compute ring timeouts exist; source kernel and provenance differ, so do not equate their trigger with WhisperX copy or TopK selection.

### Q — What makes compute/KFD queues fail to quiesce?

Source-targeted questions:
1. Was an unmap packet successfully submitted, and was `pm_send_query_status` issued?
2. Did the KFD fence fail because it never advanced before timeout, or because GPU reset/fatal state began? Capture source-specific return and timestamps.
3. Were MEC/HIQ/KIQ and KCQ able to make progress at the time, or did an earlier GPU VM fault prevent the engine from processing commands?
4. Does queue restoration assume a usable queue memory/VM mapping after VRAM loss that actually remains invalid?

**Do not import November's answer into March:** only November has an exact source-matched non-MES preemption log; March source/module and internal KFD returns are not equally proven.

### R — Why does successful low-level reset not restore desktop?

If BACO/GFX8 soft reset completes but queue re-creation, VM rebind, TLB invalidation, or graphics engine submission remains broken, `GPU reset succeeded` is not a functional recovery receipt. Confirm independently:
- KIQ/KCQ ring tests and queue submission progress after reset;
- KFD process queue suspend/resume and fence signaling;
- graphics VM rebinding and first post-reset command execution for KWin;
- whether original/hung compute process was destroyed and all old contexts evicted.

A practical **fix** should be evaluated at this recovery boundary: either restore usable graphics/compute ring and VM state or explicitly **fail closed** and reject new GPU work without misleading soft-recovery loops. Neither is proven by a simple callback stub.

## 4. Highest-information interventions, ordered

**No destructive desktop experiments:**

1. Use the already retained March and November journals to compile the ordered, first-error signature **per boot** (compute/graphics ring, GPU VA/fault, queue/preemption, KIQ, BACO, VM reinit, KWin). Distinguish *first failure* from *reset fallout*.
2. Source-diff March kernels against the verified November GFX8 KFD/AMDGPU implementation at `amdkfd_fence_wait_timeout`, `unmap_queues_cpsch`, queue reset, `gfx_v8_0_hw_fini`, KIQ test and process VM restoration. Identify shared uncorrected branch, not just strings.
3. Prepare but do not run the **reviewed** PR #8 wheel (with source/patch/build hashes), retain a model-level sort-based TopK workaround and existing WhisperX `HIP_LAUNCH_BLOCKING=1` bounded control as independent *trigger mitigations*. Successful workarounds cannot close R.
4. Evaluate upstream DRM wedge-handling design **offline**, not as an immediate RX 580 backport. Pierre-Eric Pelloux-Prayer's [9 Nov 2026 v4 wedge event series](https://www.mail-archive.com/amd-gfx@lists.freedesktop.org/msg155301.html) proposes rejecting further GPU work and signaling pending fences after a hang rather than allowing unlimited poisoned submissions; applicability to GFX8 and availability on deployed kernel require verification. It is not evidence of a fixed recovery mechanism.

**Only on a recoverable, independently managed GPU:**

5. Run a matched single-case A/B with external logs: reviewed sort-backed TopK versus old candidate when authorized, and bounded WhisperX serialized versus async; capture last dispatched command, non-progressing fence, first VM fault, *first* reset operation and post-reset queue health.
6. Test the selected **common reset-path** correction separately from either workload's trigger patch. Admission requires proof that post-reset KIQ/KCQ, KFD fence/queue and graphics VM all resume without Wayland being permanently wedged; mere `GPU reset succeeded` is insufficient.

## 5. Engineering disposition

- **Observed common class:** AMDGPU/GFX8 ring/queue nonprogress plus non-durable device recovery and graphics-context fallout.
- **Leading shared ownership:** amdgpu/amdkfd reset/preemption/queue/VM restoration, not necessarily a single implementation line or return code.
- **Strongest trigger-specific repairs:** reviewed gfx803 sort-backed TopK PR #8; bounded WhisperX serialization/copy/pressure controls.
- **Independent missing proof:** why queue/reset fails to recover consistently across workloads, and whether a fail-closed wedge policy prevents repeated corruption or a proper reset-path correction actually restores desktop functionality.
- **Safety:** one desktop RX 580 is not a recovery isolation environment. Do not reenact March/November destructive runs there.

The *primary programme* is common recovery RCA/fix; TopK and WhisperX are independent probes for that common failure class.
