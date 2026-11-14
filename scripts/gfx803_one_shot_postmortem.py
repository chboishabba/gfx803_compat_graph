#!/usr/bin/env python3
"""Offline join of one-shot TopK artifacts after the GPU has recovered.

Requires no GPU, root, device, debugfs or journal access. Imported ROCprof
records may share neither journal timestamps nor time domain. A captured
kernel launch is NOT automatically the first failed GPU dispatch.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

EXPECTED_LIB_SHA = "c1ad552aac76766b14ad78b993b5e3ee7a3b72c7fc48b7d72345516cf6fba7ff"
RETURN_EVENTS = {"fence_wait_return", "unmap_return", "quiesce_return"}
RING = re.compile(r"ring\s+(gfx|comp_[0-9.]+|kiq[^\s]+|sdma[^\s]*)\s+timeout", re.I)
KIQ = re.compile(r"ring\s+kiq[^\s]+\s+test failed\s*\((-\d+)\)", re.I)


def load_json(path: Path):
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> tuple[list[dict], list[str]]:
    if not path.is_file():
        return [], [f"missing: {path.name}"]
    rows, issues = [], []
    for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
            else:
                issues.append(f"non-object row {path.name}:{lineno}")
        except json.JSONDecodeError:
            issues.append(f"invalid or partial JSON {path.name}:{lineno}")
    return rows, issues


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rocprof_summary(folder: Path, *, last_n: int = 20, max_csv_bytes: int = 250_000_000) -> dict:
    if not folder.is_dir():
        return {"status": "no-rocprof-output", "files": [], "kernel_records": []}
    files, records = [], []
    for path in sorted(folder.rglob("*.csv")):
        if path.stat().st_size > max_csv_bytes:
            files.append({"path": str(path), "status": "too-large-for-default-parser",
                          "bytes": path.stat().st_size})
            continue
        candidate = "kernel" in path.name.lower() and "trace" in path.name.lower()
        info = {"path": str(path), "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "kind": "kernel-trace" if candidate else "other-rocprof-csv"}
        files.append(info)
        if not candidate:
            continue
        try:
            with path.open(newline="", errors="replace") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames:
                    info["parse_issue"] = "no CSV header"
                    continue
                seen = 0
                for row in reader:
                    if not isinstance(row, dict):
                        continue
                    seen += 1
                    rec = {"source_csv": str(path),
                           "row_number": seen + 1,
                           "fields": {k: v for k, v in row.items() if
                                      any(word in k.lower() for word in (
                                          "kernel", "symbol", "grid", "workgroup",
                                          "queue", "dispatch", "start", "end",
                                          "correlation", "agent", "device"))}}
                    records.append(rec)
                    if len(records) > last_n:
                        records.pop(0)
                info["rows_counted"] = seen
        except (OSError, csv.Error, UnicodeError) as exc:
            info["parse_issue"] = str(exc)
    return {"status": "kernel-records-captured" if records else "no-readable-kernel-csv",
            "files": files, "kernel_records": records,
            "last_n": last_n,
            "dispatch_causality": "launch/record identity does not prove first stalled dispatch",
            "timing": "retain original ROCprof time domain; not joined to host monotonic without calibration"}


def analyze(folder: Path, *, kfd_path: Path | None = None) -> dict:
    preflight_path = folder / "preflight.json"
    if not preflight_path.is_file():
        raise ValueError("no armed preflight receipt; cannot admit run")
    preflight = load_json(preflight_path)
    if preflight.get("armed") is not True or preflight.get("one_shot") is not True:
        raise ValueError("receipt is not an armed one-shot")
    children, child_errors = load_jsonl(folder / "child-events.jsonl")
    heartbeats, heartbeat_errors = load_jsonl(folder / "host-heartbeat.jsonl")
    external, kfd_errors = load_jsonl(kfd_path) if kfd_path else ([], ["no external KFD capture"])
    runtime = next((e.get("runtime") for e in children
                    if e.get("event") == "pre_gpu_dispatch"), None)
    if runtime is not None and runtime.get("libtorch_hip_sha256") != EXPECTED_LIB_SHA:
        raise ValueError("different GPU library from original incident core")
    kfd_returns = [r for r in external if r.get("event") in RETURN_EVENTS
                   and isinstance(r.get("monotonic_ns"), int)]
    kfd_returns.sort(key=lambda r: r["monotonic_ns"])
    journal_path = folder / "kernel-follow.log"
    journal_evidence = []
    if journal_path.is_file():
        for lineno, line in enumerate(journal_path.read_text(errors="replace").splitlines(), 1):
            m = RING.search(line)
            k = KIQ.search(line)
            if m:
                journal_evidence.append({"line": lineno, "kind": "ring-timeout",
                                         "ring": m.group(1), "text": line[:600]})
            if k:
                journal_evidence.append({"line": lineno, "kind": "kiq-test-failed",
                                         "errno": int(k.group(1)), "text": line[:600]})
            if "Failed to quiesce KFD" in line:
                journal_evidence.append({"line": lineno, "kind": "kfd-quiesce-failed",
                                         "text": line[:600]})
            if "BACO reset" in line:
                journal_evidence.append({"line": lineno, "kind": "baco-reset",
                                         "text": line[:600]})
    roc = rocprof_summary(folder / "rocprof")
    has_pre = runtime is not None
    return {
        "schema": 1, "mode": "offline-one-shot-postmortem",
        "capture_folder": str(folder),
        "original_core_gpu_library_sha256": EXPECTED_LIB_SHA,
        "runtime_prepinned": has_pre,
        "runtime": runtime,
        "child_start_event": any(x.get("event") == "one_shot_start" for x in children),
        "child_end_event": any(x.get("event") == "one_shot_end" for x in children),
        "host_heartbeat_count": len(heartbeats),
        "first_recorded_gpu_issue": journal_evidence[0] if journal_evidence else None,
        "journal_evidence_count": len(journal_evidence),
        "journal_evidence": journal_evidence[:150],
        "first_kfd_return_in_captured_stream": kfd_returns[0] if kfd_returns else None,
        "kfd_return_events_count": len(kfd_returns),
        "kfd_return_events": kfd_returns[:150],
        "kfd_input": str(kfd_path) if kfd_path else None,
        "rocprof": roc,
        "parse_warnings": child_errors + heartbeat_errors + kfd_errors,
        "gates": {
            "original_nix_binary_match": "verified-child" if has_pre else "not-captured",
            "new_run_first_kfd_return": "observed" if kfd_returns else "not-captured",
            "new_run_kernel_dispatch_metadata": "records-present-not-first-stall-proof" if roc["kernel_records"] else "not-captured",
            "first_stalled_gpu_instruction": "open",
            "SVM_two_range_invalidation": "open-not-captured",
            "persistent_gpu_recovery": "open-not-tested",
        },
        "gpu_commands": 0,
        "claims": ["not the historical November first KFD return",
                   "kernel launch is not evidence it stalled first",
                   "missing profiler tail on asynchronous SIGABRT is inconclusive",
                   "absence of SVM probes is not evidence of absence"],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--kfd-log", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        p.error("refuse overwrite")
    try:
        report = analyze(a.capture, kfd_path=a.kfd_log)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": report["gates"], "gpu_commands": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
