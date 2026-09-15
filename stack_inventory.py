#!/usr/bin/env python3
"""Collect reproducible gfx803 stack coordinates for release/update diffs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


GPU_TARGET_RE = re.compile(r"\bgfx[0-9a-f]{3,5}\b", re.IGNORECASE)
DYNAMIC_RE = re.compile(r"\((SONAME|NEEDED)\).*?\[([^\]]+)\]")


def parse_readelf_dynamic(text: str) -> dict[str, Any]:
    soname = None
    needed: list[str] = []
    for kind, value in DYNAMIC_RE.findall(text):
        if kind == "SONAME":
            soname = value
        elif kind == "NEEDED":
            needed.append(value)
    return {"soname": soname, "needed": sorted(dict.fromkeys(needed))}


def parse_strings_gpu_targets(text: str) -> list[str]:
    return sorted({match.lower() for match in GPU_TARGET_RE.findall(text)})


def _normalize_agent_key(key: str) -> str:
    return {
        "Name": "name",
        "Uuid": "uuid",
        "Marketing Name": "marketing_name",
        "Vendor Name": "vendor_name",
        "Node": "node",
        "Device Type": "device_type",
        "Chip ID": "chip_id",
        "BDFID": "bdfid",
        "Compute Unit": "compute_unit",
        "Wavefront Size": "wavefront_size",
        "Fast F16 Operation": "fast_f16",
    }.get(key, "")


def parse_rocminfo_agents(text: str) -> list[dict[str, str]]:
    agents: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if re.fullmatch(r"Agent\s+\d+", line):
            if current and current.get("device_type") == "GPU":
                agents.append(current)
            current = {}
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized = _normalize_agent_key(key.strip())
        if normalized:
            current[normalized] = value.strip()
    if current and current.get("device_type") == "GPU":
        agents.append(current)
    return agents


def _run(cmd: list[str], timeout: int = 30) -> tuple[int | None, str]:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_elf(path: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": _sha256(path),
        "soname": None,
        "needed": [],
        "gpu_targets": [],
    }

    if shutil.which("readelf"):
        rc, output = _run(["readelf", "-d", str(path)])
        if rc == 0:
            record.update(parse_readelf_dynamic(output))

    if shutil.which("strings"):
        rc, output = _run(["strings", "-a", str(path)], timeout=60)
        if rc == 0:
            record["gpu_targets"] = parse_strings_gpu_targets(output)

    return record


def collect_stack_inventory(root: Path) -> dict[str, Any]:
    root = root.resolve()
    components: dict[str, Any] = {}
    all_targets: set[str] = set()
    errors: list[dict[str, str]] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        name = path.name
        if ".so" not in name and not name.endswith((".hsaco", ".co")):
            continue
        try:
            record = inspect_elf(path)
        except (OSError, ValueError) as exc:
            errors.append({"path": str(path), "error": str(exc)})
            continue
        key = record.get("soname") or str(path.relative_to(root))
        # Preserve collisions rather than silently replacing a same-SONAME file.
        if key in components:
            key = f"{key}@{path.relative_to(root)}"
        components[key] = record
        all_targets.update(record.get("gpu_targets", []))

    topology: dict[str, Any] = {"agents": []}
    rocminfo_rc = None
    if shutil.which("rocminfo"):
        rocminfo_rc, output = _run(["rocminfo"], timeout=30)
        topology = {
            "rocminfo_returncode": rocminfo_rc,
            "agents": parse_rocminfo_agents(output) if rocminfo_rc == 0 else [],
        }

    evidence = {
        "elf_inventory": "paid" if components else "unpaid",
        "gpu_target_inventory": "paid" if all_targets else "unpaid",
        "topology": "paid" if topology.get("agents") else "unpaid",
    }

    return {
        "inventory_root": str(root),
        "components": components,
        "targets": sorted(all_targets),
        "topology": topology,
        "inventory_evidence": evidence,
        "inventory_errors": errors,
    }


def merge_inventory_into_manifest(manifest: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    merged = dict(manifest)
    merged["components"] = inventory.get("components", {})
    merged["targets"] = inventory.get("targets", [])
    merged["topology"] = inventory.get("topology", {"agents": []})
    merged["inventory_root"] = inventory.get("inventory_root")
    merged["inventory_errors"] = inventory.get("inventory_errors", [])
    evidence = dict(merged.get("evidence") or {})
    evidence.update(inventory.get("inventory_evidence") or {})
    merged["evidence"] = evidence
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory a ROCm/gfx803 artifact tree.")
    parser.add_argument("root", help="ROCm/artifact root to scan")
    parser.add_argument("--out", required=True, help="Write raw inventory JSON here")
    parser.add_argument("--manifest", help="Optional existing release manifest to enrich")
    parser.add_argument("--manifest-out", help="Write enriched manifest here")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inventory = collect_stack_inventory(Path(args.root))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.manifest:
        if not args.manifest_out:
            raise SystemExit("--manifest-out is required with --manifest")
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        merged = merge_inventory_into_manifest(manifest, inventory)
        Path(args.manifest_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.manifest_out).write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
