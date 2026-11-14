#!/usr/bin/env python3
"""Read-only GFX8 reset-wave chronology: reset-stage success vs post-reset GPU faults.

No HIP, GPU access, ioctl, modprobe, debugfs writes, or runtime tracing.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re

TIME = re.compile(r"\b(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<clock>\d\d:\d\d:\d\d)\b")
RESET_SUCCESS = re.compile(r"GPU reset\((?P<count>\d+)\) succeeded!")
RESET_BEGIN = re.compile(r"GPU reset begin!")
FATAL_AFTER = re.compile(r"ring (?:gfx|kiq|comp_[\d.]+|sdma[\d.]+) timeout|ring kiq[^\n]*test failed|VM fault \(|GPU fault detected", re.I)
KERNEL_EVENTS = (
    ("gfx_timeout", re.compile(r"ring gfx timeout", re.I)),
    ("kiq_failed", re.compile(r"ring kiq[^\n]*test failed", re.I)),
    ("kcq_disable_failed", re.compile(r"KCQ disable failed", re.I)),
    ("kfd_quiesce_failed", re.compile(r"Failed to quiesce KFD", re.I)),
    ("gfx_soft_reset_start", re.compile(r"Starting gfx_v8_0 IP block soft reset")),
    ("gfx_soft_reset_reported_success", re.compile(r"Successful gfx_v8_0 IP block soft reset")),
    ("baco", re.compile(r"\bBACO reset\b")),
    ("pci_config_reset", re.compile(r"\bPCI CONFIG reset\b")),
    ("asic_resume_attempt", re.compile(r"GPU reset succeeded, trying to resume")),
    ("vram_lost", re.compile(r"VRAM is lost due to GPU reset")),
    ("gpuvm_fault", re.compile(r"\bVM fault \(|VM_CONTEXT1_PROTECTION_FAULT_STATUS")),
    ("compute_timeout", re.compile(r"ring comp_[\d.]+ timeout", re.I)),
    ("kfd_restore_failed", re.compile(r"Failed to restore process queues|Failed to resume KFD", re.I)),
)

def parse(line: str, lineno: int, year: int = 2026) -> dict | None:
    match = TIME.search(line)
    if not match:
        return None
    try:
        dt = datetime.strptime(f"{year} {match.group(0)}", "%Y %b %d %H:%M:%S")
    except ValueError:
        return None
    kind = []
    for label, pattern in KERNEL_EVENTS:
        if pattern.search(line):
            kind.append(label)
    r = RESET_SUCCESS.search(line)
    if r:
        kind.append("gpu_reset_reported_success")
    if RESET_BEGIN.search(line):
        kind.append("gpu_reset_begin")
    if not kind:
        return None
    return {"line": lineno, "clock": dt.isoformat(), "types": kind,
            "reset_counter": int(r["count"]) if r else None,
            "text": line.strip()}

def analyse(lines: list[str], year: int = 2026, horizon: int = 10) -> dict:
    events = [parsed for i, line in enumerate(lines, 1)
              if (parsed := parse(line, i, year)) is not None]
    successes = []
    for i, event in enumerate(events):
        if "gpu_reset_reported_success" not in event["types"]:
            continue
        when = datetime.fromisoformat(event["clock"])
        following = []
        for after in events[i+1:]:
            diff = (datetime.fromisoformat(after["clock"]) - when).total_seconds()
            if diff < 0 or diff > horizon:
                continue
            if FATAL_AFTER.search(after["text"]):
                following.append({"seconds_after": int(diff), "line": after["line"],
                                  "types": after["types"], "text": after["text"]})
        successes.append({"success": event, "post_success_faults": following,
                          "post_success_fault_within_window": bool(following)})
    return {
        "schema": 1,
        "mode": "offline-journal-chronology",
        "year": year,
        "post_reset_window_seconds": horizon,
        "source_line_count": len(lines),
        "event_count": len(events),
        "first_events": events[:35],
        "reset_successes": successes,
        "key_findings": {
            "first_kiq_failure": next((e for e in events if "kiq_failed" in e["types"]), None),
            "first_baco": next((e for e in events if "baco" in e["types"]), None),
            "first_gpuvm_fault": next((e for e in events if "gpuvm_fault" in e["types"]), None),
            "success_then_fault_count": sum(s["post_success_fault_within_window"] for s in successes),
            "note": "reported reset completion never proves fresh KFD/DRM/Wayland usability; "
                    "source-level GFX8 basic ring test may have passed temporarily",
        },
        "no_gpu_executed": True,
    }

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--horizon", type=int, default=10)
    args = p.parse_args()
    if not 1 <= args.horizon <= 120:
        p.error("--horizon must be within 1..120 seconds")
    if args.output.exists():
        p.error("refuse to overwrite existing receipt")
    report = analyse(args.journal.read_text(errors="replace").splitlines(), args.year, args.horizon)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output),
                      "reported_successes": len(report["reset_successes"]),
                      "success_then_fault": report["key_findings"]["success_then_fault_count"],
                      "first_kiq": report["key_findings"]["first_kiq_failure"]["clock"] if report["key_findings"]["first_kiq_failure"] else None,
                      "first_baco": report["key_findings"]["first_baco"]["clock"] if report["key_findings"]["first_baco"] else None}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
