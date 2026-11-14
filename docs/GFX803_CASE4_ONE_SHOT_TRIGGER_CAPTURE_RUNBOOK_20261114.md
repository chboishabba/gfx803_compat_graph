# Operator runbook — one-shot original TopK case 4, *known to wedge display RX580*

**14 Nov 2026; single PR #7; manual next-day handoff.** **All files below are staged, not run against GPU.** The original incident's 14 Nov Python core is retained in [`gfx803_topk_incident_core_provenance_20261114.json`](receipts/gfx803_topk_incident_core_provenance_20261114.json). The original crash involved exactly case 4, f32 `[32,151936]`, `k=50`, 10 warmups and 50 timed iterations, a Nix `torch-site` overlay, staged ROCm 10.1, SGEMM `LD_PRELOAD` and `libtorch_hip.so` SHA-256 `c1ad552aac76766b14ad78b993b5e3ee7a3b72c7fc48b7d72345516cf6fba7ff`.

**Physical warning:** this shape already caused corruption, KFD/KIQ failure, a persistent Wayland GPU wedge and a forced reboot. This harness does not make it safe. **Save work and consider not running on your only display GPU.** No software reset / `systemctl restart sddm` / re-run / second stress test is an acceptance gate; it can further poison the GPU. This is **one** consciously operator-armed attempt, never automatic, and no crash-proof profiler guarantee.

## What was actually implemented

| Component | What it collects / does not |
| --- | --- |
| [`scripts/gfx803_one_shot_repro_capture.py`](../scripts/gfx803_one_shot_repro_capture.py) | Host-only preflight, **dry-run default**, exact runtime SHA, fsynced kernel journal + process output + periodic heartbeat; terminal acknowledgement; bounded child lifetime; no reset/reboot/retry |
| [`scripts/gfx803_one_shot_case4.py`](../scripts/gfx803_one_shot_case4.py) | Checks original Nix overlay, ROCm root, exact `libtorch_hip.so` SHA, import location, actual `LD_PRELOAD` library paths/hashes, pre-dispatch library maps; invokes **the existing benchmark's exact `_one(4,10,50)`** only after manual authorization; writes fsynced before/after dispatch markers |
| [`scripts/gfx803_case4_kfd_returns.bt`](../scripts/gfx803_case4_kfd_returns.bt) | **Inert until manually run** bpftrace probes on `unmap_queues_cpsch`, `amdkfd_fence_wait_timeout`, `kgd2kfd_quiesce_mm` entry/return, with signed return code and timestamps. **Not a GPU ISA or PASID/VMID trace** |
| [`scripts/gfx803_durable_stream.py`](../scripts/gfx803_durable_stream.py) | fsyncs each manually captured probe line to a new file; refuses overwrite |
| [`tests/test_gfx803_one_shot_capture.py`](../tests/test_gfx803_one_shot_capture.py) | 10 CPU-only cases for exact case identity, SHA gates, no-GPU command construction, no overwrite and durable log plumbing; does **not** invoke child main or import torch |

### Hard evidence boundary

A successful `rocprofv3 --kernel-trace` file with original code object, symbol, grid and timing can help identify the dispatched kernel. A KFD return trace can identify `-EIO` vs `-ETIME` at *the time it happens*. **Neither is guaranteed**: the runtime async hardware-exception abort can prevent ROCprof buffer flush, and probes can alter timing or be unavailable. Simply reproducing a hang and another GFX timeout is **not** enough to close T1.07 or K2.05.

The baseline arm without kernel probes is intentionally rejected. The **instrumented** `rocprof` arm can proceed without KFD probes if probe symbols are unavailable, but then K2.05 remains open. No process tracing or profiler is switched on automatically by dry run.

## T0 — Morning, read-only sanity and rehearsal (NO GPU dispatch)

