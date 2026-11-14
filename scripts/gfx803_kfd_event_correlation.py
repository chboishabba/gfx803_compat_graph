#!/usr/bin/env python3
"""Offline SVM invalidation/preemption witness checker: structured events only.

This is a post-processing tool; it does NOT enable tracing, access debugfs,
perform GPU commands, or emit an instrumentation kernel patch.

The input is one newline-delimited JSON object per *instrumented* event:
 capture_id, boot_id, mm_id, pasid, monotonic_ns, event, range_id/invalidation_id
Capture identity and monotonic time domain must be the same for all events.
Merely seeing source symbols, userptr errors, or kernel journal strings cannot
create a witness. Example schema is in docs/GFX803_T2_KFD_SVM_USERPTR_FENCE_AUDIT.md.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

EVENTS = {
    "svm_range_register", "svm_invalidate_enter", "svm_invalidate_return",
    "kfd_quiesce_begin", "kfd_quiesce_end", "userptr_get_pages_failed",
    "hsa_memory_lock", "hip_dispatch", "gpu_ring_timeout"
}
NON_UNMAP = {"MMU_NOTIFY_MIGRATE", "MMU_NOTIFY_CLEAR", "MMU_NOTIFY_PROTECTION_PAGE",
             "MMU_NOTIFY_SOFT_DIRTY", "MMU_NOTIFY_EXCLUSIVE", "MMU_NOTIFY_UNKNOWN"}


def validate(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    capture = {(r.get("capture_id"), r.get("boot_id")) for r in rows}
    if len(capture) != 1 or any(not a or not b for a, b in capture):
        raise ValueError("capture_id and boot_id must be present and identical")
    seen = set()
    normalized = []
    for idx, r in enumerate(rows):
        for field in ("mm_id", "pasid", "monotonic_ns", "event"):
            if field not in r:
                raise ValueError(f"row {idx} lacks required field {field}")
        if not isinstance(r["monotonic_ns"], int) or r["monotonic_ns"] < 0:
            raise ValueError("monotonic_ns must be a nonnegative integer")
        if r["event"] not in EVENTS:
            raise ValueError(f"unknown event {r['event']}")
        if r["event"] in {"svm_invalidate_enter", "svm_invalidate_return"}:
            for field in ("range_id", "invalidation_id", "notifier_event"):
                if not r.get(field):
                    raise ValueError(f"row {idx} lacks {field}")
        if r["event"] in {"kfd_quiesce_begin", "kfd_quiesce_end"}:
            if not r.get("quiesce_id"):
                raise ValueError(f"row {idx} lacks quiesce_id")
        if not r["mm_id"] or r["pasid"] is None:
            raise ValueError("mm_id and pasid must be identified")
        key = (r["monotonic_ns"], r["mm_id"], r["event"],
               r.get("invalidation_id"), r.get("quiesce_id"))
        if key in seen:
            raise ValueError(f"duplicate event identity at row {idx}")
        seen.add(key)
        normalized.append(dict(r))
    normalized.sort(key=lambda r: (r["monotonic_ns"], r["event"]))
    return normalized


def correlate(rows: list[dict]) -> dict:
    rows = validate(rows)
    if not rows:
        return {"schema": 1, "witnesses": [], "status": "no-capture",
                "causal_attribution": "unproven"}
    captures = set((r["capture_id"], r["boot_id"]) for r in rows)
    assert len(captures) == 1
    groups = defaultdict(list)
    for e in rows:
        groups[(e["mm_id"], str(e["pasid"]))].append(e)
    candidates = []
    for (mm_id, pasid), evs in groups.items():
        quiesces = {}
        invalidations = {}
        for e in evs:
            if e["event"] == "kfd_quiesce_begin":
                quiesces.setdefault(e["quiesce_id"], {})["begin"] = e
            elif e["event"] == "kfd_quiesce_end":
                quiesces.setdefault(e["quiesce_id"], {})["end"] = e
            elif e["event"] == "svm_invalidate_enter":
                invalidations.setdefault(e["invalidation_id"], {})["enter"] = e
            elif e["event"] == "svm_invalidate_return":
                invalidations.setdefault(e["invalidation_id"], {})["return"] = e
        for qid, q in quiesces.items():
            begin = q.get("begin")
            end = q.get("end")
            if not begin or not end:
                continue
            start, stop = begin["monotonic_ns"], end["monotonic_ns"]
            if stop <= start:
                raise ValueError("quiesce end must follow begin")
            first = []
            other = []
            for inv_id, inv in invalidations.items():
                i = inv.get("enter")
                ret = inv.get("return")
                if not i or not ret:
                    continue
                if ret["monotonic_ns"] <= i["monotonic_ns"]:
                    raise ValueError("notifier return must follow entry")
                if (i["range_id"] != ret["range_id"] or
                        i["notifier_event"] != ret["notifier_event"]):
                    raise ValueError("notifier enter/return mismatched")
                if i["notifier_event"] == "MMU_NOTIFY_UNMAP":
                    continue  # different kernel branch
                if i["monotonic_ns"] <= start < ret["monotonic_ns"]:
                    first.append((inv_id, i, ret))
                if start < i["monotonic_ns"] < ret["monotonic_ns"] < stop:
                    other.append((inv_id, i, ret))
            for fid, fi, fr in first:
                for sid, si, sr in other:
                    if sid == fid or si["range_id"] == fi["range_id"]:
                        continue
                    if not fi.get("xnack_off", False) or not si.get("xnack_off", False):
                        continue
                    # Confirm the second notifier returned while the first
                    # quiesce operation was still in-flight.
                    if not (fi["monotonic_ns"] <= start <
                            si["monotonic_ns"] < sr["monotonic_ns"] < stop):
                        continue
                    candidates.append({
                        "capture_id": begin["capture_id"],
                        "boot_id": begin["boot_id"], "mm_id": mm_id, "pasid": pasid,
                        "quiesce_id": qid,
                        "first_invalidation_id": fid,
                        "first_range_id": fi["range_id"],
                        "second_invalidation_id": sid,
                        "second_range_id": si["range_id"],
                        "quiesce_begin_ns": start,
                        "second_return_ns": sr["monotonic_ns"],
                        "quiesce_end_ns": stop,
                        "quiesce_return_code": end.get("return_code"),
                        "status": "ordering-overlap-witness",
                        "causal_gpu_hang_attribution": "not-established",
                    })
    return {
        "schema": 1, "mode": "offline-structured-notifier-correlation",
        "capture_id": rows[0]["capture_id"], "boot_id": rows[0]["boot_id"],
        "events": len(rows), "witnesses": candidates,
        "status": "overlap-observed" if candidates else "no-matching-overlap-in-provided-events",
        "causal_attribution": "unproven",
        "required_capture_coverage": "Complete or declared sampled event stream; no overlap does not imply absence when incomplete",
        "gpu_commands": 0,
    }


def load_jsonl(p: Path) -> list[dict]:
    result = []
    for i, line in enumerate(p.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid JSONL at line {i}: {e}") from e
        if not isinstance(row, dict):
            raise ValueError(f"line {i} must be JSON object")
        result.append(row)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        ap.error("refuse overwrite")
    try:
        report = correlate(load_jsonl(args.events))
    except (ValueError, OSError) as e:
        ap.error(str(e))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"],
                      "witnesses": len(report["witnesses"]), "gpu_commands": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
