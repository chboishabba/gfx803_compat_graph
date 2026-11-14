#!/usr/bin/env python3
"""One-shot, deliberately armed GFX803 TopK case-4 reproduction/capture.

DEFAULT IS PREFLIGHT ONLY; no torch import, HIP initialization or GPU dispatch.
An execution can wedge the only Wayland display GPU and require manual reboot.
No retry, GPU reset, post-failure healthcheck or automatic reboot.

Uses the exact original benchmark's _one(4, 10, 50) implementation in an
isolated child, rather than pretending a different torch.topk sequence was
the historical reproducer. The child entrypoint/argv differs from the
original. The record states that distinction explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "docs/receipts/gfx803_topk_incident_core_provenance_20261114.json"
BENCH = ROOT / "scripts/gfx803_topk_pr8_benchmark.py"
ACK = "I ACCEPT THE GPU WEDGE AND MANUAL REBOOT"
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
DANGEROUS = ("/tmp", "/run", "/dev/shm")
MAP_TAGS = ("libtorch_hip", "libamdhip", "libhsa", "roc", "torch", "sgemm", "shim")
PROBES = ("amdkfd_fence_wait_timeout", "unmap_queues_cpsch", "kgd2kfd_quiesce_mm")
BT = ROOT / "scripts/gfx803_kfd_return_capture.bt"

CHILD = r'''
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("original_topk_benchmark", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.CASES[4] == ((32,151936),50,"float32")
print("CAPTURE_CHILD_ENTER original_case=4 warmup=10 iterations=50", flush=True)
result = module._one(4,10,50)
print(json.dumps({"case":4,"result":result},sort_keys=True),flush=True)
'''


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def expected() -> dict:
    data = json.loads(ORIGINAL.read_text())
    if data["incident"]["case"] != 4 or data["runtime"]["sgemm_shim_preloaded"] is not True:
        raise ValueError("incident provenance is not the known TopK case-4 SGEMM-shim configuration")
    return data


def check_build_id(path: Path) -> str:
    readelf = shutil.which("readelf")
    if not readelf:
        raise ValueError("readelf is mandatory for ELF Build ID checking")
    cp = subprocess.run([readelf, "-n", str(path)], stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, timeout=35)
    if cp.returncode:
        raise ValueError("readelf -n failed: " + cp.stderr[-500:])
    ids = re.findall(r"Build ID:\s*([0-9a-fA-F]+)", cp.stdout)
    if len(set(ids)) != 1:
        raise ValueError("could not uniquely identify libtorch_hip GNU Build ID")
    return ids[0].lower()


def validate_paths(python: Path, overlay: Path, rocm: Path, shim: Path) -> dict:
    data = expected()
    if overlay.resolve() != Path(data["runtime"]["torch_overlay"]).resolve():
        raise ValueError("overlay must match immutable incident core provenance")
    if rocm.resolve() != Path(data["runtime"]["rocm_root"]).resolve():
        raise ValueError("ROCm root must match immutable incident core provenance")
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError("explicit selected Python executable missing")
    if not rocm.is_dir():
        raise ValueError("pinned incident ROCm root missing")
    if not shim.is_file():
        raise ValueError("must supply actual preloaded SGEMM shim file")
    lib = overlay / "torch/lib/libtorch_hip.so"
    if not lib.is_file():
        raise ValueError("incident libtorch_hip.so missing under torch-site")
    digest = sha256(lib)
    exp = data["runtime"]["libtorch_hip"]
    if digest != exp["sha256"]:
        raise ValueError("refusing wrong incident libtorch_hip SHA-256")
    build = check_build_id(lib)
    if build != exp["gnu_build_id"]:
        raise ValueError("refusing wrong incident libtorch_hip Build ID")
    if not BENCH.is_file():
        raise ValueError("original benchmark source not present")
    return {"libtorch_hip": str(lib), "sha256": digest, "build_id": build,
            "shim_path": str(shim), "shim_sha256": sha256(shim),
            "benchmark_sha256": sha256(BENCH),
            "python": str(python), "rocm": str(rocm), "overlay": str(overlay)}


def validate_kfd_bpftrace() -> dict:
    tool = shutil.which("bpftrace")
    if not tool or not BT.is_file():
        raise ValueError("opt-in bpftrace binary and exact probe script are required")
    available = Path("/sys/kernel/tracing/available_filter_functions")
    if not available.is_file():
        available = Path("/sys/kernel/debug/tracing/available_filter_functions")
    if not available.is_file():
        raise ValueError("cannot inspect running-kernel kprobe function availability")
    names = set()
    for line in available.read_text(errors="replace").splitlines():
        if line.strip():
            names.add(line.split()[0].split(".")[0])
    missing = [n for n in PROBES if n not in names]
    if missing:
        raise ValueError("cannot attach required KFD return probes; missing: " + ",".join(missing))
    return {"binary": tool, "script": str(BT), "script_sha256": sha256(BT),
            "functions": list(PROBES), "kind": "instrumentation-changing-kretprobes"}


def build_env(overlay: Path, rocm: Path, shim: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(overlay) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    existing_preloads = env.get("LD_PRELOAD", "").split()
    if existing_preloads and any(Path(x).resolve() != shim.resolve() for x in existing_preloads):
        raise ValueError("unexpected LD_PRELOAD library; cannot replicate original incident")
    env["LD_PRELOAD"] = str(shim)
    # The original Nix environment may have additional loader paths; record,
    # do not manufacture undocumented runtime paths or declare them equal.
    env["LD_LIBRARY_PATH"] = str(rocm / "lib") + os.pathsep + str(rocm / "core-10.1/lib") + (
        os.pathsep + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    return env


def durable_directory(path: Path) -> None:
    root = path.expanduser().resolve()
    if any(root == Path(x) or Path(x) in root.parents for x in DANGEROUS):
        raise ValueError("refusing volatile /tmp, /run or /dev/shm as capture output")
    if root.exists():
        raise ValueError("refusing existing output directory (one shot only)")
    if not root.parent.is_dir():
        raise ValueError("output parent must already exist on a persistent filesystem")
    if not os.access(root.parent, os.W_OK):
        raise ValueError("output parent not writable")


def sync_json(path: Path, obj: dict) -> None:
    with path.open("x") as fp:
        json.dump(obj, fp, indent=2, sort_keys=True)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())


def persist_lines(stream, path: Path, stop: threading.Event) -> None:
    with path.open("a", buffering=1) as fp:
        try:
            while not stop.is_set():
                line = stream.readline()
                if not line:
                    break
                fp.write(line)
                fp.flush()
                os.fsync(fp.fileno())
        except (OSError, ValueError):
            pass


def maps_watcher(pid: int, path: Path, stop: threading.Event) -> None:
    seen = set()
    with path.open("a", buffering=1) as fp:
        while not stop.is_set():
            try:
                lines = Path(f"/proc/{pid}/maps").read_text(errors="replace").splitlines()
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                break
            for line in lines:
                if not any(tag in line.lower() for tag in MAP_TAGS):
                    continue
                if line in seen:
                    continue
                seen.add(line)
                fp.write(f"{time.time_ns()} {line}\n")
                fp.flush()
                os.fsync(fp.fileno())
            stop.wait(0.02)


def run_capture(args, identity: dict, env: dict) -> int:
    durable_directory(args.out)
    args.out.mkdir(mode=0o700)
    boot = BOOT_ID.read_text().strip() if BOOT_ID.is_file() else "unknown"
    run_id = str(uuid.uuid4())
    manifest = {"schema": 1, "mode": "ONE-SHOT-KNOWN-GPU-HANG", "run_id": run_id,
                "boot_id": boot, "start_unix_ns": time.time_ns(),
                "incident_original_case": 4, "shape": [32,151936],
                "dtype": "float32", "k": 50, "warmup": 10, "iterations": 50,
                "entrypoint_different_from_incident": True,
                "used_original_benchmark_one_function": True,
                "expected_incident_core_sha256": expected()["incident"]["core_sha256"],
                "identity": identity,
                "LD_PRELOAD": env["LD_PRELOAD"],
                "LD_LIBRARY_PATH": env.get("LD_LIBRARY_PATH"),
                "PYTHONPATH": env.get("PYTHONPATH"),
                "kernel_release": os.uname().release,
                "known_risk": "GPU may permanently wedge until manual host reboot",
                "kfd_probe": args.probe_info,
                "automatic_retry": False, "automatic_reset": False,
                "automatic_reboot": False,
                "capture_limits": ["journal and maps do NOT expose actual stalled HSACO",
                                   "unprobed KFD internal return remains unknown",
                                   "timing differs from original process"] }
    sync_json(args.out / "manifest.json", manifest)
    stop = threading.Event()
    watchers = []
    journal = None
    probe = None
    log = args.out / "kernel-journal.log"
    log.touch(mode=0o600)
    # Journal follow starts BEFORE HIP child and persistently flushes lines.
    try:
        journal = subprocess.Popen(["journalctl", "-k", "-f", "-n", "0",
                                    "-o", "short-iso-precise", "--no-pager"],
                                   stdout=subprocess.PIPE, stderr=(args.out / "journal-stderr.log").open("w"),
                                   text=True, bufsize=1)
        t = threading.Thread(target=persist_lines,
                             args=(journal.stdout, log, stop), daemon=True)
        t.start()
        watchers.append(t)
        time.sleep(0.6)
        if journal.poll() is not None:
            raise RuntimeError("journal follower exited; refusing GPU dispatch")
        if args.enable_kfd_probes:
            with (args.out / "kfd-return-probe-stderr.log").open("w") as probe_stderr:
                probe = subprocess.Popen([args.probe_info["binary"], "-q",
                                          str(BT)], stdout=subprocess.PIPE,
                                         stderr=probe_stderr, text=True, bufsize=1)
            t = threading.Thread(target=persist_lines,
                                 args=(probe.stdout, args.out / "kfd-return-probe.log",
                                       stop), daemon=True)
            t.start()
            watchers.append(t)
            time.sleep(1.5)
            if probe.poll() is not None:
                raise RuntimeError("KFD bpftrace probe attachment failed; refusing GPU dispatch")
        cmd = [str(args.python), "-u", "-c", CHILD, str(BENCH)]
        with (args.out / "child-stdout.log").open("w", buffering=1) as stdout, (
             args.out / "child-stderr.log").open("w", buffering=1) as stderr:
            child = subprocess.Popen(cmd, env=env, stdout=stdout, stderr=stderr,
                                     stdin=subprocess.DEVNULL, start_new_session=True)
            with (args.out / "child-pid.txt").open("x") as fp:
                fp.write(str(child.pid)+"\n")
                fp.flush()
                os.fsync(fp.fileno())
            t = threading.Thread(target=maps_watcher,
                                 args=(child.pid, args.out / "loaded-maps.log", stop), daemon=True)
            t.start()
            watchers.append(t)
            try:
                returncode = child.wait(timeout=args.max_seconds)
                status = "child-exited"
            except subprocess.TimeoutExpired:
                # No automatic GPU reset or new kernel dispatch; a wedged
                # kernel may ignore SIGTERM. Avoid retry/extra GPU probing.
                status = "child-timeout-possible-wedge"
                returncode = None
            with (args.out / "result.json").open("x") as fp:
                json.dump({"status": status, "child_returncode": returncode,
                           "child_pid": child.pid, "end_unix_ns": time.time_ns(),
                           "manual_reboot_may_be_required": True}, fp, indent=2)
                fp.write("\n")
                fp.flush()
                os.fsync(fp.fileno())
            return 0 if returncode == 0 else 3
    finally:
        stop.set()
        if probe is not None and probe.poll() is None:
            probe.terminate()
            try:
                probe.wait(timeout=3)
            except subprocess.TimeoutExpired:
                probe.kill()
        if journal is not None and journal.poll() is None:
            journal.terminate()
            try:
                journal.wait(timeout=3)
            except subprocess.TimeoutExpired:
                journal.kill()
        for t in watchers:
            t.join(timeout=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True,
                        help="actual original candidate Python interpreter")
    parser.add_argument("--shim", type=Path, required=True,
                        help="actual SGEMM shim .so, not an invented substitute")
    parser.add_argument("--out", type=Path, required=True,
                        help="new directory on persistent filesystem, not /tmp")
    parser.add_argument("--max-seconds", type=int, default=180)
    parser.add_argument("--enable-kfd-probes", action="store_true",
                        help="EXTRA RISK: attach 3 KFD kretprobes; changes kernel tracing and timing")
    parser.add_argument("--execute", action="store_true",
                        help="HANG RISK: dispatch case 4 exactly once")
    parser.add_argument("--accept-single-display-risk", action="store_true",
                        help="acknowledge compositor and RX580 may require manual reboot")
    parser.add_argument("--ack", default="",
                        help="literal phrase displayed by --help/README")
    a = parser.parse_args()
    if a.max_seconds < 10 or a.max_seconds > 1800:
        parser.error("max-seconds must be 10..1800")
    data = expected()
    overlay = Path(data["runtime"]["torch_overlay"])
    rocm = Path(data["runtime"]["rocm_root"])
    try:
        identity = validate_paths(a.python, overlay, rocm, a.shim)
        env = build_env(overlay, rocm, a.shim)
        durable_directory(a.out)
        if not shutil.which("journalctl"):
            raise ValueError("journalctl missing, no durable kernel event capture")
        a.probe_info = validate_kfd_bpftrace() if a.enable_kfd_probes else None
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
    if not a.execute:
        print(json.dumps({"mode": "PREFLIGHT-ONLY-NO-GPU",
                          "identity": identity, "output": str(a.out),
                          "kfd_probe": a.probe_info,
                          "warning": "Known GPU wedge; execution requires explicit arm and acknowledgment"},
                         indent=2))
        return 0
    if a.ack != ACK or not a.accept_single_display_risk:
        parser.error("execute requires --accept-single-display-risk AND --ack '" + ACK + "'")
    print("ARMED: exactly one case-4 f32 32x151936 TopK; NO RESTART, NO GPU RESET", flush=True)
    if a.enable_kfd_probes:
        print("WARNING: KFD kretprobes enabled; can change scheduling/timing", flush=True)
    try:
        return run_capture(a, identity, env)
    except (OSError, RuntimeError) as exc:
        print("CAPTURE REFUSED/FAILED: " + str(exc), file=sys.stderr, flush=True)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
