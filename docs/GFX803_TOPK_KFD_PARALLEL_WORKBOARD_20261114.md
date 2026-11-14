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


## 14 November — K2.04 conditional MES queue-removal hypothesis (commit `635b40c`)

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

**K2.04 = conditional source hypothesis, not selected incident path.**
The current post-reboot parameters (`sched_policy=0`, `uni_mes=1`) select the
MES removal branch in the v7.3 reference source. However, that same reference
emits the retained incident text `The cp might be in an unrecoverable state due
to an unsuccessful queues preemption` only from the *non-MES*
`unmap_queues_cpsch` fence-timeout branch. Therefore the post-reboot parameter
observation and retained journal cannot together prove a MES
`remove_hw_queue` failure. The possible explanations are an incident-time
state change, CachyOS source divergence, a different queue/device path, or an
incomplete retained log. Neither the exact CachyOS source package nor an
incident-time call trace is present.

Read-only GDB disassembly of the extracted post-reboot module confirms that
`evict_process_queues_cpsch` contains both the MES
`remove_queue_mes_on_reset_option` call and the non-MES
`unmap_queues_cpsch` call. It therefore confirms compiled branch availability,
not the branch selected in the incident.

| Gate | Status | Next decisive artifact |
| --- | --- | --- |
| **K2.04** Polaris MES eviction dispatch mapping | CONDITIONAL: selected by post-reboot parameters, contradicted by the retained v7.3 log site | Resolve incident-time state/source and alternate non-MES path |
| **K2.05a** actual `remove_hw_queue` invocation and return | OPEN | Incident-time trace/vmcore or bounded `unknown from retained journal` |
| **K2.05b** MES removal failure vs `reset_queues_mes` result | OPEN | Separate returned error at removal, reset and `kfd_hws_hang` escalation, where observable |
| **K2.05c** hardware/firmware vs queue state | OPEN | Distinguish MES ring/firmware timeout, queue mapping/preemption and device-level loss of forward progress |
| **T1** first TopK GPU kernel | OPEN | Actual cached-wheel dispatch/HSACO, selected launch and resources |
| **F1** minimal causal repair | BLOCKED | Evidence supporting specific failed operation, not a speculative doorbell/backport patch |

**Priority ordering:** first resolve the MES/non-MES contradiction using the
exact CachyOS source/module or a safe-host trace. Only then investigate the
applicable `remove_hw_queue` or compute-scheduler preemption return. Do not
substitute the later KIQ `-110` for either unknown return: it was logged after
the first KFD quiescence failure. No destructive rerun is authorized on the
sole display RX 580.

**Handoff source:** `docs/receipts/gfx803_kfd_kernel_source_handoff_20261114.json`;
the `live_polaris_runtime` object records a conditional MES path, not an
observed invocation.

## K2.06 / T1.04 correction — source-and-binary attribution

`uni_mes=1` was previously treated as selecting the MES KFD path on Polaris.
That was incorrect. In reference Linux v7.3, `amdgpu_discovery_set_mes_ip_blocks`
sets `adev->enable_mes` only for GC11/GC12; `uni_mes` is consulted only in the
GC12 cases for `enable_uni_mes`. `amdgpu_amdkfd_device_init` copies
`adev->enable_mes`, not `uni_mes`, into KFD shared resources. Thus GFX8 uses
the non-MES `execute_queues_cpsch` → `unmap_queues_cpsch` path in that source,
which matches the retained fence-timeout diagnostic. This is a
source-reference conclusion; the exact CachyOS source/incident return remains
unmatched.

The retained pre-review TopK source similarly narrows both large test shapes
to **mbtopk**: the manual patch declines warptopk, and the multi-block
heuristic is true for both 1×151936 and 32×151936. The hashed HIP ELF contains
mbtopk symbols, but no trace identifies its executed HSACO/kernel. The full
claim boundary is in
`docs/receipts/gfx803_k205_t104_source_binary_attribution_20261114.json`.


## 14 November — K2.05/T1 implementation sprint landed

Five standalone Python tools, all within this compatibility repo and
not Schaka's PR #8:

- scripts/gfx803_kfd_incident_offline_audit.py: original journal SHA
  verification, first-error chronology, separated current-vs-historic
  configuration and fail-closed state.