Use the same operator's environment that produced the incident (the pinned Schaka/Nix shell or launcher), with the **SGEMM shim** already exported in `LD_PRELOAD`. Do not guess the shim path or mix in system ROCm. The incident original launcher SHA-256 is `9e378dbe94483f32ec66b9d02e0169d2542ab81df2063b01e0ac39fbb731a25c`, but its executable command line/environment setup beyond the recovered core receipt needs the operator's previously saved launch script. Preflight verifies the GPU library hash and records shim hashes; it cannot prove every Nix runtime component matches its historical build.

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
git switch fix/gfx803-c1b-kfd-recovery-model
git pull --ff-only

# No GPU work:
python3 -m unittest discover -s tests -p 'test_gfx803_one_shot_capture.py' -v
python3 -m unittest discover -s tests -p 'test_gfx803_incident_join.py' -v
python3 -m unittest discover -s tests -p 'test_gfx803_kfd_event_correlation.py' -v

# Use the exact Python from the incident Nix runtime environment, not an
# unrelated /usr/bin/python3. Resolve its actual executable.
PY=$(readlink -f "$(command -v python3)")
echo "Python=$PY"
echo "Kernel=$(uname -r)"
printf 'LD_PRELOAD=%s\n' "$LD_PRELOAD"

# A NEW local persistent directory is preferable; avoid NFS logging stalls
# while the kernel is already handling GPU failure.
OUT="/var/tmp/gfx803-case4-one-shot-$(date +%Y%m%d-%H%M%S)"

# NO --arm: checks original overlay, library and journal readability;
# prints the exact future child command but does not import torch/launch HIP.
python3 scripts/gfx803_one_shot_repro_capture.py \
  --python "$PY" --out "$OUT" --mode rocprof \
  --rocprof "$(command -v rocprofv3)" \
  --expect-kernel "$(uname -r)"
```

**Do not continue** if the exact Nix overlay/lib is absent, the preload differs unexpectedly, the journal is inaccessible, your system contains irreplaceable unsaved work, or the device cannot be recovered after a wedge. The historical v7.3 kernel may differ from tomorrow's running kernel; `--expect-kernel` pins *what you explicitly enter*, not automatically the incident's version.

## T1 — Pre-arm optional KFD returns (requires actual kernel privileges)

A useful original KFD return must be captured **as the kernel executes**, prior to the first reset. This is active kernel tracing and changes timing. It does not become safe simply because the probe source is small. On another TTY/session, first verify the actual installed kernel symbols; if any required symbol is absent or module lockdown denies probes, skip this arm rather than apply patches or bypass security restrictions.

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
sudo bpftrace -l 'kprobe:unmap_queues_cpsch'
sudo bpftrace -l 'kretprobe:amdkfd_fence_wait_timeout'
sudo bpftrace -l 'kretprobe:kgd2kfd_quiesce_mm'

# Separate, unique local persistent file (no preexisting file).
KFD_LOG="/var/tmp/gfx803-kfd-return-$(date +%Y%m%d-%H%M%S).jsonl"
set -o pipefail
sudo bpftrace -q scripts/gfx803_case4_kfd_returns.bt \
  | python3 -u scripts/gfx803_durable_stream.py --out "$KFD_LOG"
```

Leave this terminal collecting before proceeding. It must print a `kfd_probe_start` JSON line and remain running. The run captures **function return values**, not raw runtime SVM-range IDs/BOs. To prove the B1 two-invalidator race, a further lock-safe per-range/PASID structured capture is still required; the KFD program alone cannot adjudicate it.

## T2 — ONE manually armed reproduction

Prefer the **instrumented ROCprof arm** for original executed kernel/dispatch identity; the profiler can prevent/delay the crash, so compare with previous uninstrumented evidence instead of assuming equivalence. Use your same incident-time pinned Nix runtime and shim environment. The launcher does not start kernel probes; `--kfd-log` validates that an already running probe has a fresh `kfd_probe_start` record.

```bash
# From the exact preflight shell, using the same PY and OUT set above:
python3 scripts/gfx803_one_shot_repro_capture.py \
  --python "$PY" --out "$OUT" \
  --mode rocprof --rocprof "$(command -v rocprofv3)" \
  --kfd-log "$KFD_LOG" --expect-kernel "$(uname -r)" \
  --timeout 180 --tail-seconds 20 --arm
```

A local interactive TTY must type:

