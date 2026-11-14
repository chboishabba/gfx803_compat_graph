# RX 580 / gfx803 — TopK trigger and KFD recovery parallel workboard

**As of 14 November 2026.** Working plan, not a claim of completed
kernel debugging. Owners: host operator performs **K1/K2** (matching
CachyOS kernel sources/symbols and historical attribution); compatibility
repository maintains the evidence graph, claim boundaries, review
handoff and implementation acceptance gates. **No risky GPU repro
on the sole display RX 580.**

## State already established

- **Source-owned artifacts:** `docs/receipts/gfx803_topk_pr8_review_safe_20261114/`:
  incident narrative, safe-unpatched CSV, failed cached pre-review
  patched-wheel CSV and hashed previous-boot kernel journal.
- The cached pre-review wheel completed `float32 [1,151936],k=50`,
  then `float32 [32,151936],k=50` returned
  `GPU Hang` / signal 6; reviewed-source helper+driver wheel **not** built/
  measured by that run.
- At **12:39:28** first retained ring gfx timeout names
  `kwin_wayland`, followed by unsuccessful queue preemption,
  `Failed to quiesce KFD`, `Failed to restore process queues`,
  `Failed to resume KFD`.
- At **12:39:29**, KIQ test fails `-110`, KCQ disable fails.
  GFX8 soft reset and BACO/overall reset can report success, yet
  `device wedged` continues. New Wayland session fails until reboot.
- Later KWin (VMID7/PASID7/TC3, address `0x0C000200`) and Plasma
  (VMID7/PASID15/TC3, address `0x00000027`) VM faults are
  **post-reset observations**, not proven TopK fault addresses.
- gfx7/8 missing SDMA doorbell callback patch
  `34659c1a1f4fd4c148ab13e13b11fd64df01ffcd` and distinct
  GFX7/8 queue-buffer validation patch
  `542c3bb836733a1325874310d54d25b4907ed10e` remain
  binary-provenance checks, not presumed current regressions.

## Parallel workstreams and exact acceptance gates

| ID | Owner | Dependency | Deliverable | Gate |
| --- | --- | --- | --- | --- |
| **K1.01** | Host | Incident boot known | Exact `uname -r`, installed `amdgpu.ko` path, package version, module build ID, matching CachyOS package/source revision, firmware provenance | SOURCE/MODULE MATCH **OPEN** |
| **K1.02** | Host | K1.01 | Matching debug symbols for exact kernel and module, source links, source→binary evidence; explicit `not available` if stripped/unmatched | SYMBOL MATCH **OPEN** |
| **K1.03** | Host | K1.01 | Source audit of `hqd_sdma_get_doorbell` implementation and registration in GFX7/8, plus separate queue validation implementation | CALLBACK/QUEUE PATCH PRESENCE **OPEN** |
| **K2.01** | Host | K1 source + retained journal | First failing `gfx_v8_0` soft-reset / KIQ ring test / KCQ disable source callsite and return propagation; distinguish `-ETIMEDOUT` from other errors | FIRST RECOVERY ERROR ATTRIBUTION **OPEN** |
| **K2.02** | Host | K2.01 | KFD `quiesce → restore process queues → resume` exact source functions and conditional branches, with call ordering against KIQ/KCQ failure | QUEUE-RESTORE CAUSAL CUT **OPEN** |
| **T1.01** | GPU-kernel/source audit | Old wheel/source identity | Map actual old-wheel `TensorTopK` shape route → selected algorithm and gfx803 HSACO/kernel; original binary and compiler hashes | FIRST GPU DISPATCH IDENTIFIED **OPEN** |
| **T1.02** | GPU-kernel/source audit | T1.01 | Classify `[32,151936],k=50` resource, grid, block, workspace/VA and synchronization vs smaller passing case; static inspection before any rerun | ROOT CAUSE CANDIDATE EVIDENCE **OPEN** |
| **T1.03** | Safe hardware only | Recoverable non-display GPU | Paired selected-kernel repro and correct `mbtopk` comparison with exact kernel traces and numerical checks; record any faults | TOPK CAUSAL REPRO **BLOCKED BY SAFE HOST** |
| **J1** | Compat integration | K1/K2/T1 receipts | Source-bound join of T1 first dispatch, T2 first failed recovery operation, original logs, source/module/build hashes | COMPARISON **OPEN** |
| **F1** | Kernel/TopK owner | J1 | Minimal patch for demonstrated cause(s), correct narrow TopK routing, and independent kernel regression if recovery defect confirmed | CAUSAL PATCHES **OPEN** |
| **V1** | Safe hardware | F1 | Non-destructive test gates, then bounded TopK GPU tests and independent recovery verification on safe host | HARDWARE VERIFICATION **OPEN** |
| **PR8** | Schaka reviewer | Reviewed wheel + V1 | Clean TopK-only upstream PR (no local scripts/AI docs), real unpatched/patched CSVs, large-input time/correctness | MERGE ACCEPTANCE **OPEN** |
| **B/C** | Release factory | V1 + stability atlas | Scoped stable Nix/Cachix release, original source build provenance and independent clean-client recovery | RELEASE **OPEN** |

