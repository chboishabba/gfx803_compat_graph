# GitHub Issue Draft: MIOpen Stability & Numerical Drift on GFX803 (Polaris)

**Location:** [ROCm/MIOpen](https://github.com/ROCm/MIOpen/issues)

---

## Technical Summary
**Title:** [GFX803] Progressive Numerical Drift and Kernel Hangs in MIOpen Solvers (ROCm 6.4)

### Environment
*   **GPU:** Radeon RX 480/580 (GFX803 / Polaris)
*   **ROCm Version:** 6.4.x (also observed in 6.1.x)
*   **OS:** Linux (e.g., CachyOS / Arch / Ubuntu)
*   **PyTorch version:** 2.4.x - 2.6.x
*   **MIOpen Version:** 3.4.0 (f10c6ed80)

### Description of Issues

#### 1. Winograd Solver Hangs (KFD Reset)
Standard convolutions using the Winograd solver frequently trigger `amdgpu` ring timeouts and hardware hangs on Polaris hardware. 
*   **Symptom:** System freeze requiring hard reset or KFD soft recovery.
*   **Workaround:** `MIOPEN_DEBUG_CONV_WINOGRAD=0`.

#### 2. Progressive Numerical Drift (New Discovery)
Even when Winograd is disabled, certain MIOpen solvers (specifically `GemmFwdRest` and others selected for small input channels like 4->64) exhibit **stateful numerical corruption**. Output is correct for the first ~25 iterations, but then begins to drift significantly from the baseline.
*   **Symptom:** In Diffusion models, image generation starts clean but turns into "salt and pepper" noise or black artifacts after 20-30 steps.
*   **Findings:** The drift is **deterministic** once it begins. If `torch.backends.cudnn.enabled=False` is set (disabling MIOpen), the drift disappears entirely.
*   **Observed Solver:** ID 91 (`GemmFwdRest`).

---

### Minimal Reproducible Example (MRE)
The following script reproduces the "Stateful Drift" on an RX 580:

```python
import torch
import torch.nn as nn
import os

# Essential for GFX803
os.environ["HSA_OVERRIDE_GFX_VERSION"] = "8.0.3"
os.environ["MIOPEN_DEBUG_CONV_WINOGRAD"] = "0"
os.environ["MIOPEN_DEBUG_CONV_DET"] = "1"
os.environ["MIOPEN_DEBUG_DISABLE_FIND_DB"] = "1"
os.environ["MIOPEN_FIND_ENFORCE"] = "3"

def main():
    torch.use_deterministic_algorithms(True)
    
    # Target shape: 4 input channels (typical for Diffusion latents)
    conv = nn.Conv2d(4, 64, 3, padding=1).cuda().eval()
    x = torch.randn(1, 4, 32, 32, device="cuda")
    
    with torch.no_grad():
        base = conv(x).clone()
        for i in range(100):
            out = conv(x)
            diff = (base - out).abs().max().item()
            if diff > 1e-4:
                print(f"ITER {i:03}: DRIFT DETECTED! Max Diff: {diff:.6e}")
```

### Supporting Logs (MIOpen Trace)
```text
MIOpen(HIP): Info2 [GetSolutionsFallback] id: 91, algo: 0, time: 27.7778, ws: 147456, name: GemmFwdRest
MIOpen(HIP): Info2 [GetWorkspaceSizes] GemmFwdRest: 147456
MIOpen(HIP): Info2 [GetMaxWorkSpaceSize] 0 < 147456
```

---

### Workarounds Identified
1.  **Partial Mitigation:** `MIOPEN_DEBUG_CONV_WINOGRAD=0` (prevents hangs).
2.  **Full Mitigation:** `torch.backends.cudnn.enabled=False` (prevents drift, but slows performance by 2-5x).
