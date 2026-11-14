# RX580 known-wedge TopK case 4 — manually armed one-shot capture

**Date:** 14 Nov 2026. **Status:** launcher + post-reboot collector + optional KFD probes + CPU-only tests committed in existing PR #7. **No physical repro performed by this author.**

## Risk and objective

**THIS CAN PERMANENTLY WEDGE YOUR SOLE DISPLAY GPU UNTIL YOU MANUALLY REBOOT.** May kill the Wayland session/browser, lose unsaved work, interrupt active storage writes or leave the GPU inaccessible. One deliberate manual attempt only; no automatic retry, GPU reset, runtime healthcheck or reboot. Back up unsaved work, ensure a functional TTY/SSH console and any necessary non-GPU control path, and use a persistent disk with capacity. A **second, independently recoverable non-display GPU remains the preferred controlled test host**. Do not mislabel the current display card as a safe-host device.

The goal is to preserve **before-the-hang** evidence:
- exact **original** PyTorch/ROCm binary identity (not the older statically audited ELF);
- original case 4 input `float32 [32,151936], k=50`, ten warmups, 50 timed iterations; original benchmark's exact `_one(4,10,50)` function reused without scheduling other cases;
- early graphics/ring and KFD recovery journal messages with process + first fence;
- observed loaded libraries and preloaded SGEMM shim;
- **optional** exact internal KFD preemption return from kernel function probes;
- **optional** ROCprofv3 kernel trace for real GPU kernel, dispatch/queue/workgroup metadata if flushed.

**Never interpret absence of kernel-name data after abort as proof no kernel launched.** The ROCprof trace may buffer results until normal application exit and may fail to flush upon GPU fault. Probes and ROCprof both alter timing and may mask the event. The Python core from Nov 14 has already proved the original Nix overlay and abort handler; this run must not use `dd0b...` as the binary identity. Immutable [incident Python core provenance](receipts/gfx803_topk_incident_core_provenance_20261114.json):

| Field | Original incident |
| --- | --- |
| Case | `4`, f32 `[32,151936]`, k50 |
| Original launcher | 10 warmups, 50 timed |
| `libtorch_hip.so` SHA256 | `c1ad552aac76766b14ad78b993b5e3ee7a3b72c7fc48b7d72345516cf6fba7ff` |
| GNU Build ID | `3d27b29d191725660bbc4b8a83cb2f4753a09921` |
| Immutable torch overlay | `/nix/store/vq1lgpc49im7qvvxgxabykyfs47l2ykb-gfx803-schaka101-torch-candidate-overlay/torch-site` |
| Pinned ROCm | `/nix/store/5dbvxcs7l4mvnj1cq3ybbkdm15jpvqr9-staged-rocm` |
| SGEMM shim | Present in incident core; **exact original file path/hash not captured in committed core receipt** — operator must identify actual file before running |
| Host abort | ROCr `Runtime::HwExceptionHandler` `SIGABRT`, not the stalled GPU kernel |

## 0. Before morning: install/check in a safe terminal (NO GPU COMMANDS)

Checkout the **same PR #7**, not an older worktree. These commands only inspect source and execute CPU-side tests:

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
git fetch origin
git switch fix/gfx803-c1b-kfd-recovery-model
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_gfx803_topk_one_shot_capture.py' -v
python3 -m unittest discover -s tests -p 'test_gfx803_topk_postreboot_collect.py' -v
```

Set these from **your actual confirmed current environment**, never invent a shim location:

```bash
PYTHON_BIN="$(command -v python3)"
# Replace with the original SGEMM shim .so path in the Nix/host runtime.
SGEMM_SHIM="/REPLACE/WITH/ACTUAL/SGEMM-SHIM.so"
# A new directory under an existing persistent filesystem; NEVER /tmp or /run.
CAPTURE_PARENT="/mnt/truenas/comet-net/experiments"
OUT="$CAPTURE_PARENT/gfx803_topk_one_shot_$(date +%Y%m%d_%H%M%S)"
test -d "$CAPTURE_PARENT"
test -x "$PYTHON_BIN"
test -f "$SGEMM_SHIM"
```

**Do not execute until the original ROCm 10.1 Python is actually selected.** If `command -v python3` points to a system/other Python, select the actual candidate interpreter. A matching `libtorch_hip.so` on disk is necessary but not sufficient to prove Python resolves that torch package: the eventual loaded-library map is the verification. There is no attempt to recreate a host environment from guesses.

Default preflight has **NO torch import, HIP init or GPU dispatch**:

```bash
python3 scripts/gfx803_topk_one_shot_capture.py \
  --python "$PYTHON_BIN" --shim "$SGEMM_SHIM" --out "$OUT"
```

It verifies the recovered core's pinned store roots, **full SHA-256 and ELF Build ID** of `libtorch_hip.so`, the SGEMM shim exists, exact benchmark source is present, output is new/persistent, and `journalctl` exists. If *anything* fails, **do not run**. A terminal message `PREFLIGHT-ONLY-NO-GPU` is not an execution receipt.

### Optional probe availability preflight (also NO GPU commands)

For exact non-MES KFD `amdkfd_fence_wait_timeout`, `unmap_queues_cpsch` and `kgd2kfd_quiesce_mm` returns:

```bash
python3 scripts/gfx803_topk_one_shot_capture.py \
  --python "$PYTHON_BIN" --shim "$SGEMM_SHIM" --out "$OUT" --enable-kfd-probes
