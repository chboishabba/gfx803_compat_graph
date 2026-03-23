#!/usr/bin/env python3
import argparse
import __main__
import sys
from pathlib import Path

import torch
import torch.nn.functional as F


LEECH_ROOT = Path("/home/c/Documents/code/DASHIg/LeechTransformer")
for extra in (LEECH_ROOT, LEECH_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from config.config import LeechConfig
from models.model import LeechGPT

try:
    from torch.serialization import add_safe_globals
except ImportError:
    add_safe_globals = None


def resolve_leech_config_for_torch_load():
    safe_candidate = getattr(__main__, "LeechConfig", None)
    fallback_backup = safe_candidate
    if (
        getattr(safe_candidate, "__module__", None) == "__main__"
        and getattr(safe_candidate, "__name__", None) == "LeechConfig"
    ):
        if add_safe_globals is not None:
            add_safe_globals([safe_candidate])
        return safe_candidate, fallback_backup

    compat_cfg = type("LeechConfig", (object,), {})
    compat_cfg.__module__ = "__main__"
    __main__.LeechConfig = compat_cfg
    if add_safe_globals is not None:
        add_safe_globals([compat_cfg])
    return compat_cfg, fallback_backup


def load_checkpoint_compat(path: str, map_device: torch.device):
    try:
        return torch.load(path, map_location=map_device, weights_only=True)
    except Exception:
        compat_cfg, backup_cfg = resolve_leech_config_for_torch_load()
        try:
            return torch.load(path, map_location=map_device, weights_only=False)
        finally:
            if backup_cfg is not None:
                __main__.LeechConfig = backup_cfg
            else:
                try:
                    delattr(__main__, "LeechConfig")
                except AttributeError:
                    pass


def extract_model_state_dict(checkpoint):
    if not isinstance(checkpoint, dict):
        raise ValueError(f"Unsupported checkpoint payload type: {type(checkpoint).__name__}")
    for key in ("model_state_dict", "state_dict", "model", "module"):
        value = checkpoint.get(key)
        if isinstance(value, dict):
            return value
    tensors = {k: v for k, v in checkpoint.items() if torch.is_tensor(v)}
    if tensors:
        return tensors
    raise ValueError(f"Could not find model weights in checkpoint keys: {list(checkpoint.keys())}")


def load_model(checkpoint_path: str, device: torch.device, vocab_size: int):
    cfg = LeechConfig(vocab_size=vocab_size)
    model = LeechGPT(cfg).to(device)
    checkpoint = load_checkpoint_compat(checkpoint_path, device)
    model.load_state_dict(extract_model_state_dict(checkpoint))
    model.eval()
    return model


def make_attn_weighted(model: LeechGPT, prompt_ids):
    device = next(model.parameters()).device
    idx = torch.tensor([prompt_ids], dtype=torch.long, device=device)
    block = model.blocks[0]
    attn = block.attn

    _, seq = idx.shape
    x = model.tok_emb(idx) + model.pos_emb[:, :seq, :]
    ln1 = block.ln1(x)
    qkv = attn.qkv(ln1).reshape(1, seq, 3, attn.n_heads, attn.head_dim)
    qkv = qkv.permute(2, 0, 3, 1, 4)
    q, k, v = qkv.unbind(0)
    q = q.view(1, attn.n_heads, seq, attn.num_blocks, 24)
    k = k.view(1, attn.n_heads, seq, attn.num_blocks, 24)
    kernel = attn.W_leech[0:24, 0:24]
    q = torch.einsum("...i,ij->...j", q, kernel).reshape(1, attn.n_heads, seq, attn.head_dim)
    k = torch.einsum("...i,ij->...j", k, kernel).reshape(1, attn.n_heads, seq, attn.head_dim)
    scores = (q @ k.transpose(-2, -1)) * attn.scale
    scores = scores.masked_fill(attn.causal_mask[:, :, :seq, :seq] == 0, float("-inf"))
    attn_probs = F.softmax(scores, dim=-1)
    return (attn_probs @ v).detach().cpu()


def main():
    parser = argparse.ArgumentParser(description="Dump a fixed block0 attn_weighted tensor for standalone layout repros.")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--vocab-size", type=int, required=True)
    parser.add_argument("--prompt-ids", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    prompt_ids = [int(x) for x in args.prompt_ids.split(",") if x.strip()]
    model = load_model(args.checkpoint, torch.device("cuda"), args.vocab_size)
    attn_weighted = make_attn_weighted(model, prompt_ids)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "attn_weighted": attn_weighted,
            "prompt_ids": prompt_ids,
            "shape": tuple(attn_weighted.shape),
        },
        out_path,
    )
    print(out_path)


if __name__ == "__main__":
    main()
