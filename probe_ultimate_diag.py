import torch
import torch.nn as nn
import os
import json

def test_component(name, module, x, env):
    # Apply env
    for k, v in env.items():
        os.environ[k] = v
    
    # Try to set deterministic mode if requested
    if env.get("DET_MODE") == "1":
        torch.use_deterministic_algorithms(True)
    else:
        torch.use_deterministic_algorithms(False)
        
    module = module.cuda().float().eval()
    
    with torch.no_grad():
        base = module(x).clone()
        max_diff = 0
        for i in range(10):
            out = module(x)
            diff = (base - out).abs().max().item()
            max_diff = max(max_diff, diff)
            
    return max_diff

def main():
    torch.manual_seed(42)
    
    # Define components
    comp_1x1 = nn.Conv2d(128, 128, 1)
    x_1x1 = torch.randn(1, 128, 16, 16, device="cuda")
    
    comp_deconv = nn.ConvTranspose2d(256, 128, 4, stride=2, padding=1)
    x_deconv = torch.randn(1, 256, 8, 8, device="cuda")
    
    # For Einsum, we use a wrapper
    class EinsumWrapper(nn.Module):
        def forward(self, x):
            return torch.einsum("bhcn,bhcm->bhnm", x, x)
    comp_einsum = EinsumWrapper()
    x_einsum = torch.randn(1, 4, 256, 64, device="cuda")
    
    components = [
        ("1x1 Conv", comp_1x1, x_1x1),
        ("Deconv", comp_deconv, x_deconv),
        ("Einsum", comp_einsum, x_einsum),
    ]
    
    configs = [
        ("Stock", {"MIOPEN_LOG_LEVEL": "3"}),
        ("NoWinograd", {"MIOPEN_DEBUG_CONV_WINOGRAD": "0"}),
        ("NoWin+NoFFT", {"MIOPEN_DEBUG_CONV_WINOGRAD": "0", "MIOPEN_DEBUG_CONV_FFT": "0"}),
        ("NoWin+NoDirect", {"MIOPEN_DEBUG_CONV_WINOGRAD": "0", "MIOPEN_DEBUG_CONV_DIRECT": "0"}),
        ("NoWin+NoGEMM", {"MIOPEN_DEBUG_CONV_WINOGRAD": "0", "MIOPEN_DEBUG_CONV_GEMM": "0"}),
        ("DetMode", {"DET_MODE": "1", "CUBLAS_WORKSPACE_CONFIG": ":4096:8"}),
        ("Ultimate", {
            "MIOPEN_DEBUG_CONV_WINOGRAD": "0",
            "MIOPEN_DEBUG_CONV_FFT": "0",
            "MIOPEN_DEBUG_CONV_DET": "1",
            "DET_MODE": "1",
            "CUBLAS_WORKSPACE_CONFIG": ":4096:8"
        }),
    ]
    
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print(f"{'Config':20} | {'1x1 Conv':10} | {'Deconv':10} | {'Einsum':10}")
    print("-" * 60)
    
    for cname, cenv in configs:
        results = []
        for name, mod, x in components:
            diff = test_component(name, mod, x, cenv)
            results.append(diff)
        
        print(f"{cname:20} | {results[0]:.4e} | {results[1]:.4e} | {results[2]:.4e}")

if __name__ == "__main__":
    main()
