import torch
import torch.nn as nn
import os
import sys

# Ensure env vars are set before any CUDA calls
os.environ["MIOPEN_DEBUG_CONV_WINOGRAD"] = "0"
os.environ["MIOPEN_DEBUG_CONV_FFT"] = "0"

def check(name, conv, x):
    with torch.no_grad():
        o1 = conv(x).clone()
        o2 = conv(x).clone()
        diff = (o1 - o2).abs().max().item()
        print(f"{name:20}: diff={diff:.6e} {'[NON-DET]' if diff > 1e-6 else '[DET]'}")
    return diff

def main():
    print(f"Device: {torch.cuda.get_device_name(0)}")
    torch.manual_seed(42)
    
    # Test 1: 64->64 3x3
    print("--- Test 1 ---")
    c1 = nn.Conv2d(64, 64, 3, padding=1).cuda().float().eval()
    x1 = torch.randn(1, 64, 32, 32, device="cuda")
    check("c1 (64-64-3x3)", c1, x1)
    
    # Test 2: 128->128 1x1
    print("\n--- Test 2 ---")
    c2 = nn.Conv2d(128, 128, 1).cuda().float().eval()
    x2 = torch.randn(1, 128, 16, 16, device="cuda")
    check("c2 (128-128-1x1)", c2, x2)
    
    # Test 3: Repeat Test 1 with same instance
    print("\n--- Test 3 (Repeat 1) ---")
    check("c1 again", c1, x1)

if __name__ == "__main__":
    main()
