import torch
import torch.nn as nn
import os

# Identify the solver used for a 1x1 conv
os.environ["HSA_OVERRIDE_GFX_VERSION"] = "8.0.3"
os.environ["MIOPEN_LOG_LEVEL"] = "6"
os.environ["MIOPEN_DEBUG_CONV_WINOGRAD"] = "0"

conv = nn.Conv2d(128, 128, 1).cuda().eval()
x = torch.randn(1, 128, 16, 16, device="cuda")
with torch.no_grad():
    conv(x)