**This is a dependency DAG, not a sequence that blocks all other
non-destructive development.** K1/K2 and T1 source-level examination
may proceed in parallel; existing read-only upstream HIP/ROCr test
inventory can proceed in parallel. GPU fault-inducing tests and
release promotion remain blocked.

## Minimum kernel handoff schema

Place any results in **new evidence files** under a distinct
`experiments/gfx803_kfd_exact_kernel_20261114/` path. Do not mutate
the committed original crash receipts. Required fields in
`kernel_source_handoff.json`:

```json
{
  "schema": 1,
  "status": "unverified",
  "incident_kernel_release": "7.3.0-2-cachyos-bore",
  "running_module_path": null,
  "running_module_sha256": null,
  "running_module_build_id": null,
  "source_repository": null,
  "source_commit": null,
  "source_package_sha256": null,
  "symbols_path": null,
  "symbols_build_id": null,
  "binary_source_match": false,
  "gfx8_sdma_callback": {"implemented": null, "registered": null, "called_in_incident": null},
  "gfx8_queue_validation": {"present": null, "called_in_incident": null},
  "reset_callchain": [],
  "first_recovery_error": null,
  "journal_sha256": "be965c117fc7fd2a815a843b63b3ad807d9e88ae43ffff33495cb82043fc70f6",
  "gpu_rerun": false,
  "conclusions": []
}
```

`null` is **unknown**; `false` requires positive contrary evidence.
A missing symbol tree is not evidence that the implementation is
absent. `called_in_incident` needs an actual call trace/dump, not
a matching source definition. A source build ID alone cannot
prove the historically executing module unless tied to its
specific installed artifact.

For each reset call-chain node record: full function, exact source
path+line/revision, parent/callee, return/error handling, evidence
type (`journal`, `matching-source`, `vmcore`, `trace`),
and whether that edge was observed at runtime or only statically
reachable.

### Read-only, no-GPU commands on the host

```bash
KREL=$(uname -r)
printf 'kernel=%s\n' "$KREL"
modinfo -n amdgpu
modinfo -F vermagic amdgpu
readlink -f "/usr/lib/modules/$KREL/build"
ls -l "/usr/lib/debug/lib/modules/$KREL/vmlinux" 2>&1 || true
journalctl --list-boots
sha256sum docs/receipts/gfx803_topk_pr8_review_safe_20261114/kernel-previous-boot.log
```

If `modinfo` shows a currently running module **after reboot**,
label it `postboot_module`; establish the incident-boot module
separately (package history/boot entries/module artifacts) before
asserting a source/build match. No `amdgpu` unload, PCI reset,
GPU tests, SDDM restart or dangerous queue-reset injections are
authorized by this workboard.

## T1 TopK static handoff

For the old cached wheel, record: `torch` wheel SHA, source commit
used to build it, original `TensorTopK.cpp`/sort implementation,
ABI/runtime closure/loaded ROCm libs, `[1,151936]` pass versus
`[32,151936]` failure, `float32,k=50`, candidate dispatch
branch, selected GPU kernel/HSACO identity, relevant resource and
grid/queue assumptions, and **confidence for each inference**.
Use Ghidra only if exact source/compiler artifacts do not already
explain the compiled code. No default assumption that GPU ring
timeout came from the reported `kwin_wayland` ring job.

## J1 join / stop rules

The first event shown by the kernel journal is the first **retained**
timeout, not necessarily the first causal GPU dispatch. Preserve
separate timelines: TopK process, `kwin_wayland` gfx job,
KFD queue management, and post-reset `plasmashell` VM faults.

- Do not classify `GPU reset succeeded` as recovery admitted if
  rings/Wayland remain wedged.
- Do not infer that the old gfx8 doorbell patch is missing merely
  because KFD restore fails.
- Do not equate a working seven-case HIP/HSA smoke with durable GPU
  queue/reset recovery.
- If the incident's module/source match is unavailable, stop at
  a source-hypothesis rather than claiming an exact kernel bug.
- No destructive GPU repro on the display card until independent
  recovery has been demonstrated.

## Next review point

