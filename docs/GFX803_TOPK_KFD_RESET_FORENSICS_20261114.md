# RX 580 TopK → KFD/AMDGPU recovery incident: debugger and repair plan

**14 November 2026; no new GPU execution or repair implied.**

## Incident identity

- Host/card: `cachy-lambo`, RX 580 / gfx803, display-attached card.
- Host kernel at incident: `7.3.0-2-cachyos-bore`.
- Original 14 November assay: unpatched Schaka ROCm 10.1 selected safe
  TopK cases passed; the *cached pre-review patched* TopK wheel completed
  float32 `[1,151936]`, k=50, median 0.4008 ms and then hung on
  float32 `[32,151936]`, k=50. This wheel predates Schaka's requested
  `getCUDAHooks().isGPUArch()` + patch-driver revision.
- GPU health check also blocked; kernel logged GPU Hang, device coredump,
  `ring gfx` / `ring comp_1.0.1 timeout`, reset and KFD
  quiesce/queue-restore/resume failures. Plasma Wayland could not
  restart, and a reboot was required.
- First-party operator retained:
  `/mnt/truenas/comet-net/experiments/gfx803_topk_pr8_review_safe_20261114/INCIDENT_20261114_GPU_HANG.md`
  and a partial patched benchmark CSV. Full preceding/failed boot journal
  and coredump availability require verification.

**Two separate targets:** (T1) first nonprogressing TopK dispatch,
and (T2) failure to quiesce/reset/restore user queues after T1. The
2025 `hqd_sdma_get_doorbell` gfx7/8 missing-callback fix
(`34659c1a1f4fd4c148ab13e13b11fd64df01ffcd`) is relevant
history for T2, **not proof that it regressed**. The GFX7/8 ring-buffer
validation fix (`542c3bb836733a1325874310d54d25b4907ed10e`) is
also a separate question.

## P0: read-only forensic preservation; no GPU commands

Run from the **rebooted healthy host**, and store only in a new path.
Do not launch old patched `[32,151936]` or known-fault TopK cases.

```bash
set -euo pipefail
OUT=/mnt/truenas/comet-net/experiments/gfx803_topk_pr8_review_safe_20261114
EVID="$OUT/postboot_forensics_20261114"
test ! -e "$EVID" || { echo "Refusing to overwrite $EVID" >&2; exit 1; }
mkdir -p "$EVID"
uname -a > "$EVID/uname.txt"
cat /proc/cmdline > "$EVID/kernel-cmdline.txt"
journalctl --list-boots > "$EVID/journal-boots.txt"
journalctl -k -b -1 --since '2026-11-14 12:38:00' \
  --until '2026-11-14 12:44:00' --no-pager -o short-iso \
  > "$EVID/kernel-previous-boot.log"
journalctl -b -1 --since '2026-11-14 12:38:00' \
  --until '2026-11-14 12:44:00' --no-pager -o short-iso \
  > "$EVID/all-previous-boot.log"
modinfo -n amdgpu > "$EVID/amdgpu-module-path.txt"
modinfo amdgpu > "$EVID/amdgpu-module-info.txt"
readlink -f /sys/module/amdgpu > "$EVID/amdgpu-sysfs-path.txt" || true
find "$OUT" -maxdepth 2 -type f -printf '%p %s bytes\n' \
  > "$EVID/incident-inventory.txt"
(
  cd "$EVID"
  sha256sum *.txt *.log > SHA256SUMS
)
```

**Important:** `-b -1` refers to the immediately preceding boot,
not intrinsically to the incident. Verify `journal-boots.txt` first;
if there was an intervening reboot, select the actual indexed boot.
If journal access is denied/empty, record that deficiency. Preserve
raw logs unchanged, and do not infer zero GPU faults.

If an actual old `amdgpu-devcoredump` was saved to
`/var/log/amdgpu-devcoredumps/`, separately copy the **existing**
file with preserved metadata and hash into a non-overwriting evidence
folder. Do **not** write to
`/sys/class/drm/card*/device/devcoredump/data`, trigger a reset
or assume the sysfs coredump survived reboot. Some coredumps
contain job command buffers, PASID, VMID and process data; treat as
sensitive data, and avoid posting full dumps publicly.

