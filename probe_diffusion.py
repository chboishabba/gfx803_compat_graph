#!/usr/bin/env python3
"""
GFX803 Diffusion Stress Probe — Multi-step inference simulation.

This probe goes beyond individual op testing. It simulates the actual
computational pattern of a diffusion model denoising loop to reproduce
the noise bug reported on gfx803.

Key insight: individual Conv2d/matmul/GroupNorm all pass in isolation,
but community reports show noise appears during sustained multi-step
inference. This probe tests for:
  1. Accumulated NaN/Inf drift across steps
  2. Numerical divergence between steps (entropy collapse)
  3. MIOpen kernel selection instability (perfdb warmup effects)
  4. FP16 precision cascade failures
  5. Memory pressure under sustained compute

Results are printed as structured lines for atlas_runner ingestion.
"""
import sys
import os
import json
import time
import platform

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:
    print("RESULT: NO_TORCH")
    sys.exit(1)


# ── Mini UNet ────────────────────────────────────────────────────────────
# Simplified but structurally accurate: encoder → bottleneck → decoder
# with skip connections, GroupNorm, and SiLU (like real SD UNets)

class ResBlock(nn.Module):
    def __init__(self, ch):
        super().__init__()
        self.norm1 = nn.GroupNorm(32, ch)
        self.conv1 = nn.Conv2d(ch, ch, 3, padding=1)
        self.norm2 = nn.GroupNorm(32, ch)
        self.conv2 = nn.Conv2d(ch, ch, 3, padding=1)

    def forward(self, x):
        h = self.conv1(F.silu(self.norm1(x)))
        h = self.conv2(F.silu(self.norm2(h)))
        return x + h