When K1/K2 arrive, merge the source-grounded error path into
`docs/GFX803_TOPK_KFD_RESET_FORENSICS_20261114.md`, reconcile
with static TopK dispatch and update the phase acceptance table.
Do not modify Schaka PR #8 with kernel-recovery speculation.


## 14 November — K1/K2 evidence ingest: commit `07a52c7`

[Committed kernel handoff](receipts/gfx803_kfd_kernel_source_handoff_20261114.json)
establishes more than the previous hypothesis-only workboard:

| Gate | Evidence / disposition | Remaining precision |
| --- | --- | --- |
| **K1.01 module inventory** | **Recorded:** `7.3.0-2-cachyos-bore`; compressed `amdgpu.ko.zst` SHA-256 `044c65a459798f469a3d3d4fb0ff6af975dceaed972ba5f5285359f12de3c2dd`; decompressed SHA-256 `20df0ac89a22e67b94bb24158092a77ec593616c518338747f8618eda4f5d35f`; module build ID `e18feec811ec99ec54d951f502a8cffe882c8d9b`. Kernel build ID recorded separately. | Confirm incident-boot binary identity if module installed after reboot differs; **exact CachyOS source package match OPEN** |
| **K1.02 symbol/debug inventory** | Module symbol visibility supports callback presence; GDB-MCP registered on host | No matching DWARF in installed kernel/module; exact symbol-to-source line and locals OPEN |
| **K1.03 gfx8 callback** | **Present in module and registered in upstream v7.3 reference**; `gfx_v8_kfd2kgd` selects Polaris | Actual incident invocation **UNKNOWN**, not false; exact distro backport/source equivalence OPEN |
| **K2.01 logged failure** | **First retained KFD recovery error identified:** `Failed to quiesce KFD` following first KWin `ring gfx timeout` at 12:39:28 | First failing internal call/return branch OPEN; first *logged* error is not a full stack |
| **K2.02 downstream chain** | KFD process-queue restore/resume, KIQ ring test `-110`, KCQ disable and persistent post-reset wedge retained | Which operation precipitated restore failure versus which merely followed already-dead ring hardware OPEN |
| **T1** | Original benchmark and GPU hang remain source/shape bound | Initial TopK kernel/HSACO and first non-progressing dispatch **OPEN** |

**Original evidence record:** `07a52c7`. The handoff was
corrected on `master` after ingestion because `called_in_incident:
false` incorrectly implied demonstrated non-invocation; it is now
`null` (unknown). The immutable original commit remains available.

**Source qualification:** reference Linux v7.3 at
`c03c1a14507dfaf8b856c2608f9ac216021fc222` is *not* proof of
identical CachyOS source code; `source_package_exact_match=false`
in the receipt must remain visible. The recorded module build ID
provides a key for finding exact matching symbols, not DWARF itself.

### Next non-GPU max-cut (K2.03)

1. Locate the source statement that emits `Failed to quiesce KFD`
   in the **exact CachyOS patchset**, then follow the direct
   callee/error return chain into queue preemption.
2. Resolve the source site that prints `ring kiq_0.2.1.0 test
   failed (-110)`; determine whether this error occurs during
   teardown/reset or subsequent ring bring-up, from original
   call order rather than assuming it is the first failure.
3. Resolve `KCQ disable failed` and restore/resume prints
   to source and create a structured sequence of observed
   timestamp vs statically reachable function, retaining that
   the original journal did not record a full call stack.
4. For stripped symbols use **module build ID + ELF symbol table
   and code disassembly** in read-only GDB; inspect exact
   source/build metadata or debug-symbol build packages for
   function+line mapping. Ghidra is a fallback for binary
   control-flow, not proof of incident-time invocation.
5. Keep T1 TopK GPU dispatch as a separate causal target;
   avoid rerunning the known display-wedging case.

**Definition of completion:** precise first failing **internal**
KFD function/branch supported by a trace, matching binary/source,
or negative/positive instrumentation on recoverable hardware.
The first retained printed error alone does not close K2.


## 14 November — K2.03 mapped: userptr-triggered queue eviction

**Evidence:** commit `43e70ef`, source handoff
`docs/receipts/gfx803_kfd_kernel_source_handoff_20261114.json`.

Static upstream v7.3 control-flow mapping from the handoff:

```text
amdgpu_amdkfd_gpuvm.c:2535
  kgd2kfd_quiesce_mm(mm, KFD_QUEUE_EVICTION_TRIGGER_USERPTR)
    kfd_device.c:1200 → kfd_process_evict_queues(p, trigger)
      kfd_process.c:2075 → dqm->ops.evict_process_queues(dqm, qpd)
        nonzero error (other than -EIO in the mapped reporting branch)
          → Failed to quiesce KFD
```

