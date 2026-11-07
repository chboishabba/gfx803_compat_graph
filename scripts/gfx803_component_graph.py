#!/usr/bin/env python3
"""Exact Schaka ROCm 10.1 component pin parser and incremental build planner.

Source provenance: Schaka/rocm-gfx803 scripts/ci/resolve-pins.sh, the
docker-bake.hcl component topology and build-pipeline.yml. This parser
rejects unrecorded/malformed/partial pins. It does NOT build ROCm.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PIN_SOURCES = {
    "ROCM_SYSTEMS_REF": "ROCm/rocm-systems",
    "ROCM_LIBRARIES_REF": "ROCm/rocm-libraries",
    "MIGRAPHX_REF": "ROCm/AMDMIGraphX",
    "PYTORCH_REF": "ROCm/pytorch",
    "TORCHVISION_REF": "pytorch/vision",
    "TORCHAUDIO_REF": "ROCm/audio",
    "ORT_VERSION": "microsoft/onnxruntime",
    "TRITON_REF": "triton-lang/triton",
}
SHA = re.compile(r"^[0-9a-f]{40}$")
# Ordered topologically, matching Schaka's component-level source pipeline.
COMPONENTS = {
    "rocr-clr": {"pins": ["ROCM_SYSTEMS_REF"], "needs": []},
    "rocblas": {"pins": ["ROCM_LIBRARIES_REF"], "needs": ["rocr-clr"]},
    "miopen": {"pins": ["ROCM_LIBRARIES_REF"], "needs": ["rocr-clr"]},
    "rocsolver": {"pins": ["ROCM_LIBRARIES_REF"], "needs": ["rocblas"]},
    "migraphx": {"pins": ["MIGRAPHX_REF"], "needs": ["rocblas", "miopen", "rocsolver"]},
    "pytorch": {"pins": ["PYTORCH_REF"], "needs": ["migraphx"]},
    "torchvision": {"pins": ["TORCHVISION_REF"], "needs": ["pytorch"]},
    "torchaudio": {"pins": ["TORCHAUDIO_REF"], "needs": ["pytorch"]},
    "ort": {"pins": ["ORT_VERSION"], "needs": ["migraphx"]},
    "triton": {"pins": ["TRITON_REF"], "needs": []},
    "vllm": {"pins": [], "needs": ["pytorch"]},
    "final": {"pins": [], "needs": [
        "rocr-clr", "rocblas", "miopen", "rocsolver", "migraphx",
        "pytorch", "torchvision", "torchaudio", "ort", "triton", "vllm"]},
}


def parse_pins(stamped: str) -> dict[str, str]:
    if not isinstance(stamped, str):
        raise ValueError("source pin label must be a string")
    result: dict[str, str] = {}
    parts = stamped.split()
    if len(parts) != len(PIN_SOURCES):
        raise ValueError(f"expected {len(PIN_SOURCES)} fully resolved source pins")
    for part in parts:
        if part.count("=") != 1:
            raise ValueError("malformed source pin assignment")
        name, value = part.split("=", 1)
        if name not in PIN_SOURCES or name in result:
            raise ValueError("unexpected or duplicate source pin " + name)
        if not SHA.fullmatch(value):
            raise ValueError("source pin must be exact commit SHA: " + name)
        result[name] = value
    if set(result) != set(PIN_SOURCES):
        raise ValueError("missing required source pins")
    return result


def impacted_components(old: dict[str, str], new: dict[str, str]) -> list[str]:
    if set(old) != set(PIN_SOURCES) or set(new) != set(PIN_SOURCES):
        raise ValueError("impact planning requires complete pin dictionaries")
    changed = {k for k in PIN_SOURCES if old[k] != new[k]}
    affected = set()
    for name, details in COMPONENTS.items():
        if changed.intersection(details["pins"]):
            affected.add(name)
        if any(dep in affected for dep in details["needs"]):
            affected.add(name)
    return [name for name in COMPONENTS if name in affected]


def source_manifest(pins: dict[str, str], schaka_sha: str) -> dict:
    if not SHA.fullmatch(schaka_sha):
        raise ValueError("missing Schaka's exact own source commit")
    if set(pins) != set(PIN_SOURCES):
        raise ValueError("incomplete source pin graph")
    for value in pins.values():
        if not SHA.fullmatch(value):
            raise ValueError("nonimmutable component source ref")
    return {
        "schema_version": 1, "state": "source-graph-only-not-native-build",
        "source_repo": "Schaka/rocm-gfx803", "source_revision": schaka_sha,
        "sources": {k: {"repo": PIN_SOURCES[k], "rev": pins[k]}
                    for k in PIN_SOURCES},
        "components": COMPONENTS,
        "notes": [
            "The base ROCm compiler/OS image digest remains a distinct lock.",
            "Patch inventory and build-time inputs must be preserved from Schaka.",
            "This graph defines rebuild impact only; no native Nix builds are claimed.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate", required=True,
                   help="manifest after actual Schaka OCI import")
    p.add_argument("--out", required=True)
    p.add_argument("--compare", help="optional previous source-graph JSON")
    args = p.parse_args()
    candidate = json.loads(Path(args.candidate).read_text())
    provenance = candidate.get("provenance") or {}
    pins = parse_pins(provenance.get("published_component_pins"))
    manifest = source_manifest(pins, candidate["upstream_revision"])
    if args.compare:
        prev = json.loads(Path(args.compare).read_text())
        old = {key: obj["rev"] for key, obj in prev["sources"].items()}
        manifest["invalidated_components"] = impacted_components(old, pins)
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
