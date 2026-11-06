#!/usr/bin/env python3
"""Compare deterministic stream and non-stream chat contracts using fixtures only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ENVELOPE_COMPARE_FIELDS = [
    "id",
    "object",
    "model",
    "created",
    "choices",
    "usage",
    "error",
]

DECISION_COMPARE_FIELDS = [
    "route",
    "decision",
    "tool_allowed",
    "tool_calls_requested",
]

TOOL_COMPARE_FIELDS = [
    "tool_calls_disabled",
    "tool_calls_requested",
    "tool_calls_executed",
]


def normalize_choice(choice: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "index": choice.get("index"),
        "message": choice.get("message"),
        "delta": choice.get("delta"),
        "finish_reason": choice.get("finish_reason"),
    }


def normalize_envelope(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {
        field: payload.get(field) for field in ENVELOPE_COMPARE_FIELDS if field in payload
    }
    if "choices" in payload:
        normalized["choices"] = [normalize_choice(choice) for choice in payload.get("choices", [])]
    return normalized


def select_fields(packet: Dict[str, Any], fields: Iterable[str]) -> Dict[str, Any]:
    return {field: packet.get(field) for field in fields}


def load_fixtures(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get("fixtures", [])


def compare_records(fixture: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    non_stream = fixture["non_stream"]
    stream = fixture["stream"]

    envelope_match = normalize_envelope(non_stream["envelope"]) == normalize_envelope(
        stream["final_envelope"]
    )
    if not envelope_match:
        errors.append("response_envelope_mismatch")

    decision_match = (
        select_fields(non_stream["decision_packet"], DECISION_COMPARE_FIELDS)
        == select_fields(stream["decision_packet"], DECISION_COMPARE_FIELDS)
    )
    if not decision_match:
        errors.append("decision_packet_mismatch")

    tool_match = (
        select_fields(non_stream["tool_usage"], TOOL_COMPARE_FIELDS)
        == select_fields(stream["tool_usage"], TOOL_COMPARE_FIELDS)
    )
    if not tool_match:
        errors.append("tool_usage_mismatch")

    context_match = (
        non_stream.get("execute_context") == stream.get("execute_context")
    )
    if not context_match:
        errors.append("execute_context_mismatch")

    status_match = non_stream.get("status") == stream.get("status")
    if not status_match:
        errors.append("status_mismatch")

    return (
        not errors,
        errors,
        {
            "envelope_match": envelope_match,
            "decision_match": decision_match,
            "tool_match": tool_match,
            "context_match": context_match,
            "status_match": status_match,
        },
    )


def build_summary(fixture_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    passed = sum(1 for row in fixture_results if row["result"] == "PASS")
    failed = len(fixture_results) - passed
    return {
        "total": len(fixture_results),
        "pass": passed,
        "fail": failed,
        "status": "PASS" if failed == 0 else "FAIL",
        "fixtures": fixture_results,
        "compared_fields": {
            "envelope": ENVELOPE_COMPARE_FIELDS,
            "decision": DECISION_COMPARE_FIELDS,
            "tool_usage": TOOL_COMPARE_FIELDS,
            "execute_context": ["orchestrator", "execute_context"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare /api/v2/chat and /api/v2/chat/stream fixture parity.",
    )
    parser.add_argument(
        "--fixture-path",
        default=str(
            Path(__file__).parent / "chat_parity_fixtures.json"
        ),
        help="Path to parity fixtures JSON.",
    )
    parser.add_argument(
        "--report-path",
        default=str(
            Path(__file__).parent / "chat_parity_report.json"
        ),
        help="Path to write JSON report.",
    )
    args = parser.parse_args()

    fixture_path = Path(args.fixture_path)
    report_path = Path(args.report_path)
    fixtures = load_fixtures(fixture_path)

    fixture_results: List[Dict[str, Any]] = []
    for fixture in fixtures:
        passed, reasons, checks = compare_records(fixture)
        fixture_results.append(
            {
                "name": fixture.get("name"),
                "category": fixture.get("category"),
                "result": "PASS" if passed else "FAIL",
                "reasons": reasons,
                "checks": checks,
                "path": {
                    "non_stream": fixture["non_stream"]["endpoint"],
                    "stream": fixture["stream"]["endpoint"],
                },
            }
        )

    summary = build_summary(fixture_results)
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
