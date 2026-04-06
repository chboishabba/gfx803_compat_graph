from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas"
EXAMPLE_DIR = ROOT / "artifacts" / "lane_claims" / "examples"

SCHEMA_FILES = {
    "execution_observation": "execution_observation.schema.json",
    "compatibility_claim": "compatibility_claim.schema.json",
}


def load_schema(schema_name: str) -> dict[str, Any]:
    filename = SCHEMA_FILES[schema_name]
    return json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))


def load_example(filename: str) -> dict[str, Any]:
    return json.loads((EXAMPLE_DIR / filename).read_text(encoding="utf-8"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_execution_observation(payload: dict[str, Any]) -> None:
    required = {
        "observation_id",
        "lane_id",
        "workload_id",
        "captured_at",
        "command",
        "environment",
        "metrics",
    }
    missing = required - payload.keys()
    _require(not missing, f"missing execution observation fields: {sorted(missing)}")
    _require(isinstance(payload["command"], list) and payload["command"], "command must be a non-empty list")
    _require(isinstance(payload["environment"], dict), "environment must be an object")
    _require(isinstance(payload["metrics"], dict) and payload["metrics"], "metrics must be a non-empty object")
    trace_refs = payload.get("trace_refs", [])
    proof_refs = payload.get("proof_refs", [])
    _require(bool(trace_refs) or bool(proof_refs), "execution observation must have trace_refs or proof_refs")


def _validate_compatibility_claim(payload: dict[str, Any]) -> None:
    required = {
        "claim_id",
        "lane_id",
        "claim_scope",
        "witness_label",
        "promotion_status",
        "statement",
        "observation_refs",
    }
    missing = required - payload.keys()
    _require(not missing, f"missing compatibility claim fields: {sorted(missing)}")
    _require(isinstance(payload["observation_refs"], list) and payload["observation_refs"], "observation_refs must be non-empty")


def validate_payload(payload: dict[str, Any], schema_name: str) -> None:
    # Mirror the ITIR-suite contracts surface, but keep validation local and
    # dependency-free because jsonschema is not installed in this repo env.
    if schema_name == "execution_observation":
        _validate_execution_observation(payload)
        return
    if schema_name == "compatibility_claim":
        _validate_compatibility_claim(payload)
        return
    raise KeyError(f"unknown schema_name: {schema_name}")
