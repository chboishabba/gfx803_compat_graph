#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from lane_contracts import EXAMPLE_DIR, SCHEMA_DIR, load_example, validate_payload


ROOT = Path(__file__).resolve().parent.parent


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    require(SCHEMA_DIR.exists(), "schemas directory is missing")
    require(EXAMPLE_DIR.exists(), "examples directory is missing")

    observation_ids: set[str] = set()
    for obs_path in sorted(EXAMPLE_DIR.glob("*.execution_observation.json")):
        obs = load_example(obs_path.name)
        validate_payload(obs, "execution_observation")
        observation_ids.add(obs["observation_id"])

    require(observation_ids, "no execution observations found")

    for claim_path in sorted(EXAMPLE_DIR.glob("*.compatibility_claim.json")):
        claim = load_example(claim_path.name)
        validate_payload(claim, "compatibility_claim")
        for ref in claim["observation_refs"]:
            require(ref in observation_ids, f"{claim_path.name} references unknown observation_id: {ref}")

    print("lane artifacts validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