```text
I ACCEPT THE RX580 MAY WEDGE AND REQUIRE REBOOT
```

If you intentionally choose **unprofiled baseline**, swap to `--mode baseline`, but **`--kfd-log` is mandatory**, because another journal-only crash is low-information for first-return attribution. Do **not** launch both arms in sequence. Do not automatically run a post-fault GPU health check. Ctrl-C / process failure is not guaranteed to restore an unresponsive GPU.

### What survives to `$OUT`

- `preflight.json`: original exact library digest, running kernel and interpreter SHA, mode and safely redacted relevant environment
- `child-events.jsonl`: fsynced host-side before-dispatch marker, actual preload paths/hashes, torch version and original binary SHA; end marker only if it survives
- `child-output.log`: `GPU Hang`, Python/ROCr output including abort if emitted
- `kernel-follow.log`: fsynced complete kernel reset/error lines as the host receives them, including **after** process abort for `--tail-seconds`
- `host-heartbeat.jsonl`: fsynced host progress stamps; **not GPU-fence progress**
- `supervisor-result.json`: only if supervisor survives to write it
- `rocprof/`: optional profiler output. **Empty/missing output after SIGABRT is an expected failure mode, not proof no kernel launched**
- separate `$KFD_LOG` from kernel return probes if enabled; this is the most direct first-return capture.

The manual bpftrace capture remains running until you stop it in its own terminal. The launcher never unloads or resets amdgpu, never kills SDDM/Wayland, never executes a recovery healthcheck and never replays case 4.

## T3 — After reboot: preserve original artifacts without re-execution

If the GPU wedges, recover the host in the ordinary operator-controlled manner. **Do not force a GPU/PCI reset via sysfs.** After reboot, before another GPU workload:

```bash
# In the same shell where OUT and KFD_LOG were recorded:
find "$OUT" -maxdepth 3 -type f -printf '%p %s bytes\n'
sha256sum "$OUT"/* 2>/dev/null || true
journalctl -k -b -1 --no-pager > "$OUT"/previous-boot-kernel-after-reboot.log
coredumpctl list --no-pager | tail -40
# Store full core only if explicitly needed; it can be huge/private.
# Do not commit any raw core, memory maps containing private paths, or
# private process environment to a public PR.
```

The contents may contain host identifiers, paths, PIDs, application details and memory artifacts. Review/redact before uploading; commit **hashes, redacted JSON/summaries and minimal relevant log extracts** to PR #7, not confidential cores.

### Exact acceptance / interpretation

| Result | What it establishes | Does not establish |
| --- | --- | --- |
| `preflight` and child start receipt, no profiler output | Exact original userspace binary and start boundary | Executed GPU kernel |
| ROCprof kernel launch record with symbol, grid, queue, timestamp and a matching child/capture | Observed launch, potentially T1.07 selected HSACO | That this kernel was *first to stall*, without completion/fence evidence |
| KFD `unmap` / `fence_wait` return at first 12:39-ish failure | B3/K2.05 **actual** return and duration in new run | Retroactive first-return of November 14 incident |
| Two SVM notifier ranges, same mm/PASID, second return before quiesce ends | B1 ordering active in new run | Causality of GPU corruption or stall automatically |
| One-shot returns 0, CPU+GPU result correct | This instrumented run survived | Stable/robust GPU under sustained workload or original unprofiled result |
| GPU wedges with incomplete capture | A reproduced failure, but insufficient causal attribution | Permission to patch speculative KFD mechanisms |

**Important:** the new reproduction occurs on a *different date* and perhaps different host kernel/driver, so it is a new failure receipt. Preserve the historical 14 Nov artifact hashes, never mutate them. The synthetic/inert SVM RFC remains review-only until hardware and code-path activation evidence warrant promotion.

## T4 — No automatic follow-up or retry

Only the operator chooses any subsequent test, after evidence is preserved and independently recoverable hardware is available. The accepted result is an incident-matched dispatch/queue/return graph, followed later by a justified kernel/runtime correction and demonstrated usable graphics+compute after reset without reboot. Repeating case 4 without improving capture quality is not an acceptable next maximum cut.
