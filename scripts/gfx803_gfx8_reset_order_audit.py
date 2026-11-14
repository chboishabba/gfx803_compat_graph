#!/usr/bin/env python3
"""Offline, fail-closed GFX8 reset-order audit for source trees. No HIP/GPU."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

SOURCE_FILES = {
    "device": "drivers/gpu/drm/amd/amdgpu/amdgpu_device.c",
    "queue": "drivers/gpu/drm/amd/amdkfd/kfd_device_queue_manager.c",
    "gfx8": "drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c",
}


def strip_comments(text: str) -> str:
    """Remove C comments; sufficient for identifying the named functions."""
    return re.sub(r"/\*[\s\S]*?\*/|//[^\n]*", lambda m: " " * len(m.group(0)), text)


def function_body(source: str, name: str) -> str:
    clean = strip_comments(source)
    match = re.search(r"\b" + re.escape(name) + r"\s*\([^;]*?\)\s*\{", clean)
    if match is None:
        raise ValueError("definition not found: " + name)
    begin = clean.find("{", match.start())
    depth = 0
    for i in range(begin, len(clean)):
        if clean[i] == "{":
            depth += 1
        elif clean[i] == "}":
            depth -= 1
            if depth == 0:
                return clean[begin + 1:i]
    raise ValueError("unbalanced function: " + name)


def order_of(body: str, first: str, second: str) -> str:
    a, b = body.find(first), body.find(second)
    if a < 0 or b < 0:
        return "unknown"
    return "first-before-second" if a < b else "second-before-first"


def audit(source: dict[str, str]) -> dict:
    """Only classifies known code orderings; never proves physical causality."""
    d = source["device"]
    q = source["queue"]
    g = source["gfx8"]
    recover = function_body(d, "amdgpu_device_gpu_recover")
    halt = function_body(d, "amdgpu_device_halt_activities")
    pci = function_body(d, "amdgpu_pci_error_detected")
    unmap = function_body(q, "unmap_queues_cpsch")
    restore = function_body(q, "restore_process_queues_cpsch")
    mqd = function_body(g, "gfx_v8_0_mqd_init")
    pre_helper = "amdgpu_device_kfd_pre_reset("
    lock = "amdgpu_device_recovery_get_reset_lock("
    halt_call = "amdgpu_device_halt_activities("
    if pre_helper in recover and order_of(recover, pre_helper, lock) == "first-before-second":
        reset_order = "preempt-before-reset-lock"
    elif (order_of(recover, lock, halt_call) == "first-before-second"
          and "amdgpu_amdkfd_pre_reset(" in halt):
        reset_order = "reset-lock-before-kfd-preempt"
    else:
        reset_order = "unknown"
    if pre_helper in pci and order_of(pci, pre_helper, lock) == "first-before-second":
        pci_order = "preempt-before-reset-lock"
    elif (order_of(pci, lock, halt_call) == "first-before-second"
          and "amdgpu_amdkfd_pre_reset(" in halt):
        pci_order = "reset-lock-before-kfd-preempt"
    else:
        pci_order = "unknown"
    sched_order = order_of(recover, "amdgpu_device_sched_resume(",
                           "amdgpu_device_gpu_resume(")
    if sched_order == "first-before-second":
        sched_status = "schedulers-before-gpu-kfd-post-reset"
    elif sched_order == "second-before-first":
        sched_status = "gpu-kfd-post-reset-before-schedulers"
    else:
        sched_status = "unknown"
    restore_guard = ("amdgpu_in_reset(" in restore or "amdgpu_amdkfd_is_fed(" in restore)
    restore_status = ("reset-guard-present" if restore_guard and "-EAGAIN" in restore
                      else "no-reset-eagain-guard-seen" if not restore_guard
                      else "unknown")
    kiq_guard = "ring != &adev->gfx.kiq[0].ring" in mqd
    quantum = "CP_HQD_QUANTUM, QUANTUM_EN" in mqd
    return {
        "gpu_recover_preempt_lock_order": reset_order,
        "pci_error_preempt_lock_order": pci_order,
        "post_reset_scheduler_order": sched_status,
        "restore_queues_reset_guard": restore_status,
        "gfx8_kiq_quantum_exempt": kiq_guard if quantum else None,
        "unmap_uses_reset_domain_read_trylock": "down_read_trylock(" in unmap,
        "unmap_calls_fence_wait": "amdkfd_fence_wait_timeout(" in unmap,
        "classification": "source-only; not observed execution or patch acceptance",
    }


def read_sources(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    data, hashes = {}, {}
    for key, relpath in SOURCE_FILES.items():
        path = root / relpath
        if not path.is_file():
            raise ValueError("required exact source missing: " + str(path))
        raw = path.read_bytes()
        hashes[key] = hashlib.sha256(raw).hexdigest()
        data[key] = raw.decode("utf-8")
    return data, hashes


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--release-receipt", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    root = args.source.resolve(strict=True)
    if not root.is_dir():
        p.error("--source must be an extracted source tree")
    receipt_info = {"present": False, "source_root_matched": False,
                    "note": "a matching root path does not prove a source-to-module rebuild"}
    if args.release_receipt is not None:
        receipt = json.loads(args.release_receipt.read_text())
        receipt_root = receipt.get("source_root")
        if not receipt_root or Path(receipt_root).resolve() != root:
            p.error("release receipt root does not match selected source")
        receipt_info.update(present=True, source_root_matched=True,
                            release_archive_sha256=receipt.get("source_release_sha256"))
    try:
        source, sha = read_sources(root)
        findings = audit(source)
    except (UnicodeError, ValueError) as exc:
        p.error(str(exc))
    report = {"schema": 1, "mode": "cpu-only-source-reset-order-audit",
              "source_root": str(root), "release_receipt": receipt_info,
              "source_file_sha256": sha, "findings": findings,
              "gpu_executed": False,
              "caveats": [
                  "Source-order classification cannot prove compiled module byte identity",
                  "The first November quiesce failure may be independent of reset-lock ordering",
                  "A fix requires review and safe hardware validation of recovery",
                  "No change to kernel configuration, drivers, modules or KFD"
              ]}
    if args.out.exists():
        p.error("refuse to overwrite existing audit receipt")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(args.out.suffix + ".partial")
    tmp.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    tmp.replace(args.out)
    print(json.dumps({"out": str(args.out), "findings": findings}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
