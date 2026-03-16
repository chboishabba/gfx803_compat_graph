import torch
import os

try:
    torch.use_deterministic_algorithms(True)
    # Some ops might require CUBLAS_WORKSPACE_CONFIG
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    print("Deterministic mode enabled")
except Exception as e:
    print(f"Failed to enable deterministic mode: {e}")

q = torch.randn(1, 8, 1024, 64, device="cuda", dtype=torch.float32)
k = torch.randn(1, 8, 1024, 64, device="cuda", dtype=torch.float32)

with torch.no_grad():
    try:
        base = torch.einsum("bhcn,bhcm->bhnm", q, k).clone()
        max_diff = 0
        for i in range(50):
            out = torch.einsum("bhcn,bhcm->bhnm", q, k)
            diff = (base - out).abs().max().item()
            if diff > max_diff:
                max_diff = diff
        print(f"Einsum Max Diff (Deterministic Mode): {max_diff:.6e}")
    except Exception as e:
        print(f"Einsum failed in deterministic mode: {e}")
