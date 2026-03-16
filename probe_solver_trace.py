#!/usr/bin/env python3
import torch
import torch.nn as nn
import os
import subprocess
import json
import re

def run_probe(env_vars):
    # We'll run a separate process to avoid env var contamination in the main process
    # and to easily capture stderr where MIOpen logs usually go.
    
    script = """
import torch
import torch.nn as nn
import os
torch.manual_seed(42)
conv = nn.Conv2d(64, 128, 3, stride=2, padding=1).cuda().float().eval()
x = torch.randn(1, 64, 64, 64, device="cuda")
with torch.no_grad():
    out1 = conv(x).cpu()
    out2 = conv(x).cpu()
diff = (out1 - out2).abs().max().item()
print(f"DIFF:{diff}")
"""
    
    env = os.environ.copy()
    env.update(env_vars)
    env["MIOPEN_LOG_LEVEL"] = "3"
    
    try:
        proc = subprocess.run(
            ["python3", "-c", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = proc.stdout + proc.stderr
        
        # Look for the selected solver in logs
        # Pattern usually: MIOpen(HIP): Info [MoveForward] Selected solver: <SolverName>
        solver_match = re.search(r"Selected solver: <([^>]+)>", output)
        solver = solver_match.group(1) if solver_match else "unknown"
        
        diff_match = re.search(r"DIFF:([\d.e+-]+)", output)
        diff = float(diff_match.group(1)) if diff_match else 1.0
        
        return solver, diff, output
    except Exception as e:
        return f"error: {str(e)}", 1.0, ""

def main():
    if not torch.cuda.is_available():
        print("NO_CUDA")
        return

    test_configs = [
        {"name": "Stock", "env": {}},
        {"name": "NoGemm", "env": {"MIOPEN_DEBUG_CONV_GEMM": "0"}},
        {"name": "NoDirect", "env": {"MIOPEN_DEBUG_CONV_DIRECT": "0"}},
        {"name": "NoWinograd", "env": {"MIOPEN_DEBUG_CONV_WINOGRAD": "0"}},
        {"name": "NoFFT", "env": {"MIOPEN_DEBUG_CONV_FFT": "0"}},
        {"name": "Exhaustive", "env": {"MIOPEN_FIND_ENFORCE": "4"}},
    ]

    results = []
    print(f"{'Config':<15} | {'Solver':<20} | {'Diff':<12} | {'Status'}")
    print("-" * 60)
    
    for config in test_configs:
        solver, diff, full_log = run_probe(config["env"])
        status = "PASSED" if diff < 1e-6 else "FAILED"
        print(f"{config['name']:<15} | {solver:<20} | {diff:<12.6e} | {status}")
        results.append({
            "config": config["name"],
            "solver": solver,
            "diff": diff,
            "status": status
        })

    print(f"\nPROBE_JSON:{json.dumps(results)}")

if __name__ == "__main__":
    main()
