import torch
import torch.nn as nn
import os
import random

def poison_state():
    print("Launching 5000 random convs (High intensity)...")
    for i in range(5000):
        # Variety of shapes and types
        in_c = random.randint(16, 256)
        out_c = random.randint(16, 256)
        k = random.choice([1, 3, 5])
        s = random.choice([1, 2])
        try:
            conv = nn.Conv2d(in_c, out_c, k, stride=s, padding=k//2).cuda().eval()
            x = torch.randn(1, in_c, 32, 32, device="cuda")
            with torch.no_grad():
                conv(x)
        except: pass
        if i % 1000 == 0:
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
    c_1x1 = nn.Conv2d(128, 128, 1).cuda().eval()
    x_1x1 = torch.randn(1, 128, 16, 16, device="cuda")
    
    poison_state()
    
    diff_poisoned = test_component(c_1x1, x_1x1)
    print(f"Post-poison diff: {diff_poisoned:.4e}")

if __name__ == "__main__":
    main()
