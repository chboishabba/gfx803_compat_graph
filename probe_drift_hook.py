import torch
import torch.nn as nn
import torch.nn.functional as F
import os

# Safe environment as identified
os.environ["MIOPEN_DEBUG_CONV_WINOGRAD"] = "0"
os.environ["MIOPEN_DEBUG_CONV_FFT"] = "0"
os.environ["MIOPEN_DEBUG_CONV_DET"] = "1"
os.environ["MIOPEN_DEBUG_DISABLE_FIND_DB"] = "1"
os.environ["MIOPEN_FIND_ENFORCE"] = "3"
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

from probe_diffusion import MiniUNet

def main():
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(42)
    
    model = MiniUNet(in_ch=4, base_ch=64).cuda().float().eval()
    x = torch.randn(1, 4, 32, 32, device="cuda")
    
    # We will hook every layer to capture intermediate outputs
    activations = {}
    
    def get_hook(name, run_id):
        def hook(model, input, output):
            if name not in activations:
                activations[name] = []
            activations[name].append(output.detach().clone().cpu())
        return hook

    hooks = []
    # Register hooks for every named module
    for name, module in model.named_modules():
        # Only hook leaf modules or specific blocks
        if isinstance(module, (nn.Conv2d, nn.ConvTranspose2d, nn.GroupNorm, nn.Linear)):
            hooks.append(module.register_forward_hook(get_hook(name, 0)))

    print("Running Pass 1...")
    with torch.no_grad():
        out1 = model(x.clone())
        
    print("Running Pass 2...")
    with torch.no_grad():
        out2 = model(x.clone())
        
    final_diff = (out1.cpu() - out2.cpu()).abs().max().item()
    print(f"\nFinal Output Diff: {final_diff:.6e}")
    
    if final_diff > 0:
        print("\nLayer-by-layer Analysis:")
        print(f"{'Layer Name':40} | {'Max Diff':10}")
        print("-" * 55)
        for name, acts in activations.items():
            if len(acts) >= 2:
                diff = (acts[0] - acts[1]).abs().max().item()
                if diff > 0:
                    print(f"{name:40} | {diff:.6e}  <-- DRIFT START?")
                else:
                    # Optional: print clean layers
                    # print(f"{name:40} | {diff:.6e}")
                    pass

    for h in hooks:
        h.remove()

if __name__ == "__main__":
    main()
