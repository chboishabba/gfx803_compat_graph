#!/usr/bin/env python3
"""Isolated gfx803 PyTorch operator conformance assay (candidate only).

Each case runs in its own process. A fault is a failed/unassayed operator,
never a GPU-training or Cachix-release pass. No package is modified.
Run with the exact candidate Nix venv Python, not host Python.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Deliberately finite, audit-able case registry. Expand by real model traces.
CASES = {
    "tensor_copy": "core",
    "layernorm_2x64x384": "normalization",
    "softmax_2x4": "reduction",
    "matmul_128x384x1152": "linear",
    "batched_matmul_2x64x384": "linear",
    "sort_2x4": "selection",
    "topk_2x4_k2": "selection",
    "gather_2x4": "indexing",
    "scatter_add_2x4": "indexing",
    "embedding_64x384": "indexing",
    "conv2d_small": "nn",
    "adamw_384": "optimizer",
}
# The original fault is a GPU VM page fault, not an ordinary Python exception.
KNOWN_FAULTS = frozenset({"topk_2x4_k2"})
STATUSES = frozenset({"pass", "fail", "unsupported", "fault", "timeout", "unassayed"})


def verdict(report: dict) -> dict:
    """Pure, offline promotion-resistant summary."""
    cases = report.get("cases", {})
    if set(cases) != set(CASES):
        raise ValueError("Every registered case must have a status")
    counts = {k: 0 for k in sorted(STATUSES)}
    for name, row in cases.items():
        status = row.get("status")
        if name not in CASES or status not in counts:
            raise ValueError("Unknown case/status")
        counts[status] += 1
    return {
        "counts": counts,
        "all_cases_pass": counts["pass"] == len(CASES),
        "training_admitted": False,
        "cachix_release_admitted": False,
        "claim": "isolated selected operator evidence only; not full torch coverage",
    }


def compare(a, b, torch, *, atol: float = 1e-4, rtol: float = 1e-4) -> dict:
    a = a.detach().cpu()
    b = b.detach().cpu()
    same_shape = a.shape == b.shape
    if not same_shape:
        return {"passed": False, "reason": "shape mismatch"}
    finite = bool(torch.isfinite(a).all() and torch.isfinite(b).all())
    if not finite:
        return {"passed": False, "reason": "nonfinite"}
    diff = (a - b).abs()
    passed = bool(torch.allclose(a, b, atol=atol, rtol=rtol))
    return {
        "passed": passed,
        "max_abs_diff": float(diff.max()) if diff.numel() else 0.0,
        "shape": list(a.shape),
        "atol": atol, "rtol": rtol,
    }


def exercise(name: str, torch) -> dict:
    """Paired CPU/HIP workload; compare forward, repeat, and gradient."""
    # All inputs originate on CPU and are copied; no GPU RNG ambiguity.
    torch.manual_seed(803)
    def rand(*shape):
        return torch.randn(*shape, dtype=torch.float32)
    leaves = []
    def track(tensor):
        leaves.append(tensor)
        return tensor
    def run(device):
        if name == "tensor_copy":
            x = track(rand(2, 64, 384).to(device).requires_grad_())
            return x.contiguous().transpose(1, 2).contiguous().square().sum()
        if name == "layernorm_2x64x384":
            x = track(rand(2, 64, 384).to(device).requires_grad_())
            return torch.nn.functional.layer_norm(x, (384,)).square().mean()
        if name == "softmax_2x4":
            x = track(rand(2, 4).to(device).requires_grad_())
            return torch.softmax(x, -1).square().sum()
        if name == "matmul_128x384x1152":
            x = track(rand(128, 384).to(device).requires_grad_())
            w = rand(384, 1152).to(device)
            return (x @ w).square().mean()
        if name == "batched_matmul_2x64x384":
            x = track(rand(2, 64, 384).to(device).requires_grad_())
            y = rand(2, 384, 64).to(device)
            return torch.bmm(x, y).square().mean()
        if name in ("sort_2x4", "topk_2x4_k2"):
            # Deliberately unequal values: topk tie-order is not specified.
            x = track(torch.tensor([[0.1, 0.4, -0.2, 0.7],
                              [0.9, -0.6, 0.3, 0.2]], dtype=torch.float32,
                             device=device).requires_grad_())
            if name == "sort_2x4":
                y, idx = torch.sort(x, dim=-1, descending=True)
                values = y[:, :2]
                indices = idx[:, :2]
            else:
                values, indices = torch.topk(x, 2, dim=-1)
            return values.square().sum(), indices
        if name == "gather_2x4":
            x = track(rand(2, 4).to(device).requires_grad_())
            idx = torch.tensor([[3, 1], [0, 2]], device=device)
            return torch.gather(x, 1, idx).square().sum()
        if name == "scatter_add_2x4":
            x = track(rand(2, 4).to(device).requires_grad_())
            idx = torch.tensor([[0, 1, 0, 1], [1, 0, 1, 0]], device=device)
            return torch.zeros_like(x).scatter_add(1, idx, x).square().sum()
        if name == "embedding_64x384":
            weight = track(rand(64, 384).to(device).requires_grad_())
            idx = torch.tensor([1, 7, 2, 7], dtype=torch.long, device=device)
            return torch.nn.functional.embedding(idx, weight).square().sum()
        if name == "conv2d_small":
            x = track(rand(1, 2, 8, 8).to(device).requires_grad_())
            w = rand(4, 2, 3, 3).to(device)
            return torch.nn.functional.conv2d(x, w, padding=1).square().mean()
        if name == "adamw_384":
            x = track(rand(384).to(device).requires_grad_())
            opt = torch.optim.AdamW([x], lr=1e-3, foreach=False)
            loss = x.square().sum()
            loss.backward()
            grad = x.grad.detach().clone()
            opt.step()
            return x.detach().clone(), grad
        raise ValueError("Unknown case: " + name)

    def once(device):
        # Frozen identical inputs across CPU, GPU, and GPU-repeat calls.
        torch.manual_seed(803)
        leaves.clear()
        out = run(device)
        if name == "adamw_384":
            return {"forward": out[0], "grad": out[1]}
        if isinstance(out, tuple):
            scalar, idx = out
        else:
            scalar, idx = out, None
        # The paired run returns the first watched differentiable leaf gradient.
        # Separate independent backward operator assay is below.
        scalar.backward()
        if len(leaves) != 1 or leaves[0].grad is None:
            raise RuntimeError("expected exactly one differentiable input leaf")
        return {"forward": scalar.detach(), "indices": idx,
                "grad": leaves[0].grad.detach().clone()}

    cpu = once("cpu")
    gpu = once("cuda")
    torch.cuda.synchronize()
    gpu_repeat = once("cuda")
    torch.cuda.synchronize()
    fwd = compare(cpu["forward"], gpu["forward"], torch)
    rep = compare(gpu["forward"], gpu_repeat["forward"], torch, atol=1e-6, rtol=1e-6)
    result = {"forward": fwd, "repeat": rep}
    # Non-selector cases deliberately return ``None`` for indices.  Checking
    # only key presence would turn every such otherwise-valid assay into a
    # supervisor fault before its numerical result could be recorded.
    if cpu.get("indices") is not None:
        idx_equal = bool(torch.equal(cpu["indices"].cpu(), gpu["indices"].cpu()))
        result["indices_equal"] = idx_equal
    result["gradient"] = compare(cpu["grad"], gpu["grad"], torch)
    result["passed"] = all(x["passed"] for x in (fwd, rep)) and (
        result.get("indices_equal", True)) and result.get("gradient", {"passed": True})["passed"]
    return result


def worker(case: str, expected_root: str) -> int:
    import torch
    report = {"case": case, "source": "physical isolated torch/HIP candidate"}
    try:
        if not torch.version.hip or not torch.cuda.is_available():
            raise RuntimeError("HIP unavailable")
        gpu = torch.cuda.get_device_properties(0)
        arch = getattr(gpu, "gcnArchName", None) or getattr(gpu, "gcn_arch_name", None)
        if not arch or not str(arch).startswith("gfx803"):
            raise RuntimeError("Not an actual gfx803 device: " + repr(arch))
        # A real GPU operation forces lazy ROCm library loading.
        torch.cuda.synchronize()
        maps = Path("/proc/self/maps").read_text()
        runtime_paths = sorted(set(
            part for line in maps.splitlines()
            if len(fields := line.split()) >= 6
            for part in [fields[-1]]
            if any(lib in os.path.basename(part) for lib in
                   ("libamdhip64", "librocblas", "libhsa-runtime64", "libMIOpen", "libhipblas"))
        ))
        if not runtime_paths or any(
                not os.path.realpath(path).startswith(os.path.realpath(expected_root) + "/")
                for path in runtime_paths):
            raise RuntimeError("Mixed or absent candidate ROCm runtime: " + repr(runtime_paths))
        report.update({"torch_version": torch.__version__, "torch_hip": torch.version.hip,
                       "architecture": str(arch), "runtime_mappings": runtime_paths})
        result = exercise(case, torch)
        report["checks"] = result
        report["status"] = "pass" if result["passed"] else "fail"
    except (RuntimeError, NotImplementedError) as exc:
        report["status"] = "unsupported" if "not implemented" in str(exc).lower() else "fail"
        report["error"] = repr(exc)
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if report["status"] == "pass" else 1


def atomically_write(path: Path, data: dict):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def run(args) -> int:
    out = args.out.resolve()
    if out.exists():
        raise SystemExit("Choose fresh --out: refuse overwriting retained receipts")
    if not args.rocm_root.is_dir() or not str(args.rocm_root.resolve()).startswith("/nix/store/"):
        raise SystemExit("--rocm-root must be the selected imported Nix runtime")
    out.mkdir(parents=True)
    matrix = {"schema": 1, "candidate_rocm_root": str(args.rocm_root.resolve()),
              "python": sys.executable, "known_faults_enabled": args.include_known_faults,
              "cases": {name: {"status": "unassayed", "family": family}
                        for name, family in CASES.items()}}
    atomically_write(out / "matrix.json", matrix)
    for name in CASES:
        if name in KNOWN_FAULTS and not args.include_known_faults:
            matrix["cases"][name]["reason"] = "known gfx803 GPU VM fault; requires explicit opt-in"
            atomically_write(out / "matrix.json", matrix)
            continue
        command = [sys.executable, str(Path(__file__).resolve()), "--worker-case", name,
                   "--rocm-root", str(args.rocm_root.resolve())]
        start = time.monotonic()
        try:
            done = subprocess.run(command, capture_output=True, text=True,
                                  timeout=args.timeout, check=False,
                                  env={**os.environ, "PYTHONNOUSERSITE": "1"})
            row = json.loads(done.stdout.strip().splitlines()[-1])
            status = row.get("status")
            if status not in ("pass", "fail", "unsupported"):
                raise ValueError("unexpected child status")
            if done.returncode != (0 if status == "pass" else 1):
                raise ValueError("inconsistent worker status/exit")
        except subprocess.TimeoutExpired as exc:
            status = "timeout"
            row = {"error": repr(exc)}
            done = None
        except (IndexError, ValueError, json.JSONDecodeError) as exc:
            status = "fault"
            row = {"error": str(exc)}
        if done is not None:
            (out / (name + ".stderr.txt")).write_text(done.stderr)
            if done.returncode not in (0, 1):
                status = "fault"
                row["signal_or_exit_code"] = done.returncode
        matrix["cases"][name].update({"status": status, "elapsed_seconds": round(
            time.monotonic() - start, 3), "receipt": row})
        atomically_write(out / "matrix.json", matrix)
        if status in ("fault", "timeout") and not args.continue_after_fault:
            matrix["stopped_after_fault"] = name
            break
    matrix["summary"] = verdict(matrix)
    atomically_write(out / "matrix.json", matrix)
    print(json.dumps(matrix["summary"], indent=2))
    return 0 if matrix["summary"]["all_cases_pass"] else 2


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path)
    p.add_argument("--rocm-root", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--include-known-faults", action="store_true")
    p.add_argument("--continue-after-fault", action="store_true")
    p.add_argument("--worker-case", choices=sorted(CASES))
    args = p.parse_args()
    if args.timeout < 1 or not args.rocm_root.is_absolute():
        p.error("positive timeout and absolute ROCm root required")
    if args.worker_case:
        return worker(args.worker_case, str(args.rocm_root.resolve()))
    if args.out is None:
        p.error("--out is required for supervisor")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
