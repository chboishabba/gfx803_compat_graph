#!/usr/bin/env python3
import argparse
from pathlib import Path

import torch


def max_abs_diff(a: torch.Tensor, b: torch.Tensor) -> float:
    return (a.detach().float().cpu() - b.detach().float().cpu()).abs().max().item()


def layout_variants(attn_weighted: torch.Tensor):
    transposed = attn_weighted.transpose(1, 2)
    bsz, seq, heads, head_dim = transposed.shape
    return {
        "view": transposed.reshape(bsz, seq, -1),
        "contig": transposed.contiguous().reshape(bsz, seq, -1),
        "perm": attn_weighted.permute(0, 2, 1, 3).contiguous().reshape(bsz, seq, -1),
    }


def main():
    parser = argparse.ArgumentParser(description="Repeat layout materialization on a saved attn_weighted tensor.")
    parser.add_argument("--tensor", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    payload = torch.load(Path(args.tensor), map_location="cpu", weights_only=False)
    attn_weighted = payload["attn_weighted"].to(args.device)

    first = layout_variants(attn_weighted)
    maxima = {name: 0.0 for name in first}
    for _ in range(1, args.repeats):
        current = layout_variants(attn_weighted)
        for name in first:
            diff = max_abs_diff(first[name], current[name])
            if diff > maxima[name]:
                maxima[name] = diff

    for name, diff in maxima.items():
        print(f"{name}\t{diff:.6f}")


if __name__ == "__main__":
    main()
