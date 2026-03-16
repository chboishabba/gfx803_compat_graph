import torch
import torch.nn as nn
import os

os.environ["MIOPEN_DEBUG_CONV_WINOGRAD"] = "0"
os.environ["MIOPEN_DEBUG_CONV_FFT"] = "0"
os.environ["MIOPEN_DEBUG_CONV_DET"] = "1"
os.environ["MIOPEN_DEBUG_DISABLE_FIND_DB"] = "1"
os.environ["MIOPEN_FIND_ENFORCE"] = "3"
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

def main():
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(42)
    
    # Exactly what MiniUNet does for 'inp'
    conv = nn.Conv2d(4, 64, 3, padding=1).cuda().float().eval()
    x = torch.randn(1, 4, 32, 32, device="cuda")
    
    with torch.no_grad():
        base = conv(x).clone()
        print("Starting 100-run check on 4->64 3x3 Conv...")
        for i in range(100):
            out = conv(x)
            diff = (base - out).abs().max().item()
            if diff > 0:
                print(f"Run {i}: Diff {diff:.6e} !!!")
                # Don't return, let's see if it's every run
            if i % 20 == 0:
                print(f"  {i}...")
    
if __name__ == "__main__":
    main()
