import torch
import torch.nn as nn
import os

def test(name, env):
    # Set env vars
    for k, v in env.items():
        os.environ[k] = v
    
    torch.manual_seed(42)
    # 1x1 Conv often uses special GEMM or Direct implementations
    conv = nn.Conv2d(128, 128, 1).cuda().float().eval()
    
    # We use a fixed input
    torch.manual_seed(99)
    x = torch.randn(1, 128, 16, 16, device="cuda")
    
    with torch.no_grad():
        # First run
        o1 = conv(x).clone()
        # Second run
        o2 = conv(x).clone()
        
    diff = (o1 - o2).abs().max().item()
    print(f"{name:15}: diff={diff:.6e} {'[NON-DET]' if diff > 1e-6 else '[DET]'}")

if __name__ == "__main__":
    configs = [
        ("Stock", {}),
        ("NoWinograd", {"MIOPEN_DEBUG_CONV_WINOGRAD": "0"}),
        ("NoFFT", {"MIOPEN_DEBUG_CONV_FFT": "0"}),
        ("NoDirect", {"MIOPEN_DEBUG_CONV_DIRECT": "0"}),
        ("NoGEMM", {"MIOPEN_DEBUG_CONV_GEMM": "0"}),
        ("DetOnly", {"MIOPEN_DEBUG_CONV_DET": "1"}),
        ("AllSafe", {"MIOPEN_DEBUG_CONV_WINOGRAD": "0", "MIOPEN_DEBUG_CONV_FFT": "0", "MIOPEN_DEBUG_CONV_DET": "1"}),
    ]
    
    print(f"Device: {torch.cuda.get_device_name(0)}")
    for name, env in configs:
        test(name, env)
