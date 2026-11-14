#!/usr/bin/env python3
"""Read-only incident/branch/binary inventory for gfx803 KFD K2.05.

No GPU commands, module unload, reboot, kernel mutation or sysfs writes.
Outputs exact evidence provenance and makes unknown branch state explicit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

KNOWN_RE = re.compile(r"(uni_mes|sched_policy|mes|amdgpu|kfd)", re.I)
MESSAGES = {
    "first_gfx_timeout": "ring gfx timeout",
    "preemption": "unsuccessful queues preemption",
    "quiesce": "Failed to quiesce KFD",
    "restore": "Failed to restore process queues",
    "resume": "Failed to resume KFD",
    "kiq": "ring kiq_0.2.1.0 test failed",
    "kcq": "KCQ disable failed",
    "baco": "BACO reset",
    "wedged": "device wedged",
}

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def command(args: list[str], *, timeout: int = 15) -> dict:
    if not shutil.which(args[0]):
        return {"status": "tool-missing", "argv": args}
    try:
        p = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout, check=False)
        return {"status": "ok" if p.returncode == 0 else "failed",
                "exit": p.returncode, "stdout": p.stdout[:65536],
                "stderr": p.stderr[:2048], "argv": args}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "error", "argv": args, "error": str(exc)}

def module_parameter(name: str, *, root: Path = Path("/sys/module/amdgpu/parameters")) -> dict:
    p = root / name
    try:
        return {"value": p.read_text().strip(), "scope": "postboot-only", "path": str(p)}
    except OSError as e:
        return {"value": None, "scope": "unknown", "error": str(e)}

def journal_events(raw: str) -> dict:
    lines = raw.splitlines()
    out = {}
    for key, token in MESSAGES.items():
        matches = [{"line": i + 1, "record": line[:1024]}
                   for i, line in enumerate(lines) if token.lower() in line.lower()]
        out[key] = {"count": len(matches), "first": matches[0] if matches else None}
    return out

def scan_boot(boot: str) -> dict:
    # boot is journalctl's index / identifier, not shell-interpolated.
    kernel = command(["journalctl", "-k", "-b", boot, "--no-pager", "-o", "short-iso"], timeout=25)
    matched = []
    for line in kernel.get("stdout", "").splitlines():
        if KNOWN_RE.search(line) and re.search(r"parameter|cmdline|command line|uni_mes|sched_policy", line, re.I):
            matched.append(line[:1200])
    return {"kernel_status": kernel["status"], "config_mentions": matched[:200],
            "config_conclusion": "unknown unless incident-time override/effective value is explicit"}

def analyze(journal: Path, handoff: dict, *, boot: str | None = None) -> dict:
    raw = journal.read_text(errors="replace")
    result = {
        "schema": 1, "mode": "read-only", "incident_journal": str(journal),
        "incident_journal_sha256": digest(journal),
        "matches_receipt_hash": digest(journal) == handoff.get("journal_sha256"),
        "first_log_events": journal_events(raw),
        "actual_incident_branch": None,
        "actual_evict_return": None,
        "compiled_branches": ["MES", "non-MES"],
        "log_text_evidence": {
            "non_mes_fence_timeout_message": "unsuccessful queues preemption" in raw,
            "meaning": "supports non-MES v7.3 source path; not proof without incident binary/state match"
        },
        "current_boot": {
            "uname": command(["uname", "-r"]),
            "cmdline": Path("/proc/cmdline").read_text().strip() if Path("/proc/cmdline").exists() else None,
            "uni_mes": module_parameter("uni_mes"), "sched_policy": module_parameter("sched_policy"),
            "modinfo": command(["modinfo", "-n", "amdgpu"]),
            "boot_list": command(["journalctl", "--list-boots"])
        },
        "historical_boot": scan_boot(boot) if boot else {"status": "not-selected"},
        "source_package_exact_match": bool(handoff.get("source_package_exact_match", False)),
        "limits": [
            "postboot parameters do not establish incident-time values",
            "module symbol/call-site presence does not establish incident invocation",
            "journal events are not a full execution trace",
            "no GPU work or active kernel tracing performed"
        ]
    }
    return result

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--handoff", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--historical-boot", help="exact journalctl boot ID/index; omit rather than guessing")
    a = p.parse_args()
    if a.out.exists():
        p.error("refusing to overwrite existing evidence")
    if not a.journal.is_file() or not a.handoff.is_file():
        p.error("journal and handoff must already exist")
    data = json.loads(a.handoff.read_text())
    result = analyze(a.journal, data, boot=a.historical_boot)
    if not result["matches_receipt_hash"]:
        p.error("journal SHA mismatch: refusing to interpret unrelated/altered incident log")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"wrote {a.out}; incident branch remains unknown; no GPU work")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
