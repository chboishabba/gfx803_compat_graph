#!/usr/bin/env python3
"""Operator-armed ONE-SHOT RX580 crash capture; dry-run by default.

Runs ONLY with --arm and a typed local TTY acknowledgement. If armed, this
can wedge the GPU, kill Wayland, lose unsaved work, and require power-cycle.
No retries, no automatic reboot or GPU recovery. No GPU import in parent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import threading
import time

from gfx803_one_shot_case4 import (
    EXPECTED_LIBTORCH_SHA256, EXPECTED_OVERLAY, EXPECTED_ROCM_ROOT,
    preflight_overlay,
)

CONFIRM = "I ACCEPT THE RX580 MAY WEDGE AND REQUIRE REBOOT"
REPO = Path(__file__).resolve().parents[1]
CHILD = Path(__file__).with_name("gfx803_one_shot_case4.py")
BENCH = REPO / "scripts/gfx803_topk_pr8_benchmark.py"


def flush_json(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def command(mode: str, python: Path, folder: Path, *, rocprof: str = "rocprofv3") -> list[str]:
    child = [str(python), "-u", str(CHILD),
             "--benchmark", str(BENCH), "--overlay", EXPECTED_OVERLAY,
             "--rocm-root", EXPECTED_ROCM_ROOT,
             "--receipt", str(folder / "child-events.jsonl"),
             "--warmup", "10", "--iterations", "50",
             "--arm-token", "MANUAL_ONE_SHOT_CASE4_ACKNOWLEDGED"]
    if mode == "baseline":
        return child
    if mode == "rocprof":
        return [rocprof, "--hip-trace", "--hsa-trace", "--kernel-trace",
                "--memory-copy-trace", "--memory-allocation-trace",
                "--output-directory", str(folder / "rocprof"),
                "--output-format", "csv", "--", *child]
    raise ValueError("mode not supported")


def redact_environment() -> dict:
    def entries(key):
        return [Path(x).name for x in os.environ.get(key, "").split(":") if x]
    return {"pythonpath_entries_basename": entries("PYTHONPATH"),
            "ld_preload_entries_basename": entries("LD_PRELOAD"),
            "ld_library_path_entry_count": len(entries("LD_LIBRARY_PATH")),
            "rocm_path_present": "ROCM_PATH" in os.environ,
            "hsa_xnack": os.environ.get("HSA_XNACK"),
            "hip_launch_blocking": os.environ.get("HIP_LAUNCH_BLOCKING"),
            "amd_serialize_kernel": os.environ.get("AMD_SERIALIZE_KERNEL")}


def probe_environment(python: Path, *, expect_kernel: str | None,
                      require_journal: bool, mode: str, rocprof: str) -> dict:
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError("explicit --python must be executable (no PATH fallback)")
    if not BENCH.is_file() or not CHILD.is_file():
        raise ValueError("original benchmark or fixed child missing")
    original = preflight_overlay(Path(EXPECTED_OVERLAY), Path(EXPECTED_ROCM_ROOT))
    if original["libtorch_hip_sha256"] != EXPECTED_LIBTORCH_SHA256:
        raise ValueError("original incident binary not present")
    if not os.environ.get("LD_PRELOAD"):
        raise ValueError("missing LD_PRELOAD; original incident had SGEMM shim")
    release = os.uname().release
    if expect_kernel and release != expect_kernel:
        raise ValueError(f"running kernel mismatch: {release}, expected {expect_kernel}")
    if not shutil.which("journalctl"):
        raise ValueError("journalctl unavailable")
    result = subprocess.run(["journalctl", "-k", "-n", "1", "--no-pager"],
                            text=True, capture_output=True, timeout=10)
    if require_journal and (result.returncode != 0 or not result.stdout.strip() or
                            "No journal files were opened" in result.stdout):
        raise ValueError("kernel journal not readable; refusing blind reproduction")
    profiler_identity = None
    if mode == "rocprof":
        located = shutil.which(rocprof)
        if not located:
            raise ValueError("rocprofv3 missing; do not substitute system ROCm")
        resolved = Path(located).resolve()
        if not resolved.is_file():
            raise ValueError("rocprofv3 not a readable executable")
        # --help is CPU-only. Fail before arming if the installed profiler
        # cannot represent the requested dispatch/HSA/memory capture.
        help_result = subprocess.run([str(resolved), "--help"],
                                     capture_output=True, text=True, timeout=15)
        help_text = help_result.stdout + help_result.stderr
        required_options = ("--kernel-trace", "--hip-trace", "--hsa-trace",
                            "--memory-copy-trace", "--memory-allocation-trace")
        missing_options = [opt for opt in required_options if opt not in help_text]
        if help_result.returncode != 0 or missing_options:
            raise ValueError(f"rocprofv3 unsupported CLI options: {missing_options}")
        profiler_identity = {"path": str(resolved), "sha256": sha256(resolved),
                             "required_capture_flags_verified": True}
    return {"kernel_release": release, "original_overlay": original,
            "rocprofiler": profiler_identity,
            "python_executable": str(python), "python_sha256": sha256(python),
            "benchmark_sha256": sha256(BENCH),
            "child_sha256": sha256(CHILD), "journal_readable": bool(result.stdout.strip()),
            "mode": mode, "environment_redacted": redact_environment(),
            "capture_caveat": "ROCprof can alter timing and lose tail on abort; journal alone cannot identify GPU HSACO"}


def _copy_lines(stream, out, prefix):
    with out.open("x", encoding="utf-8", buffering=1) as target:
        for line in stream:
            target.write(line)
            target.flush()
            os.fsync(target.fileno())
            if prefix == "child":
                sys.stdout.write(line)
                sys.stdout.flush()


def _journal_start(path: Path) -> tuple[subprocess.Popen, threading.Thread]:
    # Pipe the kernel follower through fsync per line so a subsequent forced
    # reboot does not lose all the last evidence to page cache buffering.
    proc = subprocess.Popen(["journalctl", "-k", "-f", "--no-pager",
                             "--output=short-iso-precise", "--since", "now"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, start_new_session=True)
    assert proc.stdout is not None
    writer = threading.Thread(target=_copy_lines,
                              args=(proc.stdout, path, "journal"), daemon=True)
    writer.start()
    return proc, writer


def _stop(proc):
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def run(args) -> int:
    # No child, GPU runtime, journal follower or output directory before
    # original binary, interpreter and kernel preflight passes.
    original = probe_environment(args.python, expect_kernel=args.expect_kernel,
                                  require_journal=True, mode=args.mode,
                                  rocprof=args.rocprof)
    planned = command(args.mode, args.python, args.out, rocprof=args.rocprof)
    if not args.arm:
        print(json.dumps({"status": "DRY_RUN_ONLY", "original": original,
                          "command": planned, "would_wedge_display_gpu": True,
                          "capture_dir": str(args.out), "gpu_commands": 0}, indent=2))
        return 0
    if args.out.exists():
        raise ValueError(f"capture folder already exists: {args.out}")
    if args.mode == "baseline" and not args.kfd_log:
        raise ValueError("baseline arm requires an already active --kfd-log; otherwise this run cannot identify the first KFD return")
    if args.kfd_log:
        if not args.kfd_log.is_file():
            raise ValueError("KFD trace log not found; enable probes in a separate terminal first")
        if time.time() - args.kfd_log.stat().st_mtime > 600:
            raise ValueError("KFD trace log is stale (>10 minutes)")
        with args.kfd_log.open("r", encoding="utf-8", errors="replace") as probe_fd:
            if '"kfd_probe_start"' not in probe_fd.read(6000):
                raise ValueError("KFD trace startup receipt missing")
    if not sys.stdin.isatty():
        raise ValueError("interactive TTY required: never arm from CI, cron or remote pipe")
    print("\nWARNING: exact original TopK case 4 previously wedged the display RX580.")
    print("Save all work; expect permanent Wayland failure until reboot.")
    print("This runs ONCE, and will NEVER auto-retry, reset or reboot.")
    print("Tracing modes modify the timing and can mask the fault.")
    phrase = input(f"Type exactly [{CONFIRM}] to proceed: ")
    if phrase != CONFIRM:
        print("Disarmed; no GPU commands.")
        return 3
    args.out.mkdir(parents=True, exist_ok=False)
    flush_json(args.out / "preflight.json", {
        "schema": 1, "mode": args.mode, "armed": True,
        "risk_confirmation": "interactive phrase matched", "preflight": original,
        "command": planned, "host_wall_ns": time.time_ns(),
        "host_monotonic_ns": time.monotonic_ns(), "gpu_work_not_yet_started": True,
        "one_shot": True, "auto_reboot": False, "auto_recovery": False,
        "core_limit_mib_requested": args.core_limit_mib,
        "separate_kfd_log": str(args.kfd_log) if args.kfd_log else None,
    })
    # Bound possible userspace core growth rather than blindly requesting
    # unlimited disk consumption. systemd-coredump limits may still override.
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_CORE)
        requested = args.core_limit_mib * 1024 * 1024
        bound = min(requested, hard) if hard != resource.RLIM_INFINITY else requested
        resource.setrlimit(resource.RLIMIT_CORE, (bound, hard))
    except (ValueError, OSError):
        pass
    journal = None
    journal_writer = None
    child = None
    start = time.monotonic()
    try:
        journal, journal_writer = _journal_start(args.out / "kernel-follow.log")
        time.sleep(1)
        if journal.poll() is not None:
            raise RuntimeError("journal follower exited before workload")
        # The intentionally hostile workload stays in a distinct process
        # group and never imports torch into this host-side supervisor.
        child = subprocess.Popen(planned, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True,
                                 bufsize=1, start_new_session=True)
        assert child.stdout is not None
        writer = threading.Thread(target=_copy_lines,
                                  args=(child.stdout, args.out / "child-output.log", "child"),
                                  daemon=True)
        writer.start()
        status = "returned"
        last_heartbeat = 0.0
        with (args.out / "host-heartbeat.jsonl").open("x", encoding="utf-8", buffering=1) as heartbeat:
            while child.poll() is None:
                now = time.monotonic()
                if now - last_heartbeat >= 2:
                    heartbeat.write(json.dumps({
                        "event": "host_alive", "monotonic_ns": time.monotonic_ns(),
                        "wall_time_ns": time.time_ns(), "child_pid": child.pid,
                        "child_returncode": child.poll(),
                        "note": "host heartbeat is not GPU forward-progress proof"
                    }, sort_keys=True) + "\n")
                    heartbeat.flush()
                    os.fsync(heartbeat.fileno())
                    last_heartbeat = now
                if now - start >= args.timeout:
                    status = "host_timeout_gpu_unhealthy"
                    # Never try an AMDGPU reset or new compute-healthcheck.
                    try:
                        os.killpg(child.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        child.wait(timeout=4)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(child.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    break
                time.sleep(0.25)
        writer.join(timeout=3)
        # Capture the *first* reset wave after child abort instead of shutting
        # down the journal follower at exactly SIGABRT. No GPU work is issued.
        if child.poll() != 0 and args.tail_seconds:
            time.sleep(args.tail_seconds)
        flush_json(args.out / "supervisor-result.json", {
            "result": status, "returncode": child.poll(),
            "elapsed_monotonic_seconds": round(time.monotonic() - start, 3),
            "gpu_health_after_failure": "not tested",
            "kernel_trace_does_not_prove_first_gpu_dispatch": True,
            "automatic_recovery_attempted": False,
        })
        return 0 if status == "returned" and child.returncode == 0 else 2
    finally:
        _stop(journal)
        if journal_writer is not None:
            journal_writer.join(timeout=3)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--python", type=Path, required=True,
                   help="exact Nix Python interpreter; no PATH/python3 fallback")
    p.add_argument("--out", type=Path, required=True,
                   help="new durable output directory, ideally separate disk/remote mount")
    p.add_argument("--mode", choices=("baseline", "rocprof"), default="baseline")
    p.add_argument("--rocprof", default="rocprofv3",
                   help="explicitly verified rocprofv3 executable for instrumented arm")
    p.add_argument("--expect-kernel",
                   help="optional exact host kernel release, e.g. 7.3.0-2-cachyos-bore")
    p.add_argument("--kfd-log", type=Path,
                   help="fresh separately armed KFD return-probe log; mandatory for baseline mode")
    p.add_argument("--core-limit-mib", type=int, default=1024,
                   help="bounded userspace core size; systemd-coredump may impose its own limits")
    p.add_argument("--tail-seconds", type=int, default=20,
                   help="capture post-abort recovery journal without new GPU work")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--arm", action="store_true",
                   help="EXPLICIT dangerous single execution, requires local typed phrase")
    a = p.parse_args()
    if a.timeout < 15 or a.timeout > 600:
        p.error("timeout must be 15..600 seconds; no unbounded stress")
    if a.tail_seconds < 0 or a.tail_seconds > 120:
        p.error("tail-seconds must be 0..120")
    if a.core_limit_mib < 0 or a.core_limit_mib > 8192:
        p.error("core-limit-mib must be 0..8192")
    try:
        return run(a)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as e:
        p.error(str(e))


if __name__ == "__main__":
    raise SystemExit(main())
