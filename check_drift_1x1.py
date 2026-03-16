import torch
import torch.nn as nn
import os

os.environ["MIOPEN_DEBUG_CONV_WINOGRAD"] = "0"
os.environ["MIOPEN_DEBUG_CONV_FFT"] = "0"

def main():
    torch.manual_seed(42)
    conv = nn.Conv2d(128, 128, 1).cuda().eval()
    x = torch.randn(1, 128, 16, 16, device="cuda")
    
    with torch.no_grad():
        base = conv(x).clone()
        print("Starting 500-batch drift check...")
        for i in range(500):
            out = conv(x)
            diff = (base - out).abs().max().item()
            if diff > 1e-6:
                print(f"Batch {i}: Diff {diff:.6e} !!!")
                # Once it breaks, it usually stays broken
                # Let's see if next one is also broken
                return
            if i % 100 == 0:
                print(f"  {i}...")
    print("Clean run! No drift detected in 500 batches.")

if __name__ == "__main__":
    main()
