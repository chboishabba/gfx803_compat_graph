#!/usr/bin/env python3
"""Compare gfx803 compatibility/release manifests and emit bounded update notes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STATUS_ORDER = {
    "pass": 4,
    "partial": 3,
    "fail": 2,
    "hang": 1,
    "crash": 0,
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def _component_changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    old = _mapping(before.get("components"))
    new = _mapping(after.get("components"))
    changes = []
    for component in sorted(set(old) | set(new)):
        old_value = old.get(component)
        new_value = new.get(component)
        if old_value != new_value:
            changes.append({
                "component": component,
                "before": old_value,
                "after": new_value,
            })
    return changes


def _set_changes(before: Any, after: Any) -> dict[str, list[str]]:
    old = _string_set(before)
    new = _string_set(after)
    return {
        "added": sorted(new - old),
        "removed": sorted(old - new),
    }


def _benchmark_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    old_summary = _mapping(before.get("benchmark_summary"))
    new_summary = _mapping(after.get("benchmark_summary"))
    old = _mapping(old_summary.get("statuses"))
    new = _mapping(new_summary.get("statuses"))

    changes: dict[str, list[dict[str, Any]]] = {
        "promotions": [],
        "regressions": [],
        "changed_unknown": [],
        "added": [],
        "removed": [],
    }

    for record in sorted(set(old) | set(new)):
        if record not in old:
            changes["added"].append({"record": record, "status": new[record]})
            continue
        if record not in new:
            changes["removed"].append({"record": record, "status": old[record]})
            continue

        old_status = old[record]
        new_status = new[record]
        if old_status == new_status:
            continue

        row = {"record": record, "before": old_status, "after": new_status}
        if old_status in STATUS_ORDER and new_status in STATUS_ORDER:
            if STATUS_ORDER[new_status] > STATUS_ORDER[old_status]:
                changes["promotions"].append(row)
            else:
                changes["regressions"].append(row)
        else:
            changes["changed_unknown"].append(row)

    return changes


def _evidence_changes(before: dict[str, Any], after: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    old = _mapping(before.get("evidence"))
    new = _mapping(after.get("evidence"))
    changes = []
    for claim in sorted(set(old) | set(new)):
        old_value = old.get(claim)
        new_value = new.get(claim)
        if old_value != new_value:
            changes.append({"claim": claim, "before": old_value, "after": new_value})

    unpaid = sorted(
        claim
        for claim, state in new.items()
        if state in {"unpaid", "unknown", "not-run", "not_run", None, False}
    )
    return changes, unpaid


def diff_manifests(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    evidence_changes, unpaid_evidence = _evidence_changes(before, after)
    return {
        "from_release": before.get("release_id"),
        "to_release": after.get("release_id"),
        "from_stack": before.get("stack_id"),
        "to_stack": after.get("stack_id"),
        "component_changes": _component_changes(before, after),
        "target_changes": _set_changes(before.get("targets"), after.get("targets")),
        "patch_changes": _set_changes(before.get("patch_set"), after.get("patch_set")),
        "benchmark_changes": _benchmark_changes(before, after),
        "evidence_changes": evidence_changes,
        "unpaid_evidence": unpaid_evidence,
    }


def _fmt(value: Any) -> str:
    return "∅" if value is None else str(value)


def _bullet(lines: list[str], text: str) -> None:
    lines.append(f"- {text}")


def render_markdown(delta: dict[str, Any]) -> str:
    stack = delta.get("to_stack") or delta.get("from_stack") or "stack"
    old_release = _fmt(delta.get("from_release"))
    new_release = _fmt(delta.get("to_release"))
    lines = [f"# {stack} update: {old_release} → {new_release}", ""]

    lines.extend(["## Component/source deltas", ""])
    if delta["component_changes"]:
        for row in delta["component_changes"]:
            _bullet(lines, f"`{row['component']}`: `{_fmt(row['before'])}` → `{_fmt(row['after'])}`")
    else:
        _bullet(lines, "No recorded component/source changes.")
    lines.append("")

    lines.extend(["## Target and patch deltas", ""])
    for label, key in (("Targets added", "target_changes"), ("Patches added", "patch_changes")):
        values = delta[key]["added"]
        _bullet(lines, f"{label}: " + (", ".join(f"`{x}`" for x in values) if values else "none"))
    for label, key in (("Targets removed", "target_changes"), ("Patches removed", "patch_changes")):
        values = delta[key]["removed"]
        _bullet(lines, f"{label}: " + (", ".join(f"`{x}`" for x in values) if values else "none"))
    lines.append("")

    validation_sections = [
        ("Validation promotions", "promotions"),
        ("Validation regressions", "regressions"),
        ("New validation observations", "added"),
        ("Removed validation observations", "removed"),
        ("Validation changes with unknown ordering", "changed_unknown"),
    ]
    benchmark = delta["benchmark_changes"]
    for title, key in validation_sections:
        lines.extend([f"## {title}", ""])
        rows = benchmark[key]
        if not rows:
            _bullet(lines, "None recorded.")
        else:
            for row in rows:
                if "before" in row:
                    _bullet(lines, f"`{row['record']}`: {row['before']} → {row['after']}")
                else:
                    _bullet(lines, f"`{row['record']}`: {row['status']}")
        lines.append("")

    lines.extend(["## Evidence-state changes", ""])
    if delta["evidence_changes"]:
        for row in delta["evidence_changes"]:
            _bullet(lines, f"`{row['claim']}`: {_fmt(row['before'])} → {_fmt(row['after'])}")
    else:
        _bullet(lines, "No recorded evidence-state changes.")
    lines.append("")

    lines.extend(["## Evidence still unpaid", ""])
    if delta["unpaid_evidence"]:
        for claim in delta["unpaid_evidence"]:
            _bullet(lines, f"`{claim}`")
    else:
        _bullet(lines, "None recorded in the target manifest.")
    lines.append("")

    lines.extend([
        "## Interpretation boundary",
        "",
        "This report compares recorded manifests. A changed version, target, patch, or benchmark status does not by itself establish a causal mechanism, hardware support guarantee, or release-readiness promotion.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diff two gfx803 compatibility/release manifests.")
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))
    delta = diff_manifests(before, after)
    markdown = render_markdown(delta)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(delta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(markdown, encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(markdown, end="")


if __name__ == "__main__":
    main()
