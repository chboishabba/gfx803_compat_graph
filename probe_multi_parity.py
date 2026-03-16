#!/usr/bin/env python3
import torch
import torch.nn as nn
import json
import os

def check_component(name, module):
    module = module.cuda().float().eval()
    cpu_module = nn.Sequential() # dummy to match if needed
    
    # Dynamic creation of CPU pair
    if isinstance(module, nn.GroupNorm):
        cpu_module = nn.GroupNorm(module.num_groups, module.num_channels).cpu().float()
    elif isinstance(module, nn.Conv2d):
        cpu_module = nn.Conv2d(module.in_channels, module.out_channels, module.kernel_size, stride=module.stride, padding=module.padding).cpu().float()
    
    cpu_module.load_state_dict(module.state_dict())
    cpu_module.eval()
    
    torch.manual_seed(123)
    if isinstance(module, nn.GroupNorm):
        x_cpu = torch.randn(1, module.num_channels, 32, 32)
    else:
        x_cpu = torch.randn(1, module.in_channels, 32, 32)
        
    x_gpu = x_cpu.detach().clone().cuda()
    
    with torch.no_grad():
        out_cpu = cpu_module(x_cpu)
        outputs_gpu = []
        for _ in range(5):
            outputs_gpu.append(module(x_gpu).detach().clone().cpu())
            
    # Determinism (GPU vs GPU)
    max_gpu_gpu_diff = 0
    for i in range(1, len(outputs_gpu)):
        diff = (outputs_gpu[0] - outputs_gpu[i]).abs().max().item()
        max_gpu_gpu_diff = max(max_gpu_gpu_diff, diff)
        
    # Parity (GPU vs CPU)
    max_gpu_cpu_diff = (outputs_gpu[0] - out_cpu).abs().max().item()
    
    print(f"COMPONENT: {name}")
    print(f"  GPU Determinism Diff: {max_gpu_gpu_diff:.6e}")
    print(f"  GPU vs CPU Parity   : {max_gpu_cpu_diff:.6e}")
    
    return {"det": max_gpu_gpu_diff, "parity": max_gpu_cpu_diff}

def main():
    if not torch.cuda.is_available(): return
    
    results = {}
    
    # 1. GroupNorm
    results["GroupNorm"] = check_component("GroupNorm", nn.GroupNorm(32, 128))
    
    # 2. Strided Conv (The known failure)
    results["StridedConv"] = check_component("StridedConv", nn.Conv2d(64, 128, 3, stride=2, padding=1))
    
    # 3. Standard Conv
    results["StdConv"] = check_component("StdConv", nn.Conv2d(64, 64, 3, padding=1))
    
    print(f"\nPROBE_JSON:{json.dumps(results)}")

if __name__ == "__main__":
    main()
