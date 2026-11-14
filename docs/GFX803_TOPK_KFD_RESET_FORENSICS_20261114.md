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