class SelfAttention(nn.Module):
    def __init__(self, ch, heads=4):
        super().__init__()
        self.heads = heads
        self.norm = nn.GroupNorm(32, ch)
        self.qkv = nn.Conv2d(ch, ch * 3, 1)
        self.proj = nn.Conv2d(ch, ch, 1)

    def forward(self, x):
        B, C, H, W = x.shape
        h = self.norm(x)
        qkv = self.qkv(h).reshape(B, 3, self.heads, C // self.heads, H * W)
        q, k, v = qkv[:, 0], qkv[:, 1], qkv[:, 2]
        # Scaled dot-product attention
        scale = (C // self.heads) ** -0.5
        attn = torch.einsum("bhcn,bhcm->bhnm", q, k) * scale
        attn = attn.softmax(dim=-1)
        out = torch.einsum("bhnm,bhcm->bhcn", attn, v)
        out = out.reshape(B, C, H, W)
        return x + self.proj(out)


class DownBlock(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.res = ResBlock(in_ch)
        self.down = nn.Conv2d(in_ch, out_ch, 3, stride=2, padding=1)

    def forward(self, x):
        h = self.res(x)
        return h, self.down(h)


class UpBlock(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_ch, out_ch, 4, stride=2, padding=1)
        self.res = ResBlock(out_ch * 2)  # concat with skip
        self.proj = nn.Conv2d(out_ch * 2, out_ch, 1)

    def forward(self, x, skip):
        h = self.up(x)
        # Handle size mismatch from stride math
        if h.shape != skip.shape:
            h = F.interpolate(h, size=skip.shape[2:], mode="nearest")
        h = torch.cat([h, skip], dim=1)
        h = self.res(h)
        return self.proj(h)


class MiniUNet(nn.Module):
    """~2M param UNet that exercises the same op patterns as Stable Diffusion."""
    def __init__(self, in_ch=4, base_ch=64):
        super().__init__()
        self.inp = nn.Conv2d(in_ch, base_ch, 3, padding=1)

        self.down1 = DownBlock(base_ch, base_ch * 2)       # 64 -> 128
        self.down2 = DownBlock(base_ch * 2, base_ch * 4)   # 128 -> 256

        self.mid_res1 = ResBlock(base_ch * 4)
        self.mid_attn = SelfAttention(base_ch * 4)
        self.mid_res2 = ResBlock(base_ch * 4)

        self.up2 = UpBlock(base_ch * 4, base_ch * 2)       # 256 -> 128
        self.up1 = UpBlock(base_ch * 2, base_ch)            # 128 -> 64

        self.out_norm = nn.GroupNorm(32, base_ch)
        self.out_conv = nn.Conv2d(base_ch, in_ch, 3, padding=1)

    def forward(self, x):
        h = self.inp(x)

        skip1, h = self.down1(h)
        skip2, h = self.down2(h)

        h = self.mid_res1(h)
        h = self.mid_attn(h)
        h = self.mid_res2(h)

        h = self.up2(h, skip2)
        h = self.up1(h, skip1)

        h = self.out_conv(F.silu(self.out_norm(h)))
        return h


# ── Diffusion step simulation ───────────────────────────────────────────

def euler_step(model, x_t, t, total_steps):
    """Simulates one Euler step of diffusion denoising."""
    sigma = 1.0 - (t / total_steps)
    noise_pred = model(x_t)
    x_next = x_t - sigma * noise_pred
    return x_next


# ── Test functions ───────────────────────────────────────────────────────

results = {}

def run_test(name, fn):
    try:
        status, detail = fn()
        results[name] = {"status": status, "detail": detail}
        tag = "PASS" if status == "pass" else status.upper()
        print(f"TEST:{name}:{tag}  {detail}")
    except Exception as e:
        results[name] = {"status": "error", "detail": str(e)}
        print(f"TEST:{name}:ERROR  {e}")


def test_diffusion_fp32():
    """20-step denoising loop in FP32."""
    torch.manual_seed(42)
    model = MiniUNet(in_ch=4, base_ch=64).cuda().float()
    model.eval()

    steps = 20
    x = torch.randn(1, 4, 64, 64, device="cuda", dtype=torch.float32)

    step_stats = []
    with torch.no_grad():
        for t in range(steps):
            t0 = time.time()
            x = euler_step(model, x, t, steps)
            torch.cuda.synchronize()
            dt = time.time() - t0

            has_nan = torch.isnan(x).any().item()
            has_inf = torch.isinf(x).any().item()
            xmax = x.abs().max().item()
            step_stats.append({"step": t, "dt": dt, "nan": has_nan, "inf": has_inf, "max": xmax})

            if has_nan:
                return "fail_nan", f"NaN at step {t}, max={xmax:.4f}"
            if has_inf:
                return "fail_inf", f"Inf at step {t}"

    times = [s["dt"] for s in step_stats]
    maxvals = [s["max"] for s in step_stats]
    return "pass", f"{steps} steps, avg {sum(times)/len(times)*1000:.0f}ms/step, final_max={maxvals[-1]:.2f}"


def test_diffusion_fp16():
    """20-step denoising loop in FP16 (highest noise risk)."""
    torch.manual_seed(42)
    model = MiniUNet(in_ch=4, base_ch=64).cuda().half()
    model.eval()

    steps = 20
    x = torch.randn(1, 4, 64, 64, device="cuda", dtype=torch.float16)

    with torch.no_grad():
        for t in range(steps):
            x = euler_step(model, x, t, steps)

            has_nan = torch.isnan(x).any().item()
            has_inf = torch.isinf(x).any().item()

            if has_nan:
                return "fail_nan", f"FP16 NaN at step {t}"
            if has_inf:
                return "fail_inf", f"FP16 Inf at step {t}"

    return "pass", f"{steps} steps FP16 clean, final_max={x.abs().max().item():.2f}"


def test_diffusion_mixed():
    """20-step loop using autocast (mixed precision — real-world pattern)."""
    torch.manual_seed(42)
    model = MiniUNet(in_ch=4, base_ch=64).cuda().float()
    model.eval()

    steps = 20
    x = torch.randn(1, 4, 64, 64, device="cuda", dtype=torch.float32)

    with torch.no_grad():
        for t in range(steps):
            with torch.amp.autocast("cuda"):
                x = euler_step(model, x, t, steps)

            has_nan = torch.isnan(x).any().item()
            if has_nan:
                return "fail_nan", f"Mixed-precision NaN at step {t}"

    return "pass", f"{steps} steps mixed clean, final_max={x.abs().max().item():.2f}"


def test_diffusion_50step_fp32():
    """50-step loop — tests accumulated drift over longer runs."""
    torch.manual_seed(123)
    model = MiniUNet(in_ch=4, base_ch=64).cuda().float()
    model.eval()

    steps = 50
    x = torch.randn(1, 4, 64, 64, device="cuda", dtype=torch.float32)

    with torch.no_grad():
        for t in range(steps):
            x = euler_step(model, x, t, steps)

            if torch.isnan(x).any().item():
                return "fail_nan", f"NaN at step {t}/{steps}"
            if torch.isinf(x).any().item():
                return "fail_inf", f"Inf at step {t}/{steps}"
            if x.abs().max().item() > 1e10:
                return "fail_diverge", f"Diverged at step {t}, max={x.abs().max().item():.2e}"

    return "pass", f"{steps} steps clean, final_max={x.abs().max().item():.2f}"


def test_timing_stability():
    """Check if step timing is wildly unstable (perfdb warmup pattern)."""
    torch.manual_seed(42)
    model = MiniUNet(in_ch=4, base_ch=64).cuda().float()
    model.eval()

    steps = 10
    x = torch.randn(1, 4, 64, 64, device="cuda", dtype=torch.float32)
    times = []

    with torch.no_grad():
        for t in range(steps):
            torch.cuda.synchronize()
            t0 = time.time()
            x = euler_step(model, x, t, steps)
            torch.cuda.synchronize()
            dt = time.time() - t0
            times.append(dt)

    # First step is always slower (kernel compilation / warmup)
    # But if step 1 is >5x step 2, that's the perfdb instability pattern
    if len(times) >= 2 and times[0] > 0:
        warmup_ratio = times[0] / max(times[1], 1e-9)
        avg_rest = sum(times[1:]) / len(times[1:])
        std_rest = (sum((t - avg_rest)**2 for t in times[1:]) / len(times[1:])) ** 0.5
        cv = std_rest / max(avg_rest, 1e-9)  # coefficient of variation

        detail = f"warmup_ratio={warmup_ratio:.1f}x, avg_step={avg_rest*1000:.0f}ms, cv={cv:.3f}"
        # Flag if coefficient of variation > 0.5 (very unstable)
        if cv > 0.5:
            return "fail_unstable", f"UNSTABLE timing: {detail}"
        return "pass", detail

    return "pass", f"times={[f'{t*1000:.0f}ms' for t in times]}"


def test_repeated_inference_drift():
    """Run the same input through the model 5 times, check outputs match."""
    torch.manual_seed(42)
    model = MiniUNet(in_ch=4, base_ch=64).cuda().float()
    model.eval()

    x = torch.randn(1, 4, 32, 32, device="cuda", dtype=torch.float32)

    outputs = []
    with torch.no_grad():
        for _ in range(5):
            y = model(x.clone())
            outputs.append(y.clone())

    # All outputs should be identical
    for i in range(1, len(outputs)):
        diff = (outputs[0] - outputs[i]).abs().max().item()
        if diff > 1e-5:
            return "fail_nondeterministic", f"Run {i} differs by {diff:.6f}"

    return "pass", "5 identical runs"


def test_large_channels():
    """512-channel conv blocks (real SD uses 320-1280 channels)."""
    torch.manual_seed(42)
    conv1 = nn.Conv2d(512, 512, 3, padding=1).cuda().float()
    gn = nn.GroupNorm(32, 512).cuda().float()
    conv2 = nn.Conv2d(512, 512, 3, padding=1).cuda().float()

    x = torch.randn(1, 512, 32, 32, device="cuda", dtype=torch.float32)
    with torch.no_grad():
        y = conv2(F.silu(gn(conv1(x))))

    if torch.isnan(y).any().item():
        return "fail_nan", "NaN in 512ch block"
    return "pass", f"max={y.abs().max().item():.4f}"


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    if not torch.cuda.is_available():
        print("RESULT: NO_CUDA_AVAILABLE")
        sys.exit(1)

    print(f"PyTorch version : {torch.__version__}")
    print(f"Kernel          : {platform.release()}")
    print(f"Device          : {torch.cuda.get_device_name(0)}")
    for var in ["HSA_OVERRIDE_GFX_VERSION", "MIOPEN_LOG_LEVEL", "ROC_ENABLE_PRE_VEGA"]:
        val = os.environ.get(var)
        if val:
            print(f"  {var}={val}")
    print()

    tests = [
        ("diffusion_fp32_20step",     test_diffusion_fp32),
        ("diffusion_fp16_20step",     test_diffusion_fp16),
        ("diffusion_mixed_20step",    test_diffusion_mixed),
        ("diffusion_fp32_50step",     test_diffusion_50step_fp32),
        ("timing_stability",          test_timing_stability),
        ("repeated_inference_drift",  test_repeated_inference_drift),
        ("large_channel_conv",        test_large_channels),
    ]

    for name, fn in tests:
        run_test(name, fn)

    print()

    passed = sum(1 for r in results.values() if r["status"] == "pass")
    total = len(results)
    failed = [n for n, r in results.items() if r["status"] != "pass"]

    if passed == total:
        print(f"RESULT: SUCCESS_DIFFUSION_CLEAN ({passed}/{total})")
    elif any("nan" in r["status"] for r in results.values()):
        print(f"RESULT: NAN_INF_NOISE_DETECTED ({passed}/{total}, failed: {', '.join(failed)})")
    else:
        print(f"RESULT: PARTIAL_PASS ({passed}/{total}, failed: {', '.join(failed)})")

    summary = {
        "kernel": platform.release(),
        "pytorch": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "passed": passed,
        "total": total,
        "tests": results,
    }
    print(f"\nPROBE_JSON:{json.dumps(summary)}")


if __name__ == "__main__":
    main()
