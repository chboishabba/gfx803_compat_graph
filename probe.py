import sys
import os

try:
    import torch
except ImportError:
    print("RESULT: NO_TORCH")
    sys.exit(1)

def main():
    print(f"PyTorch version: {torch.__version__}")
    if not torch.cuda.is_available():
        print("RESULT: NO_CUDA_AVAILABLE")
        sys.exit(1)
        
    print(f"CUDA device count: {torch.cuda.device_count()}")
    try:
        print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
    except Exception as e:
        print(f"WARNING: Could not get device name: {e}")

    try:
        # Basic allocation
        print("Allocating memory...")
        a = torch.randn(1024, 1024, device='cuda', dtype=torch.float32)
        b = torch.randn(1024, 1024, device='cuda', dtype=torch.float32)
        
        # Matrix multiplication
        print("Performing matrix multiplication...")
        c = torch.matmul(a, b)
        
        # Check for NaN/Inf (the notorious gfx803 noise bug)
        if torch.isnan(c).any() or torch.isinf(c).any():
            print("RESULT: NAN_INF_NOISE_DETECTED")
            sys.exit(2)
            
        print("RESULT: SUCCESS_BASIC_COMPAT")
        sys.exit(0)
    except Exception as e:
        print(f"RESULT: UNHANDLED_EXCEPTION")
        print(f"ERROR: {e}")
        sys.exit(3)

if __name__ == "__main__":
    main()