## P1: identify the FIRST failing job and class

Read chronology from the raw previous-boot journal:
- `GPU Hang`, `ring gfx timeout` or `comp_1.0.1 timeout`:
  first exact timestamp, ring name, signaled/emitted fences;
- `pasid`, `vmid`, `process_name`, `thread`, IB address
  and packet data if preserved in original devcoredump;
- first GPU VM/page-not-present status/VA/client, if any;
- `GPU reset begin`, `BACO reset`, `VRAM is lost`;
- `Failed to quiesce KFD`, `Failed to restore process queues`,
  `Failed to resume KFD` and their actual return code/order;
- compositor/KWin timeouts **after** the original compute failure.

Do not conflate `ring gfx timeout` with `GPU VM page fault`.
A hang may never print a VM fault; the first failed operation can
precede its asynchronous HIP error.
Relevant current upstream documentation:
https://www.kernel.org/doc/html/latest/gpu/amdgpu/debugging.html
https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/amdgpu/amdgpu_job.c
https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/amdgpu/amdgpu_dev_coredump.c

## P2: exact running kernel → source and symbols

```bash
KREL=$(uname -r)
MOD=$(modinfo -n amdgpu)
printf 'running=%s\nmodule=%s\n' "$KREL" "$MOD"
readelf -n /sys/kernel/notes 2>/dev/null | head -80 || true
ls -l "/usr/lib/debug/lib/modules/$KREL/vmlinux" \
  "/usr/lib/modules/$KREL/build" 2>&1 || true
# Search exact installed kernel build/source, not today's upstream master:
SRC="/usr/lib/modules/$KREL/build"
grep -RFn --include='*.c' 'Failed to quiesce KFD' "$SRC/drivers/gpu/drm/amd" 2>/dev/null || true
grep -RFn --include='*.c' 'Failed to restore process queues' "$SRC/drivers/gpu/drm/amd" 2>/dev/null || true
grep -RFn --include='*.c' 'hqd_sdma_get_doorbell' "$SRC/drivers/gpu/drm/amd" 2>/dev/null || true
```

The **matching CachyOS kernel source/build** and debug-symbol package
are required for reliable source line attribution. Header-only
`/usr/lib/modules/$KREL/build` may not contain full driver sources.
A newer upstream `amdgpu` line number or just kernel version
does not prove the exact binary/backport. Verify build ID and running
module identity; obtain a matching source/package archive if missing.

Separate three results: callback source present, callback pointer
assigned in gfx7/gfx8 ops, and callback **actually invoked on the
failing queue reset path**. The first two are static audits; the last
requires a trace or dump.

## P3: what GDB / ROCgdb / Ghidra can and cannot do

**Kernel crash analysis**: with matching `vmlinux`, unstripped
module symbols and an actual CPU kernel vmcore (kdump must have existed
at failure), use the Linux `crash` utility (`crash /exact/vmlinux
/retained/vmcore`) to inspect kernel task/queue state and the relevant
reset-path symbols. GDB is best used on an exact unstripped module,
userspace crash core, or a live instrumented kernel debugger with a
proper kgdb target. A GPU device devcoredump is **not** a CPU kernel
vmcore and cannot be opened as one by ordinary GDB or `crash`.
No kernel vmcore means no post-hoc kernel pointer inspection with
a source-level debugger.

**ROCgdb**: source-level debugging for ROCm host/device code where
the installed version supports the architecture. A GPU hang may never
reach a catchable user exception. ROCgdb changes timing and can
prevent runtime GPU core dumping. For any new run, decide beforehand
between **untraced device-coredump capture** and **instrumented
debugger/profiler capture**; avoid simultaneous modes that conflict.

**Ghidra**: import the **exact** installed `amdgpu.ko`, ROCm
`libhsa-runtime64` or TopK GPU code object (HSACO), with associated
build IDs and debug symbols. Use only if corresponding source/debug
symbols are unavailable or binary differs. Focus on the actual
`hqd_sdma_get_doorbell` callback registration/call, reset-state
branches, and compiled TopK/sort code. Disassembly does not prove
that an instruction was executed during the historical crash.