- scripts/gfx803_kfd_trace_boundary.py: default read-only available
  probe/symbol inventory; optional explicit root-bound temporary
  entry/return kprobes, ten-second idle capture and scoped cleanup;
  **never starts a GPU workload**.
- scripts/gfx803_topk_binary_offline_audit.py: original wheel/overlay
  source, ELF and optional code-object SHA, candidate TopK route
  markers and lower-bound [1,151936] vs [32,151936] buffer sizing.
  Static inventory is not proof of selected kernel.
- scripts/gfx803_kfd_binary_branch_audit.py: exact compressed module,
  decompressed module and Build ID comparisons before offline
  objdump call-site and conditional-branch inventory.
- scripts/gfx803_kfd_topk_evidence_join.py: SHA-bound aggregation,
  preserving incident MES/non-MES branch and TopK trigger UNKNOWN,
  K2.05/T1 OPEN and release BLOCKED.

CPU-only synthetics:
tests/test_gfx803_kfd_topk_offline_cut.py. These are **committed,
not yet executed on the RX 580 host**. Run commands and safe stop
rules are in
[the implementation runbook](GFX803_K205_T1_IMPLEMENTATION_RUNBOOK_20261114.md).

**Sprint acceptance:** code and offline tests source-written;
physical/static host run results PENDING. No destructive GPU repro,
new kernel patch, inferred historical MES dispatch, or claim of
debugger attachment. Continue exact old wheel mapping and K2.05
return discrimination only after original receipts are run and
inspected. This adds tooling without changing the existing
K2.04 contradiction or closing K2.05.


## 14 November — offline cut physically executed (`39471ee`)

Host operator reports the K2.05/T1 offline suite **12/12 passed**.
Original previous-boot journal SHA and exact postboot AMDGPU module
SHA/Build ID verified. Disassembly confirms both MES and non-MES
compiled eviction paths. TopK audit is now **scoped to
`libtorch_hip.so`** (recorded SHA-256 prefix `dd0b4030`),
avoiding unrelated NFS reads of `libtorch_cpu.so`.

Original receipts (host-local, **not** assumed uploaded/committed):
`/mnt/truenas/comet-net/experiments/gfx803_k205_t1_static_20261114/`.
Do not claim receipt contents beyond the operator's reported outcomes
without opening those original JSON files.

**Accepted now:** offline code/test execution and binary provenance.
**Still OPEN:** exact incident boot's effective `uni_mes`/
scheduling policy and selected DQM branch; actual eviction
return; initial TopK kernel/HSACO; exact CachyOS source-package match;
post-hang KFD recovery root cause and stable GUI restoration.

**Next decisive route:** (1) search exact incident-time
initramfs/bootloader/module-load/recorded state artifacts using only
read-only operations; (2) statically map cached `libtorch_hip.so`
TopK call graph, embedded HSA GPU code objects, registration symbols
and source revision; (3) if historical state cannot be recovered,
design a **non-display, recoverable-host** trace that records the
selected branch, entry/return, first GPU dispatch and ring/queue
state. Do not equate a successful idle trace with fault reproduction.
No known-wedging TopK run on the sole display GPU.


## 14 November — T1.05 compiled mbtopk offline investigation implemented

The executable maximum cut now targets the exact candidate
`libtorch_hip.so` from the retained `7e0d5dd` attribution
receipt. Tools added:

- `scripts/gfx803_mbtopk_elf_attribution.py`: fail-closed
  original binary SHA and Build ID check, `readelf` TopK
  symbol/section inventory, optional bounded
  `.hip_fatbin` extraction, original source SHA/marker inventory,
  1-row/32-row arithmetic resource bounds.
- `scripts/gfx803_mbtopk_fatbin_scan.py`: ELF64 AMDGPU
  candidate detection with section/program-header extent validation
  and optional bounded extraction. Candidate inclusion **is not**
  incident-time execution or even necessarily a gfx803 target.
- `tests/test_gfx803_mbtopk_offline_attribution.py`: CPU-only
  synthetic SHA-mismatch, ELF parse, embedded candidate and
  source/link-negative tests.
- Extended `scripts/gfx803_kfd_topk_evidence_join.py`:
  evidence-bound K2.06 non-MES reference conclusion,
  T1.04 source candidate, T1.05 verified ELF inclusion,
  explicit T1.06 build link and T1.07 selected dispatch still OPEN.

