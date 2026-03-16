import torch
import torch.nn as nn
import os

def test_solver(name, env):
    # Apply env
    for k, v in env.items():
        os.environ[k] = v
        
    torch.manual_seed(42)
    conv = nn.Conv2d(4, 64, 3, padding=1).cuda().float().eval()
    x = torch.randn(1, 4, 32, 32, device="cuda")
    
    with torch.no_grad():
        base = conv(x).clone()
        max_diff = 0
        for i in range(10):
            out = conv(x)
            diff = (base - out).abs().max().item()
            max_diff = max(max_diff, diff)
            
    print(f"{name:15} | max_diff={max_diff:.6e} {'[NON-DET]' if max_diff > 1e-6 else '[DET]'}")

def main():
    torch.use_deterministic_algorithms(True)
    
    print(f"{'Solver Config':15} | Result")
    print("-" * 40)
    
    # Base flags already set in docker call, but we override here
    # 1. GEMM only
    test_solver("GEMM Only", {
        "MIOPEN_DEBUG_CONV_WINOGRAD": "0",
        "MIOPEN_DEBUG_CONV_FFT": "0",
        "MIOPEN_DEBUG_CONV_DIRECT": "0",
    })
    
    # 2. Direct only
    test_solver("Direct Only", {
        "MIOPEN_DEBUG_CONV_WINOGRAD": "0",
        "MIOPEN_DEBUG_CONV_FFT": "0",
        "MIOPEN_DEBUG_CONV_GEMM": "0",
    })
    
    # 3. Default (Winner picks)
    test_solver("Default", {
        "MIOPEN_DEBUG_CONV_WINOGRAD": "0",
        "MIOPEN_DEBUG_CONV_FFT": "0",
    })

if __name__ == "__main__":
    main()
