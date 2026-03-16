import torch
import torch.nn as nn
import os

def test_native_determinism():
    # Disable MIOpen (CuDNN equivalent)
    torch.backends.cudnn.enabled = False
    
    torch.manual_seed(42)
    conv = nn.Conv2d(4, 64, 3, padding=1).cuda().float().eval()
    x = torch.randn(1, 4, 32, 32, device="cuda")
    
    with torch.no_grad():
        base = conv(x).clone()
        max_diff = 0
        for i in range(50):
            out = conv(x)
            diff = (base - out).abs().max().item()
            max_diff = max(max_diff, diff)
            
    print(f"MIOpen Disabled (Native Kernels): max_diff={max_diff:.6e} {'[NON-DET]' if max_diff > 1e-6 else '[DET]'}")

if __name__ == "__main__":
    test_native_determinism()