A local `gdb-mcp` or `ghidra-mcp` is not an automatically
available ChatGPT connector. No live debugger was attached in this
repository operation.

## P4: guarded reproduction and discriminating experiments

**Do not** rerun known-wedging float32 `[32,151936]`, k=50
on the sole display GPU as a first action. Prefer a separate
non-display gfx803 machine or fully recoverable test host, with
SSH/serial access and durable external journald/coredump collection.

Test T1 first via a **reviewed rebuilt wheel**, original torch/ROCm
component source+binary hashes, and safe controls:
- compare unpatched selection (`mbtopk`) vs patched full sort
  only on a safe recoverable host, one child per case;
- resolve actual selected kernel dispatch and code object hashes;
- single-request then repeated memory-pressure and tile-/shape-
  constrained tests, with a hardware watchdog;
- compare no-profiler and pinned same-runtime HIP synchronization
  controls, recognizing instrumentation may mask a race;
- collect large-vocabulary timing only on surviving, numerically
  correct paths.

T2 requires a **controlled injected fault/reset test** or genuine
independent captured recovery failure on a non-display test GPU.
Instrument the exact kernel-source-specific reset functions using
kprobe/ftrace/dynamic debug **only after** verifying symbol names,
kernel config, lock/queue sensitivity and hardware recovery path.
Record first failing function/return, pre/post number of queues,
PASID, SDMA doorbell index and whether process queue reset was
attempted at all. Root-level tracepoint setup is not part of this
read-only plan.

**Patch decision tree:**
- T1 fault from full-sort GPU generated code/dispatch: fix/limit
  TopK route, benchmark safe `mbtopk` where it proves correct,
  rebuild reviewed wheel, retain short-route sort fallback.
- T1 due to OOM/VA mapping or queue completion: fix its actual
  allocation/async/runtime lifecycle, not a speculative TopK heuristic.
- T2 callback absent from *running* gfx7/8 build: apply missing
  2025 callback backport and test its specific invocation.
- T2 callback present but queue resume fails: inspect exact
  `quiesce → process queue restore → resume` return path,
  queue mapping/doorbell state and what hardware failed to reset;
  do **not** reapply the historical callback patch by default.
- T2 reset succeeds but graphics desktop dies: investigate
  KWin/Plasma reinitialization separately, after device state is sound.

## R0–R3 deliverables and exit gates

| Phase | Deliverable | Current status | Exit |
| --- | --- | --- | --- |
| R0 incident preservation | Fault-era journal, devcoredump inventory, module/kernel build identifiers, existing CSVs, SHA inventory | Incident note saved; raw dump availability unknown | Immutable, correlated first fault/reset timeline |
| R1 kernel provenance | Running compiled GFX8 callback and queue-validation source attribution | OPEN | Exact build-ID/source maps and callback/registration check |
| R2 T1 causal repro | Reviewed-wheel safe TopK/sort vs selection + kernel dispatch/coredump correlation | OPEN; old wheel harmful | Controlled reproduction with specific responsible dispatch |
| R3 T2 recovery causal repro | KFD reset stages/return and queue/doorbell state | OPEN | First failing KFD reset function established and independently regression-tested |
| Release | Source patch, TopK paired benchmark, queue stability, client build/admission | OPEN | Review acceptance + numerical and stable hardware receipts |

This work must remain in `gfx803_compat_graph`; do **not**
commit local debug scripts or AI investigation documents to
Schaka TopK PR #8. The upstream PR should contain only requested
patch/driver/Dockerfile and real benchmark CSVs or a concise
human-written finding if performance testing is blocked by a
reproducible hang.


## P0a: full raw previous-boot journal reconciled (14 November)

New first-party immutable evidence is now committed:

- `docs/receipts/gfx803_topk_pr8_review_safe_20261114/INCIDENT_20261114_GPU_HANG.md`
- `docs/receipts/gfx803_topk_pr8_review_safe_20261114/unpatched.csv`
- `docs/receipts/gfx803_topk_pr8_review_safe_20261114/patched-pre-review.csv`
- `docs/receipts/gfx803_topk_pr8_review_safe_20261114/kernel-previous-boot.log`,
  original SHA-256
  `be965c117fc7fd2a815a843b63b3ad807d9e88ae43ffff33495cb82043fc70f6`.

