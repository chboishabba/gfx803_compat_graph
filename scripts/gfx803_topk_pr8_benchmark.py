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


def _base(index: int) -> dict[str, object]:
    shape, k, dtype = CASES[index]
    return {"case": index, "shape": "x".join(map(str, shape)), "k": k, "dtype": dtype}


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
    args = parser.parse_args()
    if args.warmup < 0 or args.iterations < 1 or args.timeout < 1:
        parser.error("warmup must be nonnegative and iterations/timeout positive")
    if args.case is not None:
        print(json.dumps(_one(args.case, args.warmup, args.iterations), sort_keys=True), flush=True)
        return 0
    if args.out is None:
        parser.error("--out is required outside child mode")
    if args.out.exists():
        parser.error(f"refuse overwriting existing CSV: {args.out}")
    rows: list[dict[str, object]] = []
    # Large vocabulary and 1D paths can dispatch differently from the known
    # small-row fault paths, so preserve their evidence before router canaries.
    for index in (3, 4, 5, 6, 7, 8, 1, 2, 0):
        row = _base(index)
        command = [sys.executable, str(Path(__file__).resolve()), "--case", str(index),
                   "--warmup", str(args.warmup), "--iterations", str(args.iterations)]
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
            return 2
    return 0 if all(row["status"] == "ok" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
