#!/usr/bin/env python3
"""Capture a real gfx803 acceptance command and hash its retained log.

A process exit code of zero is not a passing diffusion receipt: the
historical probe_diffusion.py deliberately reports PARTIAL_PASS (6/7)
without returning a nonzero shell exit code. --expect-diffusion-all-pass
checks the structured PROBE_JSON before recording a passing result.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shlex
import subprocess
import sys
import uuid
from pathlib import Path

# Also works when invoked directly as python3 scripts/gfx803_capture.py.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from scripts.gfx803_release import REQUIRED, OPTIONAL, AdmissionError, load, write
except ModuleNotFoundError:
    from gfx803_release import REQUIRED, OPTIONAL, AdmissionError, load, write


def assess_diffusion_log(path: Path) -> tuple[bool, str]:
    summaries = []
    with Path(path).open("r", encoding="utf-8", errors="replace") as source:
        for line in source:
            if line.startswith("PROBE_JSON:"):
                try:
                    summaries.append(json.loads(line[len("PROBE_JSON:"):]))
                except json.JSONDecodeError:
                    return False, "invalid PROBE_JSON"
    if len(summaries) != 1:
        return False, f"expected one PROBE_JSON, found {len(summaries)}"
    result = summaries[0]
    tests = result.get("tests")
    if not isinstance(tests, dict) or not tests:
        return False, "missing structured individual diffusion tests"
    if result.get("total") != len(tests) or result.get("passed") != len(tests):
        return False, "partial diffusion test pass"
    if any(not isinstance(t, dict) or t.get("status") != "pass"
           for t in tests.values()):
        return False, "one or more diffusion tests are not pass"
    return True, f"all {len(tests)} diffusion tests passed"


def capture(candidate_path: Path, evidence_root: Path, gate: str,
            argv: list[str], *, expect_diffusion: bool = False,
            expect_text: list[str] | None = None) -> tuple[dict, bool]:
    if gate not in REQUIRED + OPTIONAL:
        raise AdmissionError("unknown or non-mandatory gate " + gate)
    if not argv:
        raise AdmissionError("empty command")
    candidate = load(candidate_path)
    if candidate.get("state") != "candidate":
        raise AdmissionError("receipt capture requires an unpromoted candidate")
    evidence_root.mkdir(parents=True, exist_ok=True)
    logname = gate + "-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logname += "-" + uuid.uuid4().hex[:12] + ".log"
    output = evidence_root / logname
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    with output.open("wb") as log:
        log.write(("# gfx803 acceptance command\n# started_utc=" + stamp +
                   "\n# argv=" + shlex.join(argv) + "\n").encode())
        log.flush()
        try:
            proc = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, check=False)
            code = proc.returncode
        except OSError as exc:
            code = 127
            log.write(("\ncommand-launch-error: " + str(exc) + "\n").encode())
        log.write(("\n# process_returncode=" + str(code) + "\n").encode())
    passed = code == 0
    reasons = []
    if code:
        reasons.append("command exited " + str(code))
    if expect_diffusion:
        ok, detail = assess_diffusion_log(output)
        passed = passed and ok
        if not ok:
            reasons.append(detail)
    if expect_text:
        # Match literal expected text in the retained log (not regex).
        with output.open("r", encoding="utf-8", errors="replace") as inp:
            txt = inp.read()
        for expected in expect_text:
            if expected not in txt:
                reasons.append("missing required output: " + expected)
                passed = False
    sha = hashlib.sha256()
    with output.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            sha.update(chunk)
    entry = {
        "status": "pass" if passed else "fail",
        "command": shlex.join(argv),
        "log_path": logname,
        "log_sha256": sha.hexdigest(),
        "return_code": code,
        "started_utc": stamp,
        "check": "all-diffusion-tests" if expect_diffusion else "command-and-text",
        "reason": "; ".join(reasons) if reasons else "executed checks passed",
    }
    candidate.setdefault("evidence", {})[gate] = entry
    write(candidate_path, candidate)
    return entry, passed


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate", required=True)
    p.add_argument("--evidence-root", required=True)
    p.add_argument("--gate", choices=REQUIRED + OPTIONAL, required=True)
    p.add_argument("--expect-diffusion-all-pass", action="store_true")
    p.add_argument("--expect-text", action="append", default=[])
    p.add_argument("cmd", nargs=argparse.REMAINDER,
                   help="command after --, without shell expansion")
    args = p.parse_args()
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    try:
        result, accepted = capture(
            Path(args.candidate), Path(args.evidence_root), args.gate,
            cmd, expect_diffusion=args.expect_diffusion_all_pass,
            expect_text=args.expect_text)
    except (AdmissionError, ValueError, OSError) as exc:
        p.exit(2, "NOT RECORDED: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if accepted else 3


if __name__ == "__main__":
    raise SystemExit(main())
