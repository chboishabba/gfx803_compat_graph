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


## 3A. Source-level results: Linux v7.3 reference and the most promising repair candidates

A read of the SHA-verified CachyOS `7.3.0-2` release source (whose relevant
KFD files are byte-identical to Linux v7.3), not a generic current-kernel
example, found these **specific legacy orderings**:

1. `amdgpu_device_gpu_recover` calls `amdgpu_device_recovery_get_reset_lock` **before** `amdgpu_device_halt_activities`; the latter calls `amdgpu_amdkfd_pre_reset`. Yet `unmap_queues_cpsch` uses `down_read_trylock(reset_domain->sem)` and returns `-EIO` when denied. This is the exact structural issue AMD's [8 October 2026 v2 preemption-before-lock patch](https://lore-kernel.gnuweeb.org/amd-gfx/20261008140045.1283288-1-William.Palacek@amd.com/T/) addresses. The v7.3 PCI-error branch also has lock before halt.
2. In the same source, `amdgpu_device_gpu_recover` executes `amdgpu_device_sched_resume` **before** `amdgpu_device_gpu_resume`, which calls `amdgpu_amdkfd_post_reset`. AMD's [22 October 2026 callback-order patch](https://www.mail-archive.com/search?f=1&l=amd-gfx@lists.freedesktop.org&o=newest&q=date:20261022) proposes the opposite: finish KFD and display-audio callbacks before restarting DRM schedulers.
3. `restore_process_queues_cpsch` in v7.3 does not show the `amdgpu_in_reset -> -EAGAIN` early guard described in [5 September 2026's queue-restore-during-reset patch](https://lore-kernel.gnuweeb.org/amd-gfx/20260905043031.1015676-2-xiang.liu@amd.com/T/). This is a distinct stale-queue/mapping hypothesis.
4. Negative control: v7.3's `gfx_v8_0_mqd_init` **already exempts KIQ from compute quantum settings**, matching [Alex Deucher's GFX8 KIQ correction](https://git.zx2c4.com/wireguard-linux/commit/drivers/gpu/drm/amd/amdgpu?id=7346a046c6a9b9f30cb1f7d301449300a9174c71). Do not blame this absent fix on v7.3.

**Do not yet transplant the v7.3 result to the loaded CachyOS module.** The previous receipt hash-matched only a set of relevant source files, not a full build equivalence of these newly audited functions. Patch applicability must be checked against the exact downloaded source first.

### Extra evidence from the November *raw* journal

At **12:40:55**, the log states `qcm fence wait loop timeout expired`, then `unsuccessful queues preemption` and `Failed to quiesce KFD`. In v7.3's `amdkfd_fence_wait_timeout`, the *printed* qcm-timeout branch returns **`-ETIME`**. That is affirmative evidence for the **later** wave. The first 12:39:28 failed quiescence has no retained qcm-timeout line; its internal return is still unknown, and neither later `-ETIME` nor KIQ `-110` should be substituted for it.

The observed first 12:39:28 `unsuccessful queues preemption` proves that *some* invocation made it through to the fence wait/error branch; this is not explained by an immediate reset-lock read-lock denial alone. A reset-lock defect can still poison **subsequent** reset handling, particularly if pre-reset unmap is skipped while user queues remain active.

### Run this exact-source audit (CPU-only, no HIP, kernel change, or GPU activity)

```bash
set -euo pipefail
cd /mnt/truenas/comet-net/gfx803_compat_graph
git fetch --all --prune
git switch fix/topk-benchmark-fail-closed-20261114
python3 -m unittest discover -s tests -p 'test_gfx803_gfx8_reset_order_audit.py' -v

ROOT=/mnt/truenas/comet-net/experiments/gfx803_kfd_exact_kernel_20261114/cachyos-7.3.0-2-amd-kfd-source
python3 scripts/gfx803_gfx8_reset_order_audit.py \
  --source "$ROOT" \
  --release-receipt docs/receipts/gfx803_kfd_exact_release_doorbell_queue_20261114.json \
  --out /mnt/truenas/comet-net/experiments/gfx803_kfd_exact_kernel_20261114/gfx8_reset_order_audit.json
```

If one of the three named C files is absent from the previously *selective* release extraction, stop and extract it from the already SHA-verified release archive. Do not silently substitute an upstream source tree or mark missing files safe. The audit classifies source ordering and records per-file SHA-256; it does **not** prove the module was compiled from those exact bytes.

The CPU-only audit was run against that extracted release source: all six
audit contracts passed.  It records all three legacy orderings above and the
existing GFX8 KIQ quantum exemption in
`docs/receipts/gfx803_gfx8_reset_order_audit_20261114.json`.  It remains a
source result—not proof that the stripped, deployed module was rebuilt from
those bytes or that either ordering caused an incident.

**Important correction (14 November): do not backport the pre-reset-before-lock patch.** AMD's v1–v3 proposal was explicitly rejected in [12–13 October review](https://www.mail-archive.com/amd-gfx@lists.freedesktop.org/msg153142.html); the author dropped that approach. [v4 interrupt discard](https://www.mail-archive.com/amd-gfx@lists.freedesktop.org/msg153305.html) was also superseded by [v5: wait for reset completion before freeing a BO](https://www.mail-archive.com/amd-gfx@lists.freedesktop.org/msg153397.html), which addresses a diagnosed SDMA/writeback use-after-free during reset on **MI300X**. The accepted implementation is upstream commit [`47d799a718439764432d8ef3a0952af45f025f76`](https://git.zx2c4.com/wireguard-linux/commit/drivers/gpu/drm?id=47d799a718439764432d8ef3a0952af45f025f76) and was included in the [Linux 7.3.4 stable backport review](https://lore-kernel.gnuweeb.org/all/20261107135005.989518435@linuxfoundation.org/), **after** the incident's 7.3.0-2 package. Neither v4 nor v5 is a demonstrated solution for a Polaris reset/Wayland hang; do not attribute the November wedge to this memory-lifetime bug without its corresponding free/CPU fault evidence. The source audit establishes a candidate ordering/race surface, not a valid patch by itself.

**Revised implementation priority:** (1) read-only source/backport and patch-lineage comparison, including the reviewed post-reset callback-before-scheduler ordering proposal; (2) audit queue/VM/BO cleanup when reset is already active, and determine whether any relevant GFX8 paths actually reach the newer v5 memory-lifetime hazard; (3) test focused recovery corrections only on independently recoverable hardware; (4) treat an upstream wedge/fence fail-closed policy as containment, not a restored GPU. Do not install the NAK'd reset-lock patch on the display machine.

## 3B. Cross-distro and upstream-version reconciliation

**Scope correction:** CachyOS is a particular November kernel package, not the proposed root-cause owner. The user also reports earlier occurrences on ordinary Arch Linux. Some *March 2026* repo measurements explicitly identify `6.19.7-1-cachyos-bore`; do not relabel those original measurements as plain Arch or treat older Arch reports as if they were proven to use that same build. The oldest Arch-era KFD reset reports must retain their own kernel/build provenance, and the **2025 missing gfx7/8 SDMA callback fix** is a separately resolved regression, not proof that this newer failure uses that missing callback.

Independent source comparison against `torvalds/linux` immutable tags:

| Mainline tag | GPU recovery reset lock / KFD pre-reset | Scheduler restart / KFD post-reset | GFX8 KIQ compute-quantum exemption |
| --- | --- | --- | --- |
| `v6.13` | Lock **before** pre-reset (inline, lines 5879 and 5903) | DRM scheduler restarted before `amdgpu_amdkfd_post_reset` (around 6001/6033) | Absent |
| `v6.19` | Lock before `amdgpu_device_halt_activities` -> KFD pre-reset | `amdgpu_device_sched_resume` before `amdgpu_device_gpu_resume` | Absent |
| `v7.3` | Same ordering as v6.19 | Same ordering as v6.19 | **Present** |
| CachyOS `7.3.0-2` extracted source | Same as v7.3; 6/6 CPU-only source audit | Same as v7.3 | Present |

Source files: [v6.13](https://github.com/torvalds/linux/blob/v6.13/drivers/gpu/drm/amd/amdgpu/amdgpu_device.c), [v6.19](https://github.com/torvalds/linux/blob/v6.19/drivers/gpu/drm/amd/amdgpu/amdgpu_device.c), [v7.3](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_device.c). The GFX8 MQD setting comes from the corresponding `gfx_v8_0.c` at each tag; the comparison establishes **source ancestry**, not binary equivalence for a physical Arch installation.

The old ordering is thus **upstream and predates CachyOS's November build**. Conversely, the KIQ quantum exemption changed between v6.19 and v7.3, yet the November incident still logged a KIQ `-110`: that particular improvement was not sufficient to eliminate the observed RX 580 recovery-failure class.

Important qualifications:
- A source pattern across three tags can be an intentional legacy behavior or a defect; AMD's NAK means one tempting change is **not accepted as a repair**.
- The v5 memory-free patch concerns buffer lifetime during GPU reset, not demonstrated first-fault attribution of TopK, WhisperX, or KWin.
- The 2026 proposed user-queue/MES fixes for GC11/12 must not be assumed applicable to this **non-MES GFX8** device.
- The November later `-ETIME` fence-timeout evidence does not determine the first quiescence return.

## 3C. Completed priority C/D source-path comparison — stronger recovery-path failure mode

**See [GFX803_CROSS_VERSION_RECOVERY_C_D_AUDIT_20261114.md](GFX803_CROSS_VERSION_RECOVERY_C_D_AUDIT_20261114.md)** for original upstream v6.13/v6.19/v7.3 source references, exact branch ordering and missing evidence.

The highest-information finding is **an error-return propagation gap** predating the recent CachyOS package:

- `kgd2kfd_post_reset` calls `kfd_resume` for the KFD queue manager, returns an error if startup fails, and leaves the `kfd_locked` decrement untouched on that failure branch.
- `amdgpu_amdkfd_post_reset` returns the KFD status, but `amdgpu_device_gpu_resume` calls it without checking that return; the upstream device path uses this pattern in v6.13, v6.19 and v7.3.
- Thus a `GPU reset succeeded!` log is *not* equivalent to successful KFD queue restoration or a usable new graphics context. The wording may be emitted before KFD post-reset.
- **No historical KFD post-reset return has been captured**; source alone does not prove it failed during the November event.

Additional established details:

- November ran **BACO** as shown by its kernel journal and by `vi_asic_reset`'s exact log statement. The initial KIQ `-110` precedes that BACO operation, so BACO *exit* cannot by itself explain the first KIQ failure.
- GFX8 `gfx_v8_0_cp_test_all_rings` tests **gfx before KIQ before compute**; descriptions that call KIQ the 'first ring tested' are inaccurate.
- For Polaris10/11/12, the actual IP block is **`tonga_ih`**, not `cik_ih`. KFD has a separate interrupt FIFO; stale-event involvement remains a hypothesis.
- `kfd_process_wq_release` already waits on the reset workqueue before releasing process resources. The MI300X v5 buffer-free fix must be evaluated at its *specific* lifetime point, not assumed to provide the only reset-time wait.
- DRM scheduler workqueues restart before KFD post-reset finishes in all three upstream versions. This is a source-visible window; `kfd_locked` prevents the overly strong claim that ROCm user queues necessarily resubmit during that window.

**Revised repair cut:** first build a CPU-only/mock failure-path test for `kfd_resume != 0` and correct error propagation/unwind without leaking locks or starting DRM prematurely; then investigate queue-manager/VM recovery cause on an independently recoverable GFX8 machine. Capturing post-reset KFD return, queue-manager state, ring tests and actual fresh graphics-context usability is more discriminating than the reset-success line alone.

## 4. Highest-information interventions, ordered

**No destructive desktop experiments:**

The TopK benchmark now requires independently recoverable-host attestation for *all* GPU cases, not only known-fault cases 0/1/4. This guards against repeating the shared, workload-independent hard-reboot failure class.

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
