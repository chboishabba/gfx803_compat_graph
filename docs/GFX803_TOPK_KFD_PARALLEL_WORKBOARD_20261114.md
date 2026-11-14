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
