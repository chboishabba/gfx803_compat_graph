#!/usr/bin/env python3
"""Binary-search the MiniUNet to find which block introduces non-determinism.

We run each component in isolation 5x on the same input and compare outputs.
This should pinpoint whether it's ConvTranspose2d, F.interpolate, attention,
or accumulated drift from composition.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import json
import os

def det_check(name, fn, x, runs=5):
    """Run fn(x) `runs` times and report max diff."""
    with torch.no_grad():
        base = fn(x.clone()).clone()
        max_diff = 0
        for i in range(runs):
            out = fn(x.clone())
            diff = (base - out).abs().max().item()
            max_diff = max(max_diff, diff)
    tag = "DET" if max_diff < 1e-6 else "NON-DET"
    print(f"  {name:30s}: max_diff={max_diff:.6e}  [{tag}]")
    return {"name": name, "max_diff": max_diff, "tag": tag}

def main():
    if not torch.cuda.is_available():
        print("NO_CUDA")
        return

    # Enable deterministic algorithms if env says so
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG"):
        torch.use_deterministic_algorithms(True)

    print(f"PyTorch: {torch.__version__}")
    print(f"Device:  {torch.cuda.get_device_name(0)}")
    print(f"Deterministic Mode: {torch.are_deterministic_algorithms_enabled()}")
    print()

    torch.manual_seed(42)
    results = []

    # 1. Conv2d (no stride) — baseline
    print("=== Individual Ops ===")
    conv_ns = nn.Conv2d(64, 64, 3, padding=1).cuda().float().eval()
    x_64 = torch.randn(1, 64, 32, 32, device="cuda")
    results.append(det_check("Conv2d(64→64, k=3, s=1)", conv_ns, x_64))

    # 2. Conv2d (strided) — the known culprit
    conv_s = nn.Conv2d(64, 128, 3, stride=2, padding=1).cuda().float().eval()
    results.append(det_check("Conv2d(64→128, k=3, s=2)", conv_s, x_64))

    # 3. ConvTranspose2d — the suspected new culprit
    deconv = nn.ConvTranspose2d(128, 64, 4, stride=2, padding=1).cuda().float().eval()
    x_128 = torch.randn(1, 128, 16, 16, device="cuda")
    results.append(det_check("ConvTranspose2d(128→64, k=4, s=2)", deconv, x_128))

    # 4. ConvTranspose2d (larger channels)
    deconv_big = nn.ConvTranspose2d(256, 128, 4, stride=2, padding=1).cuda().float().eval()
    x_256 = torch.randn(1, 256, 8, 8, device="cuda")
    results.append(det_check("ConvTranspose2d(256→128, k=4, s=2)", deconv_big, x_256))

    # 5. GroupNorm
    gn = nn.GroupNorm(32, 128).cuda().float().eval()
    x_gn = torch.randn(1, 128, 16, 16, device="cuda")
    results.append(det_check("GroupNorm(32, 128)", gn, x_gn))

    # 6. SiLU
    silu = nn.SiLU().cuda()
    results.append(det_check("SiLU", silu, x_128))

    # 7. F.interpolate nearest
    def interp_fn(x):
        return F.interpolate(x, size=(32, 32), mode="nearest")
    results.append(det_check("F.interpolate(nearest, 16→32)", interp_fn, x_128))

    # 8. Einsum (attention pattern)
    q = torch.randn(1, 4, 256, 64, device="cuda")
    def einsum_fn(x):
        return torch.einsum("bhcn,bhcm->bhnm", x, x)
    results.append(det_check("Einsum(attention, 256 tokens)", einsum_fn, q))

    # 9. Softmax
    attn_in = torch.randn(1, 4, 256, 256, device="cuda")
    results.append(det_check("Softmax(dim=-1)", lambda x: x.softmax(dim=-1), attn_in))

    # 10. Conv2d 1x1 (used in attention projection)
    conv1x1 = nn.Conv2d(128, 128, 1).cuda().float().eval()
    results.append(det_check("Conv2d(128→128, k=1)", conv1x1, x_128))

    # === Compound blocks ===
    print("\n=== Compound Blocks ===")

    # 11. ResBlock
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

    res64 = ResBlock(64).cuda().float().eval()
    results.append(det_check("ResBlock(64)", res64, x_64))

    res128 = ResBlock(128).cuda().float().eval()
    results.append(det_check("ResBlock(128)", res128, x_128))

    # 12. DownBlock (ResBlock + strided conv)
    class DownBlock(nn.Module):
        def __init__(self, in_ch, out_ch):
            super().__init__()
            self.res = ResBlock(in_ch)
            self.down = nn.Conv2d(in_ch, out_ch, 3, stride=2, padding=1)
        def forward(self, x):
            h = self.res(x)
            return self.down(h)

    down = DownBlock(64, 128).cuda().float().eval()
    results.append(det_check("DownBlock(64→128)", down, x_64))

    # 13. UpBlock (deconv + concat + resblock)
    class UpBlock(nn.Module):
        def __init__(self, in_ch, out_ch):
            super().__init__()
            self.up = nn.ConvTranspose2d(in_ch, out_ch, 4, stride=2, padding=1)
            self.res = ResBlock(out_ch * 2)
            self.proj = nn.Conv2d(out_ch * 2, out_ch, 1)
        def forward(self, x):
            h = self.up(x)
            skip = torch.randn_like(h)  # simulate skip connection
            h = torch.cat([h, skip], dim=1)
            h = self.res(h)
            return self.proj(h)

    # Note: this uses randn_like skip, so it will always differ.
    # Let's make it deterministic:
    class UpBlockDet(nn.Module):
        def __init__(self, in_ch, out_ch):
            super().__init__()
            self.up = nn.ConvTranspose2d(in_ch, out_ch, 4, stride=2, padding=1)
            self.res = ResBlock(out_ch * 2)
            self.proj = nn.Conv2d(out_ch * 2, out_ch, 1)
            self.register_buffer("skip", torch.randn(1, out_ch, 32, 32))
        def forward(self, x):
            h = self.up(x)
            if h.shape != self.skip.shape:
                h = F.interpolate(h, size=self.skip.shape[2:], mode="nearest")
            h = torch.cat([h, self.skip.expand_as(h)], dim=1)
            h = self.res(h)
            return self.proj(h)

    up = UpBlockDet(128, 64).cuda().float().eval()
    results.append(det_check("UpBlock(128→64)", up, x_128))

    # 14. SelfAttention block
    class SelfAttn(nn.Module):
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
            scale = (C // self.heads) ** -0.5
            attn = torch.einsum("bhcn,bhcm->bhnm", q, k) * scale
            attn = attn.softmax(dim=-1)
            out = torch.einsum("bhnm,bhcm->bhcn", attn, v)
            out = out.reshape(B, C, H, W)
            return x + self.proj(out)

    sattn = SelfAttn(128).cuda().float().eval()
    results.append(det_check("SelfAttention(128, heads=4)", sattn, x_128))

    # Summary
    print("\n=== SUMMARY ===")
    non_det = [r for r in results if r["tag"] == "NON-DET"]
    if non_det:
        print(f"Found {len(non_det)} non-deterministic component(s):")
        for r in non_det:
            print(f"  ❌ {r['name']}: {r['max_diff']:.6e}")
    else:
        print("All components are deterministic in isolation! ✅")
        print("Non-determinism must come from composition / accumulated drift.")

    print(f"\nPROBE_JSON:{json.dumps(results)}")

if __name__ == "__main__":
    main()
