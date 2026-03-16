import torch
import torch.nn as nn
import os
import random

def poison_state():
    print("Launching 1000 random convs to stress MIOpen state...")
    for i in range(1000):
        in_c = random.choice([32, 64, 128])
        out_c = random.choice([32, 64, 128])
        k = random.choice([1, 3])
        s = random.choice([1, 2])
        conv = nn.Conv2d(in_c, out_c, k, stride=s, padding=k//2).cuda().eval()
        x = torch.randn(1, in_c, 32, 32, device="cuda")
        with torch.no_grad():
            conv(x)
        if i % 200 == 0:
            print(f"  {i}...")

def test_component(module, x):
    with torch.no_grad():
        base = module(x).clone()
        max_diff = 0
        for i in range(10):
            out = module(x)
            diff = (base - out).abs().max().item()
            max_diff = max(max_diff, diff)
    return max_diff

def main():
    os.environ["MIOPEN_DEBUG_CONV_WINOGRAD"] = "0"
    os.environ["MIOPEN_DEBUG_CONV_FFT"] = "0"

    torch.manual_seed(42)
    
    comp_1x1 = nn.Conv2d(128, 128, 1).cuda().eval()
    x_1x1 = torch.randn(1, 128, 16, 16, device="cuda")
    
    comp_deconv = nn.ConvTranspose2d(256, 128, 4, stride=2, padding=1).cuda().eval()
    x_deconv = torch.randn(1, 256, 8, 8, device="cuda")
    
    print("Pre-poison check:")
    print(f"  1x1: {test_component(comp_1x1, x_1x1):.4e}")
    print(f"  Deconv: {test_component(comp_deconv, x_deconv):.4e}")
    
    poison_state()
    
    print("\nPost-poison check:")
    print(f"  1x1: {test_component(comp_1x1, x_1x1):.4e}")
    print(f"  Deconv: {test_component(comp_deconv, x_deconv):.4e}")

if __name__ == "__main__":
    main()
