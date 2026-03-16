import torch
import torch.nn as nn
import os

# Set known stable flags
os.environ["MIOPEN_DEBUG_CONV_WINOGRAD"] = "0"
os.environ["MIOPEN_DEBUG_CONV_FFT"] = "0"

def check(name, conv, x):
    with torch.no_grad():
        o1 = conv(x).clone()
        o2 = conv(x).clone()
        diff = (o1 - o2).abs().max().item()
        print(f"{name:20}: diff={diff:.6e}")
    return diff

def main():
    torch.manual_seed(42)
    
    c_1x1 = nn.Conv2d(128, 128, 1).cuda().float().eval()
    x_128 = torch.randn(1, 128, 16, 16, device="cuda")
    
    print("--- Phase 1: Fresh 1x1 ---")
    check("1x1 Initial", c_1x1, x_128)
    
    print("\n--- Phase 2: Triggering Kernel (ConvTranspose2d) ---")
    c_deconv = nn.ConvTranspose2d(256, 128, 4, stride=2, padding=1).cuda().float().eval()
    x_256 = torch.randn(1, 256, 8, 8, device="cuda")
    check("Deconv", c_deconv, x_256)
    
    print("\n--- Phase 3: Post-Trigger 1x1 ---")
    check("1x1 Post-Deconv", c_1x1, x_128)

if __name__ == "__main__":
    main()
