# Polaris (GFX803) Stability Blueprint

This document outlines the stabilized profile for running modern Machine Learning workloads (Diffusion, WhisperX) on AMD Polaris (RX 480/580) hardware using ROCm 6.x.

## ⚠️ Identified Hazards

1.  **Winograd Hangs:** Common convolution solvers that cause GPU ring timeouts and system freezes.
2.  **GEMM Drift:** MIOpen solver `GemmFwdRest` (ID 91) is numerically incorrect on Polaris, causing a ~0.15 drift per iteration.
3.  **rocBLAS Non-determinism:** `torch.einsum` and batch matmuls are non-deterministic by default on this architecture.
4.  **State Poisoning:** Sustained high-volume kernel launches degrade numerical integrity until even 1x1 convolutions fail.

## 🛡️ Recommended "Safe Profile"

To achieve stable and reproducible results, use the following environment variables.

### Environment Variables

```bash
# General Compatibility
export HSA_OVERRIDE_GFX_VERSION=8.0.3
export ROC_ENABLE_PRE_VEGA=1

# MIOpen Mitigations (Hangs & Noise)
export MIOPEN_DEBUG_CONV_WINOGRAD=0     # Fixes system hangs
export MIOPEN_DEBUG_CONV_GEMM=0         # Fixes major numerical noise/drift
export MIOPEN_DEBUG_CONV_FFT=0          # Extra safety margin

# Enforced Stability
export MIOPEN_DEBUG_CONV_DET=1          # Force deterministic solver selection
export MIOPEN_DEBUG_DISABLE_FIND_DB=1   # Bypass potentially stale or poisoned caches
export MIOPEN_FIND_ENFORCE=3            # Speed up startup with stable selection

# rocBLAS / PyTorch Determinism
export CUBLAS_WORKSPACE_CONFIG=:4096:8  # Required for deterministic matmuls
```

### PyTorch Configuration

Always initialize your scripts with:

```python
import torch

# Enable deterministic algorithms for Einsum/Attention
torch.use_deterministic_algorithms(True)

# (Optional) The "Absolute Precision" mode
# If you still see drift, disable MIOpen entirely. 
# This is slow but bit-perfect.
# torch.backends.cudnn.enabled = False 
```

## 🔍 Deep-Dive Findings

### Identified Failing Kernel
Through `rocprof`, the unstable kernel has been identified as a Tensile GEMM kernel:
`Cijk_Ailk_Bljk_SB_MT64x64x16_SN_AMAS3_BL1_BS1_EPS1_GLVWA4_GLVWB4_GRVWn1_GSU1_GSUASB_ISA803_K1_KLA_LPA0_LPB4_LRVW4_MMFGLC_NLCA1_NLCB1_PGR1_PLR1_SIA1_SU32_SUS256_SVW4_TT4_4_USFGROn1_VAW1_VSn1_VW4_VWB4_WG16_16_1_WGM8`

**Root Cause:** Tensile YAML generation bug for GFX803. Likely an indexing or register reuse issue in the assembly generation.
