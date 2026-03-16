#!/usr/bin/env python3
import torch
import torch.nn as nn
import sys
import json
import os
from probe_diffusion import MiniUNet

def test_layer_divergence():
    if not torch.cuda.is_available():
        print("RESULT: NO_CUDA")
        return

    torch.manual_seed(42)
    model = MiniUNet(in_ch=4, base_ch=64).cuda().float().eval()
    
    # Input
    torch.manual_seed(123)
    x = torch.randn(1, 4, 64, 64, device="cuda", dtype=torch.float32)

    layer_outputs_1 = {}
    layer_outputs_2 = {}
    layer_names = []

    def get_hook(name, storage):
        def hook(model, input, output):
            # Clone and move to CPU to avoid memory pressure and ensure we capture the state
            storage[name] = output.detach().clone().cpu()
        return hook

    # Register hooks
    hooks = []
    for name, module in model.named_modules():
        if isinstance(module, (nn.Conv2d, nn.ConvTranspose2d, nn.GroupNorm, nn.Linear)):
            hooks.append(module.register_forward_hook(get_hook(name, layer_outputs_1)))
            layer_names.append(name)

    # Pass 1
    with torch.no_grad():
        _ = model(x)
    
    # Remove hooks and register for second pass
    for h in hooks:
        h.remove()
    
    hooks = []
    for name, module in model.named_modules():
        if isinstance(module, (nn.Conv2d, nn.ConvTranspose2d, nn.GroupNorm, nn.Linear)):
            hooks.append(module.register_forward_hook(get_hook(name, layer_outputs_2)))

    # Pass 2
    with torch.no_grad():
        _ = model(x)

    for h in hooks:
        h.remove()

    # Compare
    first_divergence = None
    max_diff_global = 0.0
    
    results = {}
    
    for name in layer_names:
        out1 = layer_outputs_1[name]
        out2 = layer_outputs_2[name]
        diff = (out1 - out2).abs().max().item()
        
        results[name] = diff
        if diff > max_diff_global:
            max_diff_global = diff
            
        if diff > 1e-6 and first_divergence is None:
            first_divergence = name
            print(f"DIVERGENCE_FOUND:{name}:diff={diff:.6e}")

    if first_divergence:
        print(f"RESULT: DIVERGENCE_DETECTED at {first_divergence}")
    else:
        print(f"RESULT: DETERMINISTIC_LAYERS (max_diff={max_diff_global:.6e})")

    summary = {
        "first_divergence": first_divergence,
        "max_diff": max_diff_global,
        "layer_diffs": results
    }
    print(f"PROBE_JSON:{json.dumps(summary)}")

if __name__ == "__main__":
    test_layer_divergence()
