#!/usr/bin/env python3
"""
GFX803 Compatibility Probe — Progressive GPU test battery.

Each test is independent. Results are printed as structured lines:
    TEST:<name>:<status>   (status = PASS | FAIL_NAN | FAIL_INF | FAIL_MISMATCH | ERROR)

The atlas_runner verify command parses these to auto-populate the graph.
"""
import sys
import os
import platform
import json
import time

try:
    import torch
except ImportError:
    print("RESULT: NO_TORCH")
    sys.exit(1)


def header():
    print(f"PyTorch version : {torch.__version__}")
    print(f"Kernel          : {platform.release()}")
    print(f"CUDA available  : {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"Device count    : {torch.cuda.device_count()}")
        try:
            print(f"Device name     : {torch.cuda.get_device_name(0)}")
        except Exception:
            pass
    # Dump relevant env vars
    for var in ["HSA_OVERRIDE_GFX_VERSION", "PYTORCH_ROCM_ARCH",
                "MIOPEN_LOG_LEVEL", "ROC_ENABLE_PRE_VEGA"]:
        val = os.environ.get(var)
        if val:
            print(f"  {var}={val}")
    print()


results = {}

def run_test(name, fn):
    """Run a single test, catch all exceptions, print structured result."""
    try:
        status, detail = fn()
        results[name] = {"status": status, "detail": detail}
        tag = "PASS" if status == "pass" else status.upper()
        print(f"TEST:{name}:{tag}  {detail}")
    except Exception as e:
        results[name] = {"status": "error", "detail": str(e)}
        print(f"TEST:{name}:ERROR  {e}")


# ---------------------------------------------------------------------------
# T1: Basic FP32 matmul
# ---------------------------------------------------------------------------
def test_fp32_matmul():
    a = torch.randn(1024, 1024, device="cuda", dtype=torch.float32)
    b = torch.randn(1024, 1024, device="cuda", dtype=torch.float32)
    c = torch.matmul(a, b)
    if torch.isnan(c).any():
        return "fail_nan", f"NaN count: {torch.isnan(c).sum().item()}"
    if torch.isinf(c).any():
        return "fail_inf", f"Inf count: {torch.isinf(c).sum().item()}"
    return "pass", f"max={c.abs().max().item():.4f}"


# ---------------------------------------------------------------------------
# T2: FP16 matmul (half precision — known fragile on gfx803)
# ---------------------------------------------------------------------------
def test_fp16_matmul():
    a = torch.randn(1024, 1024, device="cuda", dtype=torch.float16)
    b = torch.randn(1024, 1024, device="cuda", dtype=torch.float16)
    c = torch.matmul(a, b)
    if torch.isnan(c).any():
        return "fail_nan", f"NaN count: {torch.isnan(c).sum().item()}"
    if torch.isinf(c).any():
        return "fail_inf", f"Inf count: {torch.isinf(c).sum().item()}"
    return "pass", f"max={c.abs().max().item():.4f}"


# ---------------------------------------------------------------------------
# T3: Conv2d FP32 (MIOpen path — the primary suspect for diffusion noise)
# ---------------------------------------------------------------------------
def test_conv2d_fp32():
    conv = torch.nn.Conv2d(64, 128, kernel_size=3, padding=1).cuda().float()
    x = torch.randn(1, 64, 64, 64, device="cuda", dtype=torch.float32)
    y = conv(x)
    if torch.isnan(y).any():
        return "fail_nan", f"NaN in conv output, count={torch.isnan(y).sum().item()}"
    if torch.isinf(y).any():
        return "fail_inf", f"Inf in conv output"
    return "pass", f"shape={list(y.shape)}, max={y.abs().max().item():.4f}"


# ---------------------------------------------------------------------------
# T4: Conv2d FP16 (half-precision conv — maximum noise risk)
# ---------------------------------------------------------------------------
def test_conv2d_fp16():
    conv = torch.nn.Conv2d(64, 128, kernel_size=3, padding=1).cuda().half()
    x = torch.randn(1, 64, 64, 64, device="cuda", dtype=torch.float16)
    y = conv(x)
    if torch.isnan(y).any():
        return "fail_nan", f"NaN in fp16 conv, count={torch.isnan(y).sum().item()}"
    if torch.isinf(y).any():
        return "fail_inf", f"Inf in fp16 conv"
    return "pass", f"shape={list(y.shape)}, max={y.abs().max().item():.4f}"


# ---------------------------------------------------------------------------
# T5: Conv2d determinism check (run twice, compare outputs)
# ---------------------------------------------------------------------------
def test_conv2d_determinism():
    torch.manual_seed(42)
    conv = torch.nn.Conv2d(64, 64, kernel_size=3, padding=1).cuda().float()
    x = torch.randn(1, 64, 32, 32, device="cuda", dtype=torch.float32)
    y1 = conv(x).clone()
    y2 = conv(x).clone()
    if not torch.allclose(y1, y2, atol=1e-6):
        diff = (y1 - y2).abs().max().item()
        return "fail_mismatch", f"Non-deterministic conv! max_diff={diff}"
    return "pass", "Deterministic within atol=1e-6"


# ---------------------------------------------------------------------------
# T6: Larger Conv2d simulating UNet block (256 channels, bigger spatial)
# ---------------------------------------------------------------------------
def test_unet_block_conv():
    conv1 = torch.nn.Conv2d(256, 256, kernel_size=3, padding=1).cuda().float()
    conv2 = torch.nn.Conv2d(256, 256, kernel_size=3, padding=1).cuda().float()
    x = torch.randn(1, 256, 64, 64, device="cuda", dtype=torch.float32)
    y = conv2(torch.relu(conv1(x)))
    if torch.isnan(y).any():
        return "fail_nan", f"NaN in unet-like block"
    if torch.isinf(y).any():
        return "fail_inf", f"Inf in unet-like block"
    return "pass", f"shape={list(y.shape)}, max={y.abs().max().item():.4f}"


# ---------------------------------------------------------------------------
# T7: GroupNorm (used heavily in diffusion models)
# ---------------------------------------------------------------------------
def test_groupnorm():
    gn = torch.nn.GroupNorm(32, 256).cuda().float()
    x = torch.randn(1, 256, 32, 32, device="cuda", dtype=torch.float32)
    y = gn(x)
    if torch.isnan(y).any():
        return "fail_nan", "NaN in GroupNorm output"
    if torch.isinf(y).any():
        return "fail_inf", "Inf in GroupNorm output"
    return "pass", f"max={y.abs().max().item():.4f}"


# ---------------------------------------------------------------------------
# T8: Attention-like pattern (QKV matmul + softmax)
# ---------------------------------------------------------------------------
def test_attention_pattern():
    B, H, S, D = 1, 8, 64, 64
    q = torch.randn(B, H, S, D, device="cuda", dtype=torch.float32)
    k = torch.randn(B, H, S, D, device="cuda", dtype=torch.float32)
    v = torch.randn(B, H, S, D, device="cuda", dtype=torch.float32)
    attn = torch.matmul(q, k.transpose(-2, -1)) / (D ** 0.5)
    attn = torch.softmax(attn, dim=-1)
    out = torch.matmul(attn, v)
    if torch.isnan(out).any():
        return "fail_nan", "NaN in attention output"
    if torch.isinf(out).any():
        return "fail_inf", "Inf in attention output"
    return "pass", f"max={out.abs().max().item():.4f}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not torch.cuda.is_available():
        print("RESULT: NO_CUDA_AVAILABLE")
        sys.exit(1)

    header()

    tests = [
        ("fp32_matmul",        test_fp32_matmul),
        ("fp16_matmul",        test_fp16_matmul),
        ("conv2d_fp32",        test_conv2d_fp32),
        ("conv2d_fp16",        test_conv2d_fp16),
        ("conv2d_determinism", test_conv2d_determinism),
        ("unet_block_conv",    test_unet_block_conv),
        ("groupnorm",          test_groupnorm),
        ("attention_pattern",  test_attention_pattern),
    ]

    for name, fn in tests:
        run_test(name, fn)

    print()

    # Summary
    passed = sum(1 for r in results.values() if r["status"] == "pass")
    total = len(results)
    failed_names = [n for n, r in results.items() if r["status"] != "pass"]

    if passed == total:
        print(f"RESULT: SUCCESS_BASIC_COMPAT ({passed}/{total} tests passed)")
    elif any(r["status"] == "fail_nan" for r in results.values()):
        print(f"RESULT: NAN_INF_NOISE_DETECTED ({passed}/{total} passed, failed: {', '.join(failed_names)})")
    else:
        print(f"RESULT: PARTIAL_PASS ({passed}/{total} passed, failed: {', '.join(failed_names)})")

    # Dump machine-readable JSON summary
    summary = {
        "kernel": platform.release(),
        "pytorch": torch.__version__,
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
        "passed": passed,
        "total": total,
        "tests": results,
    }
    print(f"\nPROBE_JSON:{json.dumps(summary)}")


if __name__ == "__main__":
    main()