**Do not rerun the first postboot preservation step to overwrite this
captured evidence.** Historical incident and raw journal already exist,
and the post-reboot transitory sysfs GPU devcoredump was not retained.

The journal was reviewed directly rather than extrapolating from
the short incident note. Chronology:

| Time | Original kernel observation | Implication |
| --- | --- | --- |
| 12:39:28 | `ring gfx timeout`, submitted process `kwin_wayland` PID 1877; `The cp might be in an unrecoverable state due to an unsuccessful queues preemption` | KWin owns **reported timed-out ring job**, not necessarily original TopK fault |
| 12:39:28 | `Failed to quiesce KFD`, `Failed to restore process queues`, `Failed to resume KFD` | Queue quiesce/restore path directly failed |
| 12:39:29 | KIQ ring test `-110` (timeout), `KCQ disable failed` | KIQ/KCQ failures make queue management progress a decisive target |
| 12:39:29 | `Successful gfx_v8_0 IP block soft reset` followed by `device wedged, but no recovery needed` | Success of individual hardware reset operation **does not equal functional GPU recovery** |
| 12:39:29–30 | BACO reset; `GPU reset succeeded, trying to resume`; VRAM loss; `GPU reset(2) succeeded!`; **device still wedged** | Recovery state remained unusable despite low-level reset completion |
| 12:39:32 | KWin VM fault, `VM_CONTEXT1_PROTECTION_FAULT_ADDR 0x0C000200`, `STATUS 0x0E0C4001`, VMID 7/PASID 7, TC3 read | Graphics-context VM mapping invalid after the first reset wave |
| 12:39:55 | Plasma shell VM fault, address `0x00000027`, status `0x0E0C4008`, VMID 7/PASID 15, TC3 read | Separate graphics process/address; do **not** conflate either fault with the TopK process's GPU VA |
| 12:39–12:43:59 | Repeated `ring gfx timeout`, `ring comp` timeouts and device coredump announcements plus intermittent `Successful gfx_v8_0 IP block soft reset` | Persistent GPU/queue failure; Wayland session restart alone cannot repair |

**Correction to earlier root-cause phrasing:** the record proves
a *non-durable reset / KFD queue recovery failure* that persists even
after GFX8 soft reset and BACO stages reported success. It does not
prove a failed reset at every hardware block, nor that the old missing
doorbell callback recurred, nor that KWin rather than the TopK
compute workload initiated the first fault.

Updated maximum cut: recover exact kernel 7.3.0-2-cachyos-bore
GFX8 reset source, inspect the KIQ ring test `-110` and KCQ
disable handling before / during KFD queue-manager resume, and
establish whether the queue restoration failed because hardware
rings were already unresponsive, firmware/queue state mismatched,
or KFD-specific doorbell/queue-memory restoration was invalid.
Only a matched source line/trace or retained low-level dump can
discriminate those mechanisms.

**Release blocker:** a GPU wedged strongly enough that SDDM was
running but relaunching Plasma Wayland could not recover requires
a full host reboot in the recorded incident. No short HIP smoke pass,
GPU reset-return success code or `kwin_wayland` process restart
closes this gate.


## Current parallel K1/K2 + T1 plan

The active source/recovery plan and exact machine-readable operator
handoff are maintained in
[TopK/KFD parallel workboard](GFX803_TOPK_KFD_PARALLEL_WORKBOARD_20261114.md).

The operator is acquiring the **incident-boot** CachyOS source and
symbols, verifying compiled gfx7/8 callback/queue handling and mapping
the first KIQ/KCQ/KFD error. In parallel, source analysis of the old
TopK full-sort dispatch can proceed without re-triggering the
known display-wedging GPU case.

Do not mark K1, K2, T1 or J1 completed until source/build proof and
actual first-error/dispatch attribution have been ingested.
The immutable previous-boot journal is already preserved; avoid
creating duplicate raw captures or overwriting original evidence.


## K1/K2 source receipt now available (14 November)

