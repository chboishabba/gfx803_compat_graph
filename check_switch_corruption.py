import torch
import torch.nn as nn
import os

os.environ["MIOPEN_DEBUG_CONV_WINOGRAD"] = "0"
os.environ["MIOPEN_DEBUG_CONV_FFT"] = "0"

def main():
    torch.manual_seed(42)
    
    # Target to monitor
    monitor = nn.Conv2d(128, 128, 1).cuda().eval()
    x_monitor = torch.randn(1, 128, 16, 16, device="cuda")
    
    # Switching set
    convs = [
        nn.Conv2d(64, 64, 3, padding=1).cuda().eval(),
        nn.Conv2d(64, 128, 3, stride=2, padding=1).cuda().eval(),
        nn.ConvTranspose2d(256, 128, 4, stride=2, padding=1).cuda().eval(),
    ]
    inputs = [
        torch.randn(1, 64, 32, 32, device="cuda"),
        torch.randn(1, 64, 32, 32, device="cuda"),
        torch.randn(1, 256, 8, 8, device="cuda"),
    ]
    
    print("Starting Interleaved Switching test...")
    with torch.no_grad():
        base = monitor(x_monitor).clone()
        for i in range(200):
            # Run the switchers
            for c, x in zip(convs, inputs):
                c(x)
                
            # Check the monitor
            out = monitor(x_monitor)
            diff = (base - out).abs().max().item()
            if diff > 1e-6:
                print(f"Iter {i}: Monitor CORRUPTED! Diff {diff:.6e}")
                return
            if i % 50 == 0:
                print(f"  {i}...")
                
    print("Clean run! No corruption in 200 switches.")

if __name__ == "__main__":
    main()
