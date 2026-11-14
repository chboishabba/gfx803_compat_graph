#!/usr/bin/env python3
"""One-shot RX580 TopK incident reproducer: launched ONLY by explicit manual arm.

Unlike the historical benchmark's safe-host-gated entrypoint, this file
deliberately exposes its same case-4 _one() implementation to the operator
with a typed destructive-risk acknowledgement. Never import/execute it during
unit tests. No import of torch or device initialization before preflight.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

EXPECTED_LIBTORCH_SHA256 = "c1ad552aac76766b14ad78b993b5e3ee7a3b72c7fc48b7d72345516cf6fba7ff"
EXPECTED_OVERLAY = "/nix/store/vq1lgpc49im7qvvxgxabykyfs47l2ykb-gfx803-schaka101-torch-candidate-overlay/torch-site"
EXPECTED_ROCM_ROOT = "/nix/store/5dbvxcs7l4mvnj1cq3ybbkdm15jpvqr9-staged-rocm"
CASE = 4
SHAPE = (32, 151936)
K = 50
DTYPE = "float32"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fd:
        for block in iter(lambda: fd.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def preflight_overlay(overlay: Path, rocm: Path, *, enforce_original: bool = True) -> dict:
    if enforce_original and str(overlay) != EXPECTED_OVERLAY:
        raise ValueError("wrong incident-time Nix torch-site overlay")
    if enforce_original and str(rocm) != EXPECTED_ROCM_ROOT:
        raise ValueError("wrong incident-time staged ROCm root")
    lib = overlay / "torch/lib/libtorch_hip.so"
    if not lib.is_file() or not rocm.is_dir():
        raise ValueError("missing original libtorch_hip.so or staged ROCm root")
    actual = sha256(lib)
    if enforce_original and actual != EXPECTED_LIBTORCH_SHA256:
        raise ValueError(f"original libtorch_hip SHA mismatch: {actual}")
    return {"overlay": str(overlay), "rocm_root": str(rocm),
            "libtorch_hip": str(lib), "libtorch_hip_sha256": actual,
            "sha_matches_original": actual == EXPECTED_LIBTORCH_SHA256}


def emit(fd, event: str, **values) -> None:
    payload = {"event": event, "wall_time_ns": time.time_ns(),
               "monotonic_ns": time.monotonic_ns(), **values}
    fd.write(json.dumps(payload, sort_keys=True) + "\n")
    fd.flush()
    os.fsync(fd.fileno())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, default=Path(EXPECTED_OVERLAY))
    parser.add_argument("--rocm-root", type=Path, default=Path(EXPECTED_ROCM_ROOT))
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--arm-token", required=True,
                        help="exact value from the interactive launcher, never generated automatically")
    a = parser.parse_args()
    if a.arm_token != "MANUAL_ONE_SHOT_CASE4_ACKNOWLEDGED":
        parser.error("no valid manually armed one-shot token")
    if a.warmup != 10 or a.iterations != 50:
        parser.error("exact original reproducer requires warmup=10, iterations=50")
    if a.receipt.exists():
        parser.error("refuse receipt overwrite")
    if not a.benchmark.is_file():
        parser.error("historical benchmark source missing")
    try:
        original = preflight_overlay(a.overlay, a.rocm_root)
    except (OSError, ValueError) as e:
        parser.error(str(e))
    # Ensure torch is always imported from the exact incident Nix overlay,
    # not an incidental system wheel. LD_PRELOAD must already be inherited
    # from the operator's original launch environment.
    sys.path.insert(0, str(a.overlay))
    import torch
    expected_torch = a.overlay / "torch"
    actual_torch = Path(torch.__file__).resolve()
    if not actual_torch.is_relative_to(expected_torch.resolve()):
        parser.error(f"unexpected torch import: {actual_torch}")
    if torch.version.hip is None:
        parser.error("torch is not HIP-backed")
    original["torch_file"] = str(actual_torch)
    original["torch_version"] = torch.__version__
    original["hip_version"] = torch.version.hip
    original["ld_preload_present"] = bool(os.environ.get("LD_PRELOAD"))
    if not original["ld_preload_present"]:
        parser.error("original incident used a SGEMM shim preload; LD_PRELOAD absent")
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf-8", buffering=1) as fd:
        emit(fd, "pre_gpu_dispatch", case=CASE, shape=SHAPE, k=K,
             dtype=DTYPE, warmup=a.warmup, iterations=a.iterations,
             runtime=original, gpu_executed=False)
        # Run the very same _one() implementation that the historical
        # gfx803_topk_pr8_benchmark.py used. Importing its module never
        # enters its safe-host-guarded main().
        spec = importlib.util.spec_from_file_location("gfx803_historical_topk_bench", a.benchmark)
        if not spec or not spec.loader:
            raise RuntimeError("cannot import verified historical benchmark")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if mod.CASES[CASE] != (SHAPE, K, DTYPE):
            raise RuntimeError("historical benchmark case 4 contract changed")
        emit(fd, "one_shot_start", case=CASE, gpu_executed=True)
        result = mod._one(CASE, a.warmup, a.iterations)
        emit(fd, "one_shot_end", case=CASE, result=result,
             gpu_executed=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
