import torch
import os

# Typical diffusion attention shapes
# B, Heads, SeqLen, DimHead
# 1, 8, 1024, 64
q = torch.randn(1, 8, 1024, 64, device="cuda", dtype=torch.float32)
k = torch.randn(1, 8, 1024, 64, device="cuda", dtype=torch.float32)

with torch.no_grad():
    # Scaled dot product: (1, 8, 1024, 64) @ (1, 8, 64, 1024) -> (1, 8, 1024, 1024)
    base = torch.einsum("bhcn,bhcm->bhnm", q, k).clone()
    max_diff = 0
    for i in range(50):
        out = torch.einsum("bhcn,bhcm->bhnm", q, k)
        diff = (base - out).abs().max().item()
        if diff > max_diff:
            max_diff = diff
        if diff > 0:
            print(f"Iter {i}: Diff {diff:.6e}")

print(f"Einsum Max Diff: {max_diff:.6e}")

# Try standard Matmul
a = torch.randn(1024, 1024, device="cuda", dtype=torch.float32)
b = torch.randn(1024, 1024, device="cuda", dtype=torch.float32)
with torch.no_grad():
    base = torch.matmul(a, b).clone()
    max_diff = 0
    for i in range(50):
        out = torch.matmul(a, b)
        diff = (base - out).abs().max().item()
        if diff > max_diff:
            max_diff = diff
    print(f"Matmul Max Diff: {max_diff:.6e}")
