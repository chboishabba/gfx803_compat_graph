import torch
import torch.nn as nn
import os
import sys

# Set MIOpen Find Enforce to 3 (Fastest) to avoid profiling noise?
# Or 1 (Normal)?
# Let's try to simulate the diffusion loop: 20 passes.

torch.manual_seed(42)
conv = nn.Conv2d(64, 128, 3, stride=2, padding=1).cuda().float().eval()
x = torch.randn(1, 64, 64, 64, device="cuda")

with torch.no_grad():
    base = conv(x).clone()
    max_diff = 0
    for i in range(50):
        out = conv(x)
        diff = (base - out).abs().max().item()
        if diff > max_diff:
            max_diff = diff
        if diff > 0:
            print(f"Iter {i}: Diff {diff:.6e}")

print(f"Final Max Diff: {max_diff:.6e}")
if max_diff > 0:
    print("RESULT: NON-DETERMINISTIC")
else:
    print("RESULT: DETERMINISTIC")