```

The preflight requires `bpftrace`, a readable running-kernel `available_filter_functions`, and all **three required symbols**. If absent, the launcher **refuses to attach**; do not bypass by fabricating symbol names. Kprobes are optional and instrumentation-changing; they may alter race timing. Kernel symbol listing is read-only, but actual attachment is not.

### Optional dispatch profiler preflight (NO GPU commands)

Kernel dispatch trace CLI is documented by [AMD ROCprofv3](https://rocm.docs.amd.com/projects/rocprofiler-sdk/en/latest/how-to/using-rocprofv3.html). The launcher requires an explicit `rocprofv3` executable under the **same pinned original ROCm root**, not a PATH fallback:

```bash
ROCM_ROOT="/nix/store/5dbvxcs7l4mvnj1cq3ybbkdm15jpvqr9-staged-rocm"
test -x "$ROCM_ROOT/bin/rocprofv3"  # Only if this path genuinely exists
# Add --rocprofv3 "$ROCM_ROOT/bin/rocprofv3" to the preflight.
```

ROCprof captures kernel name, queue, dispatch and grid **if it flushes the record**. On a hard GPU hang the profiler can itself abort before writing results; a profiler-assisted non-hang is still useful as a **separate instrumented control**, not original causal evidence.

## 1. One deliberate, operator-armed case 4 (ONLY WHEN READY)

**This is the dangerous command.** Do not copy it into a scheduled job. Close unsaved documents, stop unrelated compute workloads, verify the output parent is durable, and expect a manual reboot.

For the strongest first fence-return evidence, after KFD probe preflight passes, explicitly arm:

```bash
python3 scripts/gfx803_topk_one_shot_capture.py \
  --python "$PYTHON_BIN" \
  --shim "$SGEMM_SHIM" \
  --out "$OUT" \
  --max-seconds 300 \
  --enable-kfd-probes \
  --execute \
  --accept-single-display-risk \
  --ack 'I ACCEPT THE GPU WEDGE AND MANUAL REBOOT'
```

If the **optional KFD probe preflight fails** and you decide to proceed without it, remove `--enable-kfd-probes`, but know the kernel journal will likely still **not print the first internal KFD return**. For dispatch identity, optionally add `--rocprofv3 "$ROCM_ROOT/bin/rocprofv3"` **only if that exact binary is installed and its own preflight passes**. Combining ROCprof with KFD probes offers more observability at the cost of more timing perturbation; no single configuration can guarantee both the original hang and a fully flushed GPU kernel trace.

The launcher first creates `manifest.json` and starts `journalctl -k -f` with per-line fsync. If requested and available, it attaches bpftrace **before** launching the HIP child. It launches exactly one `_one(4,10,50)` in a new Python process, captures stdout, stderr, and live Python/ROCprof child process `/proc/*/maps` matches, then records exit/timeout. It **does not** dispatch a post-fault health check, issue a GPU reset or initiate a reboot. Note that subprocess invocation differs from the original `--case 4` argv but calls the same benchmark `_one` function, and that distinction is recorded.

**Safety on a wedged desktop:** if nothing responds, do not repeatedly launch another TopK attempt or forcibly retry KFD resets. Use your established recovery procedure once you have preserved whatever logs you can. The terminal/SSH may remain alive while the GPU is not.

## 2. After reboot: collect from the original boot ID (NO GPU COMMANDS)

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
# OUT must still refer to the exact first-run directory.
python3 scripts/gfx803_topk_postreboot_collect.py \
  --run "$OUT" --out "${OUT}-postreboot"
```

This uses the **saved original boot ID**, not `journalctl -b -1` (which can silently shift after another reboot). Collects original boot kernel journal, filtered system journal, coredump list and SHA-256s of original capture artifacts into a new directory. It does not export the full Python core by default—large data should stay host-local unless needed—and it records missing journal access or unavailable coredumps as errors, not as negative GPU evidence.

### Report back after the run

Provide **small** files first: `manifest.json`, `result.json`, `kernel-journal.log`, `kfd-return-probe.log` if present, `loaded-maps.log`, and the post-reboot `receipt.json`. Also the ROCprof `*.db` metadata / file listing and (if available) extracted kernel trace CSV with queue IDs. The kernel/probe logs can contain process names, addresses and paths; inspect them before publicly sharing.

Only upgrade gates with actual evidence:
- **T1.07** actual kernel/queue dispatch if profiler emitted one or another trace captured it;
- **K2.05** first KFD `retval` if bpftrace output retained a linked return with monotonic timestamp;
- **B1** actual SVM double-notifier race remains **not captured** by these three return probes alone; requires separate validated same-PASID/range/MMU notifier instrumentation.
- **R1/R5** post-BACO reset usability remains OPEN unless independently tested **without** reboot.

Do **not** install the SVM or reset RFC patch as part of this reproduction; doing so would change the trigger condition and confound attribution. Keep this as a baseline capture of the original suspected failure.

## 3. What is not promised

- A Python core records user process state, not GPU wavefront state.
- `rocprofv3` may suppress failure, or lose its trace after abort; *missing* kernel trace does not establish no kernel launched.
- KFD kretprobes measure **CPU kernel function returns**, not first stalled GPU instruction. If the GPU hangs before a function returns, no return event may exist.
- A first gfx timeout after visible corruption is not proof KWin caused the underlying fault.
- Persistent filesystem and per-line fsync reduce data loss but cannot protect against storage/power failure.
- Reproducing on the display GPU still carries the original data-loss/no-recovery risks. A non-display, independently recoverable host is the preferred target.

**Physical verification remains operator-gated. No GPU trigger has been executed by this PR.**
