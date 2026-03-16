#!/usr/bin/env python3
import torch
import torch.nn as nn
import time
import os
import sys

def test_conv_determinism(config_name, env_vars):
    # Set env vars
    for k, v in env_vars.items():
        os.environ[k] = v
        
    torch.manual_seed(42)
    # The specific failure case: Conv2d(64, 128, 3, stride=2, padding=1)
    conv = nn.Conv2d(64, 128, 3, stride=2, padding=1).cuda().float().eval()
    
    torch.manual_seed(123)
    x = torch.randn(1, 64, 64, 64, device="cuda")
    
    with torch.no_grad():
        # First pass
        out1 = conv(x).detach().clone().cpu()
        # Second pass
        out2 = conv(x).detach().clone().cpu()
        
    diff = (out1 - out2).abs().max().item()
    status = "DET" if diff < 1e-6 else "NON-DET"
    print(f"RESULT:{config_name}:{status}:diff={diff:.6e}")
    return diff < 1e-6

def main():
    if not torch.cuda.is_available():
        print("NO_CUDA")
        return

    configs = [
        ("Stock", {}),
        ("DetMode", {"MIOPEN_DEBUG_CONV_DET": "1"}),
        ("BypassDB", {"MIOPEN_DEBUG_DISABLE_FIND_DB": "1", "MIOPEN_FIND_ENFORCE": "3"}),
        ("NoGemm", {"MIOPEN_DEBUG_CONV_GEMM": "0"}),
        ("NoDirect", {"MIOPEN_DEBUG_CONV_DIRECT": "0"}),
        ("NoWinograd", {"MIOPEN_DEBUG_CONV_WINOGRAD": "0"}),
        ("NoFFT", {"MIOPEN_DEBUG_CONV_FFT": "0"}),
        ("Det+Bypass", {"MIOPEN_DEBUG_CONV_DET": "1", "MIOPEN_DEBUG_DISABLE_FIND_DB": "1", "MIOPEN_FIND_ENFORCE": "3"}),
    ]

    for name, env in configs:
        test_conv_determinism(name, env)

if __name__ == "__main__":
    main()
