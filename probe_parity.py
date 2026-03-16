#!/usr/bin/env python3
import torch
import torch.nn as nn
import os
import json

def test_conv_vs_cpu(env_vars):
    # Set env vars
    for k, v in env_vars.items():
        os.environ[k] = v
        
    torch.manual_seed(42)
    # The problematic layer: Conv2d(64, 128, 3, stride=2, padding=1)
    # Using a fixed seed for weight initialization
    conv_gpu = nn.Conv2d(64, 128, 3, stride=2, padding=1).cuda().float()
    conv_cpu = nn.Conv2d(64, 128, 3, stride=2, padding=1).cpu().float()
    
    # Copy weights exactly
    conv_cpu.load_state_dict(conv_gpu.state_dict())
    
    conv_gpu.eval()
    conv_cpu.eval()
    
    torch.manual_seed(123)
    x_cpu = torch.randn(1, 64, 64, 64, dtype=torch.float32)
    x_gpu = x_cpu.detach().clone().cuda()
    
    with torch.no_grad():
        # CPU Reference (Ground Truth)
        out_cpu = conv_cpu(x_cpu)
        
        # GPU Run 1
        out_gpu1 = conv_gpu(x_gpu).detach().clone().cpu()
        # GPU Run 2
        out_gpu2 = conv_gpu(x_gpu).detach().clone().cpu()
        
    # Stats
    diff_gpu_gpu = (out_gpu1 - out_gpu2).abs().max().item()
    diff_gpu1_cpu = (out_gpu1 - out_cpu).abs().max().item()
    diff_gpu2_cpu = (out_gpu2 - out_cpu).abs().max().item()
    
    print(f"--- PARITY CHECK (MIOPEN_DEBUG_CONV_DET={os.environ.get('MIOPEN_DEBUG_CONV_DET','0')}) ---")
    print(f"GPU vs GPU Diff : {diff_gpu_gpu:.6e}")
    print(f"GPU1 vs CPU Diff: {diff_gpu1_cpu:.6e}")
    print(f"GPU2 vs CPU Diff: {diff_gpu2_cpu:.6e}")
    
    return {
        "gpu_vs_gpu": diff_gpu_gpu,
        "gpu_vs_cpu": diff_gpu1_cpu
    }

if __name__ == "__main__":
    if not torch.cuda.is_available():
        print("NO_CUDA")
        exit(1)
        
    print("Testing with MIOPEN_DEBUG_CONV_DET=0")
    res_stock = test_conv_vs_cpu({"MIOPEN_DEBUG_CONV_DET": "0"})
    
    print("\nTesting with MIOPEN_DEBUG_CONV_DET=1")
    res_det = test_conv_vs_cpu({"MIOPEN_DEBUG_CONV_DET": "1"})
    
    summary = {
        "stock": res_stock,
        "det": res_det
    }
    print(f"\nPROBE_JSON:{json.dumps(summary)}")