The operator committed `07a52c7`, now tracked by
[the kernel handoff JSON](receipts/gfx803_kfd_kernel_source_handoff_20261114.json).
The installed AMDGPU module has recorded SHA-256 and Build ID;
Polaris selects `gfx_v8_kfd2kgd`; the gfx8 SDMA doorbell callback
is present in the module and registered in v7.3 **reference source**.
Neither actual callback invocation nor an exact CachyOS source-package
match is established. The installed kernel/module have no available
DWARF debug symbols; GDB-MCP is usable on the operator host only.

The first **logged** KFD recovery failure is `Failed to quiesce KFD`,
followed by process queue restore/resume errors, KIQ timeout `-110`
and KCQ disable failure. This advances K2 but does not prove the first
failing **internal** function, which is the next source-level maximum
cut. The corrected receipt marks callback invocation `null` (unknown)
rather than `false`.

See [the updated parallel workboard](GFX803_TOPK_KFD_PARALLEL_WORKBOARD_20261114.md)
for status and exact K2.03 next deliverables. No physical rerun.


## K2.03 source map received (commit `43e70ef`)

The source-owned handoff maps the first logged KFD quiescence
failure from `amdgpu_amdkfd_gpuvm.c:2535` through
`kgd2kfd_quiesce_mm` → `kfd_process_evict_queues` →
`dqm->ops.evict_process_queues`, then a nonzero return (other
than `-EIO` in the mapped reporting branch) to `Failed to quiesce KFD`.

This is a **static reference-source call path**, not a captured
incident-time internal return or proof of an exact CachyOS source
package match. Later KIQ `-110` and KCQ disable occur after the
first reported quiescence failure in the retained journal. Their
common deeper hardware cause remains possible, not demonstrated.

**Next:** K2.04 selected DQM eviction implementation and reachable
error propagation matrix; K2.05 actual incident-time return if
recoverable from evidence. The complete gate table is in the
[parallel workboard](GFX803_TOPK_KFD_PARALLEL_WORKBOARD_20261114.md).


## K2.04 MES eviction path mapped (commit `635b40c`)

For the recorded live Polaris KFD configuration
`gfx_target_version=80003`, `sched_policy=0`, `uni_mes=1`,
upstream reference-source selection reaches
`evict_process_queues_cpsch` → `remove_queue_mes` →
`adev->mes.funcs->remove_hw_queue`. Source-level failure
escalation can reach `reset_queues_mes` and `kfd_hws_hang`
when recovery is enabled.

This is only a **conditional** MES path: post-reboot `uni_mes=1` selects it
in the v7.3 reference source, but the retained incident's unsuccessful
queue-preemption diagnostic is emitted there only by the non-MES
`unmap_queues_cpsch` fence-timeout path. K2.05 must first resolve that
MES/non-MES contradiction. The journal does not demonstrate
`remove_hw_queue` invocation or its return. Neither a GFX8 doorbell regression
nor the later KIQ `-110` is established as the initial failure. See the
[parallel workboard](GFX803_TOPK_KFD_PARALLEL_WORKBOARD_20261114.md)
for K2.05a–c acceptance criteria.

## K2.06 correction — Polaris is non-MES in the reference path

The preceding MES hypothesis is superseded for the v7.3 Polaris reference.
`uni_mes` is not the KFD `enable_mes` flag: the latter is set only by the
GC11/GC12 MES IP-block cases and is copied to KFD shared resources. A GFX8
device therefore takes the non-MES unmap/fence path, which is consistent with
the retained preemption diagnostic. The precise incident errno remains open
without an exact CachyOS source match or trace. See
`docs/receipts/gfx803_k205_t104_source_binary_attribution_20261114.json`.

No GPU rerun, matched CachyOS source package, new DWARF symbols,
or kernel patch is claimed.

## 14 November — offline fatbin result

The fail-closed audit verified the retained candidate HIP ELF identity and
extracted its 42,919,798-byte `.hip_fatbin` section.  A bounded scan found no
direct embedded AMDGPU ELF64 payload.  This only rules out that narrow storage
representation; it cannot identify or exclude a wrapped/compressed HSACO, and
it cannot establish what dispatched in the incident.  The corrected results
are in the host-local `gfx803_t105_k206_20261114_r2` directory cited by the
parallel workboard.  No GPU execution occurred.


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