See [the runnable runbook](GFX803_T105_K206_MBTopK_BINARY_MAXCUT_20261114.md)
for a single CPU-only command sequence. All scripts and tests are
**committed, not yet executed on the TrueNAS host**. Results,
actual HSACO metadata, original build provenance, dispatch and
KFD incident return are pending. No GPU/HIP workload or kernel
patch has been performed.

## 14 November — T1.05 host audit completed

The CPU-only host cut completed with **25/25 focused tests passing** (12
ELF/fatbin tests and 13 prior KFD/TopK tests).  A legitimate large-ELF
condition in the first runner attempt was corrected before accepting the
receipt: the runner now streams all TopK-matching `readelf` lines, records
their full count separately from its 300-line evidence display, and excludes
ordinary `.rodata` from offload-section classification.

The source-bound candidate identity was reconfirmed: `libtorch_hip.so` SHA-256
`dd0b4030c4034fdab10daa48dd260397f4de2348ad1cec7ef95474ebd05fa0d2`, Build
ID `392fee76f7a23e82b345dae1b40d02bd0ea32cd5`; its sole `.hip_fatbin` payload
is 42,919,798 bytes with SHA-256
`35733398518e0a82aadbf64a7f9e80874069f4da40e401b4bf772cab37623de3`.

The bounded structural scanner found zero directly embedded ELF64/AMDGPU
candidates.  That is not a negative dispatch result: the payload may use a
wrapper or compression that this scanner intentionally does not decode.
It leaves T1.06 (build linkage), T1.07 (selected HSACO/kernel), K2.05 and J1
open.  The superseding host-local outputs are under
`/mnt/truenas/comet-net/experiments/gfx803_t105_k206_20261114_r2/`; no GPU,
HIP, tracing or kernel mutation occurred.


## T1.08 compressed/offload bundle inspection (after `052889b`)

The 25/25 passed host offline suite verified the HIP binary and
extracted a 42.9 MB .hip_fatbin. Failure to locate raw embedded
ELF is inconclusive for Clang's CCOB compressed or uncompressed
offload bundle container. The new `gfx803_mbtopk_offload_container_audit.py`
classifies header magic, parses bounded bundle/CCOB metadata,
optionally asks `clang-offload-bundler --type=o --list` for
supported architecture IDs, and only unbundles an explicitly
advertised unique gfx803 target. It never invokes HIP or GPU
work. Tests and commands: `test_gfx803_mbtopk_offload_container.py`
and `GFX803_T105_K206_MBTopK_BINARY_MAXCUT_20261114.md`.
Do not commit the entire 42.9 MB payload if small JSON receipts
can answer architecture/metadata questions.

T1.08 tool source implemented; host acceptance pending.
T1.07 incident kernel dispatch and K2.05 original fence errno OPEN.

## 14 November — T1.08 CCOB and gfx803 code-object inventory

The matching staged ROCm 10.1 `clang-offload-bundler --list` identifies one
unique `hip-amdgcn-amd-amdhsa--gfx803` target, occurring 219 times alongside
219 host bundles.  The tool's HIP-target parser was corrected after it
incorrectly excluded the `hip-` spelling; it now records unique target IDs and
occurrence counts.

Offline unbundling of that explicit target produced a local 5,246,152-byte
AMDGPU ELF with `gfx803` header flags and SHA-256
`3aacb81a0c571c10d842922935db1f248a59602746d0497f5aa383fad101a0c8`.
It establishes packaged gfx803 code-object inclusion, not incident execution.
No readable `mbtopk`, `topk`, or `gather` name appears in the static
symbol/metadata scan, so the actual candidate kernel remains unselected.
Only small JSON receipts are committed; the 42.9 MB fatbin and 5.25 MB code
object stay host-local. No GPU/HIP runtime execution occurred.


## 14 November — T1.09–T1.12 / K2.07–K2.08 complete offline implementation

**Source has landed; this new suite has NOT been executed on the
RX580 host yet.** Start with the one-command no-GPU runbook:

[GFX803_T109_K207_FULL_OFFLINE_HANDOFF_20261114.md](GFX803_T109_K207_FULL_OFFLINE_HANDOFF_20261114.md)

