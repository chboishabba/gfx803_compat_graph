#!/usr/bin/env python3
import torch
import torch.nn as nn
import os
import subprocess
import json
import re

def run_probe(env_vars):
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
            timeout=120
        )
        output = proc.stdout + proc.stderr
        
        # Enhanced solver extraction:
        # Looking for lines like: MIOpen(HIP): Info [MoveForward] Selected solver: <SolverName>
        # Or: MIOpen(HIP): Info [MoveForward] Find: <SolverName>
        solvers = re.findall(r"(?:Selected solver|Find): <([^>]+)>", output)
        solver = "/".join(list(set(solvers))) if solvers else "unknown"
        
        diff_match = re.search(r"DIFF:([\d.e+-]+)", output)
        diff = float(diff_match.group(1)) if diff_match else 1.0
        
        # Check if we saw Winograd in the logs at all
        saw_winograd = "Winograd" in output
        
        return solver, diff, saw_winograd, output
    except subprocess.TimeoutExpired:
        return "timeout", 1.0, False, ""
    except Exception as e:
        return f"error: {str(e)}", 1.0, False, ""

def main():
    if not torch.cuda.is_available():
        print("NO_CUDA")
        return

    test_configs = [
        {"name": "Stock", "env": {}},
        {"name": "NoWinograd", "env": {"MIOPEN_DEBUG_CONV_WINOGRAD": "0"}},
        {"name": "NoFFT", "env": {"MIOPEN_DEBUG_CONV_FFT": "0"}},
        {"name": "ForceWinograd", "env": {"MIOPEN_DEBUG_CONV_GEMM": "0", "MIOPEN_DEBUG_CONV_DIRECT": "0", "MIOPEN_DEBUG_CONV_FFT": "0"}},
    ]

    results = []
    print(f"{'Config':<15} | {'Solver(s)':<30} | {'Winograd?':<10} | {'Diff':<12} | {'Status'}")
    print("-" * 85)
    
    for config in test_configs:
        solver, diff, saw_w, full_log = run_probe(config["env"])
        status = "PASSED" if diff < 1e-6 else "FAILED"
        print(f"{config['name']:<15} | {solver:<30} | {str(saw_w):<10} | {diff:<12.6e} | {status}")
        results.append({
            "config": config["name"],
            "solver": solver,
            "saw_winograd": saw_w,
            "diff": diff,
            "status": status
        })

    print(f"\nPROBE_JSON:{json.dumps(results)}")

if __name__ == "__main__":
    main()
