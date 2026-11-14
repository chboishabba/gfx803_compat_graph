#!/usr/bin/env python3
"""Conservative offline GPU incident evidence join (no device/trace access).

Ingest retained kernel journals, CSV benchmark data, JSONL harness events,
and text incident reports. No timestamp is manufactured for observations that
lack one; detection is not causal attribution. Negative evidence requires an
explicitly scoped, complete trace, never the absence of a log string.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

PATTERNS = {
    "gpu_ring_timeout": re.compile(r"ring\s+(?P<ring>(?:gfx|comp_[0-9.]+|sdma[0-9.]+|kiq[^\s]*))\s+timeout\b", re.I),
    "kiq_ring_test_failed": re.compile(r"ring\s+kiq[^\s]*\s+test\s+failed\s*\((?P<errno>-[0-9]+)\)", re.I),
    "kfd_quiesce_failed": re.compile(r"Failed to quiesce KFD", re.I),
    "kfd_restore_failed": re.compile(r"Failed to restore process queues|Failed to resume KFD", re.I),
    "kfd_preemption_failed": re.compile(r"unsuccessful queues preemption", re.I),
    "kfd_fence_expired": re.compile(r"qcm fence wait loop timeout expired", re.I),
    "kcq_disable_failed": re.compile(r"KCQ disable failed", re.I),
    "baco_reset": re.compile(r"\bBACO reset\b", re.I),
    "vram_lost": re.compile(r"VRAM is lost due to GPU reset", re.I),
    "gpuvm_fault": re.compile(r"VM fault\s*\(0x|VM_CONTEXT1_PROTECTION_FAULT_STATUS", re.I),
    "userptr_get_pages_failed": re.compile(r"init_user_pages:\s*Failed to get user pages:\s*(?P<errno>-[0-9]+)", re.I),
    "svm_eviction": re.compile(r"\bsvm_range_evict\b", re.I),
    "svm_registration": re.compile(r"\bsvm_range_(?:register|add|create)\b|hsa_amd_memory_lock", re.I),
    "oom_kill": re.compile(r"Out of memory: Killed process|systemd-oomd.*killed", re.I),
    "process_segv": re.compile(r"segfault at|\bSIGSEGV\b", re.I),
    "gpu_hang": re.compile(r"GPU Hang|HW Exception by GPU", re.I),
}
DATE = re.compile(r"^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d\d?)\s+(?P<hms>\d\d:\d\d:\d\d)")
ISO = re.compile(r"(?P<date>20\d\d-\d\d-\d\d)[T ](?P<hms>\d\d:\d\d:\d\d)(?P<frac>\.\d+)?(?P<offset>Z|[+-]\d\d:?\d\d)?")
GPU_PID = re.compile(r"\bProcess\s+(?P<name>[^\s]+)\s+pid\s+(?P<pid>\d+)")
RESET = re.compile(r"GPU reset\((?P<counter>\d+)\) succeeded!")
STAGE = re.compile(r"\b(?P<stage>transcribe|align|load_model|load_audio)\b", re.I)


def digest(p: Path) -> dict:
    raw = p.read_bytes()
    return {"path": str(p), "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw)}


def parse_time(line: str, year: int) -> str | None:
    iso = ISO.search(line)
    if iso:
        z = iso.group(0)
        try:
            return datetime.fromisoformat(z.replace("Z", "+00:00")).isoformat()
        except ValueError:
            return None
    m = DATE.search(line)
    if m:
        try:
            return datetime.strptime(f"{year} {m['mon']} {m['day']} {m['hms']}",
                                     "%Y %b %d %H:%M:%S").isoformat()
        except ValueError:
            return None
    return None


def parse_journal(path: Path, year: int, incident: str) -> list[dict]:
    out = []
    for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        for kind, rex in PATTERNS.items():
            match = rex.search(line)
            if not match:
                continue
            e = {"incident": incident, "kind": kind, "time": parse_time(line, year),
                 "origin": "kernel-journal", "source": str(path), "line": n,
                 "evidence": line.strip()[:900], "confidence": "observed-log"}
            for key, val in match.groupdict().items():
                if val is not None:
                    e[key] = val
            pid = GPU_PID.search(line)
            if pid:
                e.update(pid.groupdict())
            out.append(e)
        rst = RESET.search(line)
        if rst:
            out.append({"incident": incident, "kind": "reset_reported_success",
                        "time": parse_time(line, year), "origin": "kernel-journal",
                        "source": str(path), "line": n,
                        "counter": int(rst["counter"]),
                        "confidence": "observed-log",
                        "evidence": line.strip()[:900]})
    return out


def parse_csv(path: Path, incident: str) -> list[dict]:
    with path.open(newline="", errors="replace") as fp:
        reader = csv.DictReader(fp)
        if not reader.fieldnames or not {"shape", "status"}.issubset(reader.fieldnames):
            return []
        return [{"incident": incident, "kind": "benchmark_case", "time": None,
                 "origin": "benchmark-csv", "source": str(path), "line": i,
                 "shape": row.get("shape"), "dtype": row.get("dtype"),
                 "k": row.get("k"), "status": row.get("status"),
                 "error": row.get("error"), "confidence": "observed-csv"}
                for i, row in enumerate(reader, 2)]


def parse_jsonl(path: Path, incident: str) -> list[dict]:
    out = []
    for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            out.append({"incident": incident, "kind": "malformed_jsonl",
                        "origin": "jsonl", "source": str(path), "line": i,
                        "time": None, "confidence": "parser-warning"})
            continue
        if not isinstance(item, dict):
            continue
        raw_time = next((item[k] for k in ("timestamp", "time", "ts", "utc")
                         if isinstance(item.get(k), str)), None)
        action = str(item.get("event", item.get("type", "unclassified")))
        out.append({"incident": incident, "kind": "harness_event",
                    "event": action, "stage": item.get("stage"),
                    "time": parse_time(raw_time or "", 2026),
                    "origin": "harness-jsonl", "source": str(path), "line": i,
                    "confidence": "observed-jsonl"})
    return out


def parse_markdown(path: Path, incident: str) -> list[dict]:
    # The report is a human-written retrospective. Never label it a raw
    # device observation or claim it contains incident-time dispatch telemetry.
    out = []
    for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        kinds = [kind for kind, rex in PATTERNS.items() if rex.search(line)]
        for kind in kinds:
            out.append({"incident": incident, "kind": kind, "time": None,
                        "origin": "retrospective-note", "source": str(path), "line": i,
                        "confidence": "secondary-report",
                        "evidence": line.strip()[:900]})
    return out


def parse_file(path: Path, year: int, incident: str) -> list[dict]:
    name = path.name.lower()
    if name.endswith(".csv"):
        return parse_csv(path, incident)
    if name.endswith(".jsonl"):
        return parse_jsonl(path, incident)
    if name.endswith(".md"):
        return parse_markdown(path, incident)
    if name.endswith(".log") or name.endswith(".txt"):
        return parse_journal(path, year, incident)
    raise ValueError(f"unsupported input type {path}")


def gate(events: list[dict], incident: str) -> dict:
    own = [e for e in events if e["incident"] == incident]
    raw = [e for e in own if e["origin"] == "kernel-journal"]
    def found(kinds: set[str]) -> list[dict]:
        return [e for e in raw if e["kind"] in kinds]
    ring = found({"gpu_ring_timeout"})
    def first(evs):
        dated = [e for e in evs if e.get("time")]
        return min(dated, key=lambda x: (x["time"], x["line"])) if dated else None
    svms = found({"svm_registration", "svm_eviction"})
    userptr = found({"userptr_get_pages_failed"})
    preempt = found({"kfd_preemption_failed", "kfd_quiesce_failed",
                     "kfd_fence_expired"})
    return {
        "incident": incident,
        "raw_ring_timeout_count": len(ring),
        "first_logged_ring_timeout": first(ring),
        "first_logged_userptr_failure": first(userptr),
        "raw_userptr_failures": len(userptr),
        "raw_svm_mentions": len(svms),
        "raw_preemption_failures": len(preempt),
        "first_logged_preemption_failure": first(preempt),
        "first_logged_baco": first(found({"baco_reset"})),
        "runtime_svm_registration": "open-not-captured",
        "two_concurrent_svm_invalidations": "open-not-captured",
        "first_stalled_dispatch": "open-not-captured",
        "original_queue_fence_errno": "open-not-captured",
        "historical_userptr_error_cause": "open-not-captured",
        "status_note": "no log mention is not evidence of no SVM/userptr use",
    }


def join(inputs: list[tuple[str, Path]], year: int = 2026) -> dict:
    files, events = [], []
    for incident, path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
        meta = digest(path)
        meta["incident"] = incident
        files.append(meta)
        events.extend(parse_file(path, year, incident))
    incidents = sorted(set(incident for incident, _ in inputs))
    events.sort(key=lambda e: (e["incident"], e["time"] is None,
                               e["time"] or "", e["source"], e["line"], e["kind"]))
    return {"schema": 1, "mode": "offline-read-only-incident-join",
            "files": files, "events": events,
            "gates": {incident: gate(events, incident) for incident in incidents},
            "gpu_commands": 0, "kernel_tracing_enabled": False,
            "claim_rules": [
                "kernel ring attribution identifies a timed-out submitter, not the first bad instruction",
                "retrospective notes are secondary, undated incident summaries",
                "static code-object presence does not prove dispatch",
                "no SVM mention does not establish absence of SVM registration",
                "a userptr failure is not automatically an SVM eviction",
                "a reported reset success is not lasting GPU recovery",
                "source-reachable does not mean incident-activated",
            ]}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", nargs=2, metavar=("INCIDENT", "FILE"),
                   action="append", required=True)
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        p.error("refuse to overwrite evidence receipt")
    try:
        out = join([(k, Path(v)) for k, v in args.input], args.year)
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"inputs": len(out["files"]), "events": len(out["events"]),
                      "incidents": list(out["gates"]), "gpu_commands": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
