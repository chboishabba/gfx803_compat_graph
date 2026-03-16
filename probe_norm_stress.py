import torch
import torch.nn as nn
import os

def check_det(name, fn, x):
    with torch.no_grad():
        base = fn(x.clone()).clone()
        max_diff = 0
        for i in range(50): # Higher stress
            out = fn(x.clone())
            diff = (base - out).abs().max().item()
            max_diff = max(max_diff, diff)
    print(f"{name:30}: max_diff={max_diff:.6e} {'[NON-DET]' if max_diff > 1e-6 else '[DET]'}")

def main():
    torch.use_deterministic_algorithms(True)
    
    # Stressing GroupNorm with various channel configurations
    print("--- Normalization Stress Probe ---")
    
    # Typical Diffusion Bottleneck (512+ channels)
    x512 = torch.randn(1, 512, 16, 16, device="cuda")
    gn512 = nn.GroupNorm(32, 512).cuda().eval()
    check_det("GroupNorm(32, 512)", gn512, x512)
    
    # Large Resolution
    x128_large = torch.randn(1, 128, 128, 128, device="cuda")
    gn128 = nn.GroupNorm(32, 128).cuda().eval()
    check_det("GroupNorm(32, 128) SmallRes", gn128, x128_large)

    # LayerNorm (sometimes used in attention)
    ln = nn.LayerNorm([128, 32, 32]).cuda().eval()
    x128 = torch.randn(1, 128, 32, 32, device="cuda")
    check_det("LayerNorm", ln, x128)

if __name__ == "__main__":
    main()
