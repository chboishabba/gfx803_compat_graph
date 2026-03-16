import torch
import torch.nn as nn
import torch.nn.functional as F
import os

def check_det(name, fn, x):
    with torch.no_grad():
        base = fn(x.clone()).clone()
        max_diff = 0
        for i in range(20):
            out = fn(x.clone())
            diff = (base - out).abs().max().item()
            max_diff = max(max_diff, diff)
    print(f"{name:20}: max_diff={max_diff:.6e} {'[NON-DET]' if max_diff > 1e-6 else '[DET]'}")

def main():
    torch.use_deterministic_algorithms(True)
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    
    x = torch.randn(1, 128, 32, 32, device="cuda")
    
    print("--- Upsampling Probes ---")
    
    # 1. Bicubic (Often non-deterministic on older ROCm)
    check_det("Bicubic Interp", lambda t: F.interpolate(t, scale_factor=2, mode="bicubic", align_corners=False), x)
    
    # 2. Bilinear
    check_det("Bilinear Interp", lambda t: F.interpolate(t, scale_factor=2, mode="bilinear", align_corners=False), x)
    
    # 3. Nearest (Should be rock solid)
    check_det("Nearest Interp", lambda t: F.interpolate(t, scale_factor=2, mode="nearest"), x)
    
    # 4. ConvTranspose2d (Large Kernel)
    deconv = nn.ConvTranspose2d(128, 128, 4, stride=2, padding=1).cuda().eval()
    check_det("ConvTranspose2d", deconv, x)

if __name__ == "__main__":
    main()
