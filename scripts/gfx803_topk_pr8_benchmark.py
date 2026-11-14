#!/usr/bin/env python3
"""Fault-contained TopK A/B benchmark for Schaka's gfx803 PR #8.

Each case is a separate process.  The parent writes a CSV after every child
so that a known selection-kernel fault retains all earlier large-row results.
This belongs to the local compatibility graph, not the upstream patch PR.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

CASES = (
    ((2, 4), 2, "float32"),
    ((2048, 64), 8, "float32"),
    ((2048, 128), 8, "float16"),
    ((1, 151936), 50, "float32"),
    ((32, 151936), 50, "float32"),
    ((32, 151936), 50, "float16"),
    ((1_000_000,), 10, "float32"),
    ((1_000_000,), 1000, "float32"),
    ((16_000_000,), 100, "float32"),
)
FIELDS = ("case", "shape", "k", "dtype", "status", "median_ms",
          "min_ms", "values_ok", "indices_ok", "torch", "hip", "arch", "error")
# Preserve the previous case IDs/order for evidence, but skip historically
# faulting ones by default. A fresh Python process is NOT GPU fault isolation;
# after an unexpected failure we must stop without any health-check dispatch.
ORDER = (3, 4, 5, 6, 7, 8, 1, 2, 0)
# Confirmed historic faults (0/1 unpatched, 4 pre-review). Never run by default.
# Process isolation is not GPU isolation: case 4 wedged the display RX 580.
HAZARDOUS_CASES = frozenset((0, 1, 4))
SAFE_HOST_FIELDS = ("non_display_gpu", "out_of_band_management",
                    "durable_external_logging", "independent_power_recovery")


def _base(index: int) -> dict[str, object]:
    shape, k, dtype = CASES[index]
    return {"case": index, "shape": "x".join(map(str, shape)), "k": k, "dtype": dtype}


def planned_cases(skipped: set[int], *, allow_hazardous: bool = False) -> tuple[int, ...]:
    """Fail closed for known GPU-wedging cases unless independently authorized."""
    unknown = skipped.difference(range(len(CASES)))
    if unknown:
        raise ValueError(f"unknown case IDs: {sorted(unknown)}")
    excluded = skipped | (set() if allow_hazardous else HAZARDOUS_CASES)
    return tuple(index for index in ORDER if index not in excluded)


def validate_safe_host_receipt(path: Path) -> dict:
    """Validate operator attestation, NOT physical proof of safe recovery."""
    try:
        receipt = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable safe-host receipt: {exc}") from exc
    if (not isinstance(receipt, dict) or receipt.get("schema") != 1 or
            not all(receipt.get(key) is True for key in SAFE_HOST_FIELDS)):
        raise ValueError("safe-host receipt must attest all four recovery prerequisites")
    return receipt


def _one(index: int, warmup: int, iterations: int) -> dict[str, object]:
    import torch

    shape, k, dtype = CASES[index]
    if not torch.version.hip or not torch.cuda.is_available():
        raise RuntimeError("HIP GPU unavailable")
    arch = str(torch.cuda.get_device_properties(0).gcnArchName)
    if not arch.startswith("gfx803"):
        raise RuntimeError(f"gfx803 hardware required: {arch}")
    torch.manual_seed(0)
    cpu = torch.randn(shape, dtype=getattr(torch, dtype))
    gpu = cpu.cuda()
    values, indices = torch.topk(gpu, k, dim=-1)
    torch.cuda.synchronize()
    values, indices = values.cpu(), indices.cpu()
    expected = torch.topk(cpu, k, dim=-1).values
    values_ok = bool(torch.equal(torch.sort(values, dim=-1).values,
                                 torch.sort(expected, dim=-1).values))
    gathered_ok = bool(torch.equal(torch.gather(cpu, -1, indices), values))
    distinct_ok = bool(indices.sort(dim=-1).values.diff(dim=-1).ne(0).all())
    for _ in range(warmup):
        torch.topk(gpu, k, dim=-1)
    torch.cuda.synchronize()
    times = []
    for _ in range(iterations):
        start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        start.record()
        torch.topk(gpu, k, dim=-1)
        end.record()
        end.synchronize()
        times.append(start.elapsed_time(end))
    times.sort()
    return {"median_ms": round(times[len(times) // 2], 4), "min_ms": round(times[0], 4),
            "values_ok": values_ok, "indices_ok": gathered_ok and distinct_ok,
            "torch": torch.__version__, "hip": torch.version.hip, "arch": arch}


def _healthcheck() -> dict[str, object]:
    """Minimal post-fault HIP check, intentionally in its own interpreter."""
    import torch

    if not torch.version.hip or not torch.cuda.is_available():
        raise RuntimeError("HIP GPU unavailable after benchmark child failure")
    x = torch.arange(4096, device="cuda", dtype=torch.float32).reshape(64, 64)
    value = float((x @ x.T).sum().cpu())
    return {"arch": str(torch.cuda.get_device_properties(0).gcnArchName),
            "checksum": value}


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    with partial.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, restval="")
        writer.writeheader()
        writer.writerows(rows)
    partial.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--case", type=int, choices=range(len(CASES)))
    parser.add_argument("--healthcheck", action="store_true",
                        help="run a small fresh-process HIP health check")
    parser.add_argument("--skip-case", type=int, choices=range(len(CASES)), action="append",
                        default=[], help="record a known fault without executing it")
    parser.add_argument("--recover-after-fault", action="store_true",
                        help="DEPRECATED/REFUSED: a GPU health check cannot prove recovery")
    parser.add_argument("--enable-known-fault-cases", action="store_true",
                        help="opt in to cases 0/1/4 ONLY on independently recoverable hardware")
    parser.add_argument("--safe-host-receipt", type=Path,
                        help="operator-attested host eligibility JSON; no independent verification")
    args = parser.parse_args()
    if args.warmup < 0 or args.iterations < 1 or args.timeout < 1:
        parser.error("warmup must be nonnegative and iterations/timeout positive")
    if args.recover_after_fault:
        parser.error("automatic healthcheck/continuation after a GPU hang is unsafe")
    if args.enable_known_fault_cases:
        if args.safe_host_receipt is None:
            parser.error("--enable-known-fault-cases requires --safe-host-receipt")
        try:
            validate_safe_host_receipt(args.safe_host_receipt)
        except ValueError as exc:
            parser.error(str(exc))
    if args.healthcheck:
        if not args.enable_known_fault_cases:
            parser.error("standalone HIP healthcheck requires safe-host authorization")
        if args.case is not None:
            parser.error("--healthcheck cannot be combined with --case")
        print(json.dumps(_healthcheck(), sort_keys=True), flush=True)
        return 0
    if args.case is not None:
        if args.case in HAZARDOUS_CASES and not args.enable_known_fault_cases:
            parser.error("known-fault case requires an independently recoverable safe host")
        print(json.dumps(_one(args.case, args.warmup, args.iterations), sort_keys=True), flush=True)
        return 0
    if args.out is None:
        parser.error("--out is required outside child mode")
    if args.out.exists():
        parser.error(f"refuse overwriting existing CSV: {args.out}")
    rows: list[dict[str, object]] = []
    skipped = set(args.skip_case)
    if not args.enable_known_fault_cases:
        skipped.update(HAZARDOUS_CASES)
    try:
        scheduled = planned_cases(skipped, allow_hazardous=args.enable_known_fault_cases)
    except ValueError as error:
        parser.error(str(error))
    # Write known-fault rows up front: they are evidence, not successful tests.
    for index in ORDER:
        if index in skipped:
            row = _base(index)
            row.update(status="known-fault-skip" if index in HAZARDOUS_CASES else "operator-skip",
                       error="withheld; not an executed or passing GPU benchmark")
            rows.append(row)
    _write(args.out, rows)
    for index in scheduled:
        row = _base(index)
        command = [sys.executable, str(Path(__file__).resolve()), "--case", str(index),
                   "--warmup", str(args.warmup), "--iterations", str(args.iterations)]
        if args.enable_known_fault_cases:
            command.extend(["--enable-known-fault-cases", "--safe-host-receipt",
                            str(args.safe_host_receipt)])
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
            if result.returncode == 0:
                receipt = json.loads(result.stdout.strip().splitlines()[-1])
                row.update(receipt)
                row["status"] = "ok" if row["values_ok"] and row["indices_ok"] else "wrong-result"
            else:
                row.update(status=f"exit-{result.returncode}",
                           error=(result.stderr.strip().splitlines() or [""])[-1][:240])
        except subprocess.TimeoutExpired:
            row.update(status="timeout", error="child exceeded timeout")
        _write(args.out, rows + [row])
        rows.append(row)
        print(f"case {index}: {row['status']}", flush=True)
        if row["status"] in ("timeout",) or str(row["status"]).startswith("exit-"):
            # A different Python process cannot repair or certify a wedged GPU.
            return 2
    return 0 if all(row["status"] == "ok" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