New code:

1. gfx803_mbtopk_hsaco_metadata.py — strict unbundled HSACO
   SHA, size, ELF e_machine; readelf/LLVM note/section/symbol
   and kernel metadata extraction.
2. gfx803_amdgpu_msgpack_notes.py — bounded pure-Python ELF PT_NOTE
   AMDGPU MessagePack metadata parser and kernel resource fields.
3. gfx803_mbtopk_retained_source_audit.py — exact original
   TensorTopK.hip SHA gate, source launch/heuristic excerpts and
   explicitly supplied original build-log hints.
4. gfx803_mbtopk_kernel_disasm.py — optional exact metadata-symbol
   bounded llvm-objdump and static instruction classification.
5. gfx803_kfd_nonmes_source_audit.py — targeted source-only
   non-MES fence/preemption diagnostic evidence, with no inferred errno.
6. gfx803_kfd_safehost_trace_plan.py — inert return-probe source
   and six-way dedicated host eligibility checklist. No probes attached.
7. gfx803_t109_k207_final_join.py — SHA-bound source/ELF/fatbin/HSACO
   evidence chain with T1.06/T1.07/K2.05 still OPEN and release blocked.
8. run_gfx803_t109_k207_offline.sh — one-command CPU-only host pipeline.

CPU-only tests cover note parsing, identity refusals, messagepack
bounds, source hashes, kernel symbol validation, safe-host default
denial and evidence-join error rejection. **No test pass count is
claimed for these newly committed tests until the operator runs them.**

### Gating

T1.08 CCOB/gfx803 inclusion ACCEPTED from a45ad49 (33/33 earlier
tests). T1.09/T1.10/T1.11/T1.12 offline metadata/ISA acceptance
PENDING. T1.06 original build-to-benchmark-loader provenance OPEN;
T1.07 selected first stalled kernel/HSACO OPEN. K2.06 source
non-MES fence alignment exists; K2.05 historical internal return
OPEN, K2.07 exact source match/return OPEN. Do not substitute a
future trace for missing historical Nov 14 capture. K2.08 safe
dedicated-host tracing gated and NOT started.

**Do not** run the destructive 32×151936 TopK on the display RX580.
Do not upstream these forensic scripts via Schaka PR #8.


## 14 November — T1.13/14 multi-CCOB member maximum cut

Commit 11223f6 physically ran 61/61 CPU-only contracts and
committed four original T1.09/K2.07 receipts under
docs/receipts/gfx803_t109_k207_host_20261114/.
The SHA-verified gfx803 HSACO was decoded as **336 kernels,
zero readable TopK-name matches**; LLVM's specific metadata
option was unavailable, while the pure-Python AMDGPU MessagePack
decoder succeeded. Original retained TensorTopK.hip SHA
acb592c2… verified (6 source spans, 226 selected lines).
The existing join correctly leaves T1.06/T1.07/K2.05 open.

The next cut is the **219-member offload format**, not another
generic device reset experiment:
- scripts/gfx803_ccob_member_index.py: SHA-verified CCOB v2/v3
  indexing, authoritative member-size boundaries, bounded
  inter-member padding inspection (never search inside compressed
  bytes for CCOB magic).
- scripts/gfx803_ccob_all_members_topk.py: offline per-member
  clang-offload-bundler invocation, SHA and AMDGPU MessagePack
  metadata, each member's readable TopK kernels, checkpointed
  bounded JSON receipts.
- tests/test_gfx803_ccob_member_index.py and
  tests/test_gfx803_ccob_all_members.py: collision, padding,
  bad identity, partial-scan and CPU-only batch tests.
- Runbook:
  [GFX803_T113_T114_CCOB_ALL_MEMBERS_20261114.md](GFX803_T113_T114_CCOB_ALL_MEMBERS_20261114.md).

**New code committed, host acceptance PENDING.** The 61/61
pass count pertains to 11223f6, *not* these new tests.

Even 219/219 fully decoded members would only establish code-object
inclusion and metadata, not original incident-time selected kernel,
benchmark-loaded wheel linkage or KFD's missing internal fence
return. T1.06/T1.07/K2.05/J1/F1/release stay OPEN/BLOCKED
according to original receipts. No new GPU work or KFD patch.
