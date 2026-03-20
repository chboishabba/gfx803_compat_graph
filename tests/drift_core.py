import torch
import json
import time
import sys
import os

def run_repeated_conv_test(device="cuda", iters=100):
    torch.manual_seed(0)

    # Use a simple conv that mimics common workloads
    x = torch.randn(1, 64, 64, 64, device=device)
    conv = torch.nn.Conv2d(64, 64, 3, padding=1).to(device)

    # Warmup and get baseline
    baseline = conv(x).detach()

    drifts = []

    for i in range(iters):
        out = conv(x)
        drift = (out - baseline).abs().max().item()
        drifts.append(drift)

    return {
        "max_drift": max(drifts),
        "mean_drift": sum(drifts) / len(drifts) if drifts else 0.0,
        "first_drift_iter": next((i for i, d in enumerate(drifts) if d > 1e-6), None),
        "deterministic": all(d < 1e-6 for d in drifts)
    }


def collect_env():
    return {
        "rocm_version": os.environ.get("HSA_OVERRIDE_GFX_VERSION", "unknown"),  # Usually set outside
        "gfx_override": os.environ.get("HSA_OVERRIDE_GFX_VERSION"),
        "solver_flags": {
            "direct": os.environ.get("MIOPEN_DEBUG_CONV_DIRECT"),
            "gemm": os.environ.get("MIOPEN_DEBUG_CONV_GEMM"),
            "winograd": os.environ.get("MIOPEN_DEBUG_CONV_WINOGRAD"),
            "fft": os.environ.get("MIOPEN_DEBUG_CONV_FFT")
        }
    }


def main():
    if not torch.cuda.is_available():
        print("ERROR: HIP not available in this environment.", file=sys.stderr)
        sys.exit(1)

    result = run_repeated_conv_test()

    output = {
        "env": collect_env(),
        "test": "repeated_conv",
        "results": result
    }
    
    # Store solver directly in output for easy parsing out
    solver = "GEMM" if os.environ.get("MIOPEN_DEBUG_CONV_GEMM") == "1" else "DIRECT" if os.environ.get("MIOPEN_DEBUG_CONV_DIRECT") == "1" else "DEFAULT"
    output["env"]["solver"] = solver

    print("FINAL_JSON=" + json.dumps(output))

if __name__ == "__main__":
    main()
