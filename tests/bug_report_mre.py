import torch
import torch.nn as nn
import os
import sys
import argparse
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args()

    # Environment defaults. External runners may override these for profile comparisons.
    os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", "8.0.3")
    os.environ.setdefault("MIOPEN_DEBUG_CONV_WINOGRAD", "0")
    os.environ.setdefault("MIOPEN_DEBUG_CONV_FFT", "0")
    os.environ.setdefault("MIOPEN_DEBUG_CONV_DET", "1")
    os.environ.setdefault("MIOPEN_DEBUG_DISABLE_FIND_DB", "1")
    os.environ.setdefault("MIOPEN_FIND_ENFORCE", "3")
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    
    # Must use deterministic to reveal the stable drift
    torch.use_deterministic_algorithms(True)
    
    print(f"PyTorch: {torch.__version__}")
    
    if not torch.cuda.is_available():
        print("ERROR: HIP available: False. Check ROCm installation and KFD permissions.")
        sys.exit(1)
        
    print(f"Device: {torch.cuda.get_device_name(0)}")
    
    torch.manual_seed(42)
    conv = nn.Conv2d(4, 64, 3, padding=1).cuda().eval()
    x = torch.randn(1, 4, 32, 32, device="cuda")
    
    with torch.no_grad():
        base = conv(x).clone()
        print(f"Starting {args.iterations}-iteration stress test...")
        drifts = []
        for i in range(args.iterations):
            out = conv(x)
            diff = (base - out).abs().max().item()
            if diff > 1e-4:
                print(f"ITER {i:03}: DRIFT {diff:.6e}")
                drifts.append({"iter": i, "drift": diff})
            if i % 20 == 0:
                print(f"  {i}...")

    max_drift = max((item["drift"] for item in drifts), default=0.0)
    mean_drift = sum(item["drift"] for item in drifts) / len(drifts) if drifts else 0.0
    first_drift_iter = drifts[0]["iter"] if drifts else None
    status = "pass" if max_drift <= 1e-6 else "partial"
    payload = {
        "test": "bug_report_mre",
        "status": status,
        "device_name": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
        "iterations": args.iterations,
        "metrics": {
            "drift_count": len(drifts),
            "max_drift": max_drift,
            "mean_drift": mean_drift,
            "first_drift_iter": first_drift_iter,
        },
        "runtime": {
            "HSA_OVERRIDE_GFX_VERSION": os.environ.get("HSA_OVERRIDE_GFX_VERSION"),
            "MIOPEN_DEBUG_CONV_DIRECT": os.environ.get("MIOPEN_DEBUG_CONV_DIRECT"),
            "MIOPEN_DEBUG_CONV_GEMM": os.environ.get("MIOPEN_DEBUG_CONV_GEMM"),
            "MIOPEN_DEBUG_CONV_WINOGRAD": os.environ.get("MIOPEN_DEBUG_CONV_WINOGRAD"),
            "MIOPEN_DEBUG_CONV_FFT": os.environ.get("MIOPEN_DEBUG_CONV_FFT"),
            "MIOPEN_DEBUG_CONV_DET": os.environ.get("MIOPEN_DEBUG_CONV_DET"),
            "MIOPEN_FIND_ENFORCE": os.environ.get("MIOPEN_FIND_ENFORCE"),
        },
    }
    print("FINAL_JSON=" + json.dumps(payload))

if __name__ == "__main__":
    main()
