#!/usr/bin/env python3
"""Read-only gfx7/gfx8 KFD doorbell and queue-validation provenance audit.

The 2025 upstream callback patch deliberately installs zero-return stubs for
gfx7/gfx8. Their presence establishes null-callback protection only; it does
not prove an SDMA reset, historical callback invocation, or recovery success.
No HIP, GPU, tracefs, module, or reset operation is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

PATCHES = {
    "sdma_callback": "34659c1a1f4fd4c148ab13e13b11fd64df01ffcd",
    "gfx7_8_queue_validation": "542c3bb836733a1325874310d54d25b4907ed10e",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def callback_file(path: Path) -> dict:
    text = path.read_text(errors="replace")
    implementation = "static uint32_t kgd_hqd_sdma_get_doorbell" in text
    assignment = bool(re.search(
        r"\.hqd_sdma_get_doorbell\s*=\s*kgd_hqd_sdma_get_doorbell", text))
    zero_stub = bool(re.search(
        r"kgd_hqd_sdma_get_doorbell[\s\S]{0,300}?return\s+0\s*;", text))
    return {
        "path": str(path), "sha256": sha256(path),
        "callback_implementation": implementation,
        "callback_assignment": assignment,
        "intentional_zero_return_stub": zero_stub,
    }


def queue_validation_file(path: Path) -> dict:
    text = path.read_text(errors="replace")
    gfx7_8_guard = bool(re.search(
        r"gfx_target_version\s*>=\s*70000[\s\S]{0,300}?gfx_target_version\s*<\s*90000", text))
    half_size = bool(re.search(r"queue_size\s*/\s*2", text))
    ring_uses_expected = bool(re.search(
        r"ring_bo\s*,\s*expected_queue_size", text))
    return {
        "path": str(path), "sha256": sha256(path),
        "gfx7_8_guard": gfx7_8_guard,
        "half_queue_size": half_size,
        "ring_validation_uses_expected_size": ring_uses_expected,
    }


def module_zero_stub_audit(path: Path) -> dict:
    """Read-only symbol/disassembly check for the two gfx7/gfx8 stubs."""
    if not path.is_file():
        raise ValueError("module file missing: " + str(path))
    nm = subprocess.run(["nm", "-a", "-n", str(path)], check=False,
                        capture_output=True, text=True)
    if nm.returncode:
        raise ValueError("nm could not inspect module")
    addresses = []
    for line in nm.stdout.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] == "kgd_hqd_sdma_get_doorbell":
            addresses.append(int(fields[0], 16))
    stubs = []
    for address in addresses:
        dis = subprocess.run(
            ["objdump", "-d", "--start-address=" + hex(address),
             "--stop-address=" + hex(address + 32), str(path)],
            check=False, capture_output=True, text=True)
        stubs.append({"address": hex(address),
                      "zero_return_instruction": "xor    %eax,%eax" in dis.stdout})
    return {"path": str(path), "sha256": sha256(path),
            "stub_symbol_count": len(stubs), "stubs": stubs,
            "two_zero_return_stubs_present": len(stubs) >= 2 and all(
                row["zero_return_instruction"] for row in stubs)}


def audit(source: Path, expected_release_sha256: str | None,
          module: Path | None = None) -> dict:
    root = source.resolve()
    bridge = [
        root / "drivers/gpu/drm/amd/amdgpu/amdgpu_amdkfd_gfx_v7.c",
        root / "drivers/gpu/drm/amd/amdgpu/amdgpu_amdkfd_gfx_v8.c",
    ]
    queue = root / "drivers/gpu/drm/amd/amdkfd/kfd_queue.c"
    missing = [str(p) for p in (*bridge, queue) if not p.is_file()]
    if missing:
        raise ValueError("required source files missing: " + ", ".join(missing))
    callbacks = {p.name: callback_file(p) for p in bridge}
    validation = queue_validation_file(queue)
    callback_present = all(
        row["callback_implementation"] and row["callback_assignment"] and
        row["intentional_zero_return_stub"] for row in callbacks.values())
    queue_patch_present = all(validation[key] for key in (
        "gfx7_8_guard", "half_queue_size", "ring_validation_uses_expected_size"))
    result = {
        "schema": 1,
        "mode": "offline-source-only-doorbell-queue-audit",
        "upstream_patches": PATCHES,
        "source_root": str(root),
        "source_release_sha256": expected_release_sha256,
        "callbacks": callbacks,
        "queue_validation": validation,
        "sdma_callback_source_present": callback_present,
        "queue_validation_source_present": queue_patch_present,
        "callback_called_in_incident": None,
        "incident_queue_validation_path": None,
        "binary_source_rebuild_match": False,
        "gpu_executed": False,
        "limits": [
            "zero-return callbacks protect unconditional calls; they do not supply a doorbell value",
            "source presence does not establish historical callback invocation",
            "the original KFD return and TopK kernel remain unobserved",
        ],
    }
    if module is not None:
        result["postboot_module"] = module_zero_stub_audit(module)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-source", type=Path, required=True)
    parser.add_argument("--release-sha256")
    parser.add_argument("--module", type=Path,
                        help="optional decompressed postboot amdgpu.ko for read-only stub audit")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite existing receipt")
    try:
        result = audit(args.kernel_source, args.release_sha256, args.module)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("source audit complete; GPU calls 0; incident invocation remains unknown")


if __name__ == "__main__":
    main()