**K2.03 = source branch mapped, NOT dynamic error attribution.**
The original journal establishes the failure print, not its internal
return code or the exact DQM implementation entered on the incident
kernel. Source/package exact match is still false; no GPU rerun.

| Next gate | Concrete task | Required evidence |
| --- | --- | --- |
| **K2.04a DQM dispatch** | Determine registered `evict_process_queues` implementation for the real Polaris KFD DQM mode; inspect both available scheduler/queue-manager paths rather than guessing | Exact source callback assignment + matching binary symbol/call target |
| **K2.04b DQM failure returns** | Enumerate every *reachable* nonzero return and its callee: process eviction preconditions, queue preemption/dequeue, HWS packet or interrupt wait, MES/direct queue mechanism as applicable to this GFX8 build | Function-by-function error propagation matrix; distinguish observed from statically possible |
| **K2.04c precedence** | Compare the 12:39:28 `Failed to quiesce KFD` against the subsequently logged KIQ `-110`, KCQ disable, and restoration/resume failures | Event order backed by preserved journal; do not infer prior internal success/failure from later errors |
| **K2.04d exact module/build** | Resolve real `7.3.0-2-cachyos-bore` source/binary equivalence and available debug symbols; use Build ID for read-only disassembly if source differs | Build/package match or explicitly bounded upstream-reference conclusion |
| **K2.04e dynamic return** | If still unknowable from retained evidence, design *future* minimal return tracing on independently recoverable host | Capture DQM return value and first failing child call, no tracing on display GPU during a destructive reproducer |

**Do not** assign KIQ `-110` as the quiescence return code merely
because it appears later. **Do not** equate a static `-EIO`
exclusion with the actual returned value. Dynamic callback invocation
of the historical gfx8 SDMA doorbell patch remains unknown. T1
TopK first GPU dispatch also remains OPEN.

**Decisive acceptance:** for **K2.04**, name the selected DQM
implementation, enumerate its concrete failure branches and identify
which can propagate to the reported log; for **K2.05**, establish the
actual incident-time DQM error/operation from trace or preserved
dump. If the historical journal cannot support K2.05, record
`unrecoverable-from-existing-evidence` and pursue safe future
instrumentation, not a guessed fix.


## 14 November — K2.04 source-mapped MES queue removal (commit `635b40c`)

The operator's committed handoff now records the Polaris configuration:

```text
polaris10 / gfx_target_version=80003
sched_policy=0, uni_mes=1

dqm->ops.evict_process_queues
  → evict_process_queues_cpsch
    → remove_queue_mes
      → adev->mes.funcs->remove_hw_queue
        on nonzero MES removal result:
          → reset_queues_mes
          → potential kfd_hws_hang escalation if GPU recovery enabled
```

**K2.04 = selected path SOURCE-MAPPED** for the recorded live
configuration. Neither the exact CachyOS source package nor an
incident-time call trace is present; the original journal does not
record the `remove_hw_queue` return. Thus this is **not**
proof that `remove_hw_queue` itself failed during the incident.
It remains the first specific return boundary to investigate.

| Gate | Status | Next decisive artifact |
| --- | --- | --- |
| **K2.04** Polaris MES eviction dispatch mapping | SOURCE-MAPPED from recorded config and reference source | Confirm exact source/binary implementation and any alternate pre-MES failure branches |
| **K2.05a** actual `remove_hw_queue` invocation and return | OPEN | Incident-time trace/vmcore or bounded `unknown from retained journal` |
| **K2.05b** MES removal failure vs `reset_queues_mes` result | OPEN | Separate returned error at removal, reset and `kfd_hws_hang` escalation, where observable |
| **K2.05c** hardware/firmware vs queue state | OPEN | Distinguish MES ring/firmware timeout, queue mapping/preemption and device-level loss of forward progress |
| **T1** first TopK GPU kernel | OPEN | Actual cached-wheel dispatch/HSACO, selected launch and resources |
| **F1** minimal causal repair | BLOCKED | Evidence supporting specific failed operation, not a speculative doorbell/backport patch |

**Priority ordering:** determine source-level `remove_hw_queue`
implementation and its possible errors, then source-level
`reset_queues_mes` escalation/termination. Do not substitute the
later KIQ `-110` for the unknown MES removal return: it was logged
after the first KFD quiescence failure. No destructive rerun is
authorized on the sole display RX 580.

**Handoff source:** `docs/receipts/gfx803_kfd_kernel_source_handoff_20261114.json`;
the `live_polaris_runtime` object explicitly labels the path
`inferred_eviction_implementation`, not observed invocation.
