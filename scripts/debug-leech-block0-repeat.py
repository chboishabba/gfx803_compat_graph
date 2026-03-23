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


def max_abs_diff(a: torch.Tensor, b: torch.Tensor) -> float:
    return (a.detach().float().cpu() - b.detach().float().cpu()).abs().max().item()


def run_block0(model: LeechGPT, prompt_ids):
    device = next(model.parameters()).device
    idx = torch.tensor([prompt_ids], dtype=torch.long, device=device)
    block = model.blocks[0]

    bsz, seq, _ = model.tok_emb(idx).shape
    x = model.tok_emb(idx) + model.pos_emb[:, :seq, :]
    stages = {"embed_plus_pos": x}

    ln1 = block.ln1(x)
    stages["ln1"] = ln1

    attn = block.attn
    qkv = attn.qkv(ln1).reshape(bsz, seq, 3, attn.n_heads, attn.head_dim)
    qkv = qkv.permute(2, 0, 3, 1, 4)
    q, k, v = qkv.unbind(0)
    stages["q_raw"] = q
    stages["k_raw"] = k
    stages["v_raw"] = v

    q = q.view(bsz, attn.n_heads, seq, attn.num_blocks, 24)
    k = k.view(bsz, attn.n_heads, seq, attn.num_blocks, 24)
    kernel = attn.W_leech[0:24, 0:24]
    q = torch.einsum("...i,ij->...j", q, kernel)
    k = torch.einsum("...i,ij->...j", k, kernel)
    q = q.reshape(bsz, attn.n_heads, seq, attn.head_dim)
    k = k.reshape(bsz, attn.n_heads, seq, attn.head_dim)
    stages["q_rot"] = q
    stages["k_rot"] = k

    scores = (q @ k.transpose(-2, -1)) * attn.scale
    scores = scores.masked_fill(attn.causal_mask[:, :, :seq, :seq] == 0, float("-inf"))
    stages["scores"] = scores
    attn_probs = F.softmax(scores, dim=-1)
    stages["attn_probs"] = attn_probs

    attn_weighted = attn_probs @ v
    stages["attn_weighted"] = attn_weighted
    attn_heads_transposed = attn_weighted.transpose(1, 2)
    stages["attn_heads_transposed"] = attn_heads_transposed

    attn_out_preproj = attn_weighted.permute(0, 2, 1, 3).contiguous().reshape(bsz, seq, -1)
    stages["attn_out_preproj"] = attn_out_preproj

    attn_out_manual = torch.matmul(attn_out_preproj, attn.out.weight.t())
    if attn.out.bias is not None:
        attn_out_manual = attn_out_manual + attn.out.bias
    stages["attn_out_manual"] = attn_out_manual

    resid1 = x + attn_out_manual
    stages["resid1"] = resid1
    ln2 = block.ln2(resid1)
    stages["ln2"] = ln2
    ffn_out = block.ffn(ln2)
    stages["ffn_out"] = ffn_out
    resid2 = resid1 + ffn_out
    stages["resid2"] = resid2
    return stages


def main():
    parser = argparse.ArgumentParser(description="Repeat block0-only Leech probe for same-process GPU drift.")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--vocab-size", type=int, required=True)
    parser.add_argument("--prompt-ids", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--intra-eps", type=float, default=1e-6)
    args = parser.parse_args()

    if args.repeats < 2:
        raise ValueError("--repeats must be >= 2")

    prompt_ids = [int(x) for x in args.prompt_ids.split(",") if x.strip()]
    gpu_model = load_model(args.checkpoint, torch.device("cuda"), args.vocab_size)

    first = run_block0(gpu_model, prompt_ids)
    stage_names = list(first.keys())
    intra_max = {name: 0.0 for name in stage_names}
    first_intra = None

    for run_idx in range(1, args.repeats):
        current = run_block0(gpu_model, prompt_ids)
        for name in stage_names:
            diff = max_abs_diff(first[name], current[name])
            if diff > intra_max[name]:
                intra_max[name] = diff
            if first_intra is None and diff > args.intra_eps:
                first_intra = (name, diff, run_idx + 1)

    for name in stage_names:
        print(f"{name}\t{intra_max[name]:.6f}")

    if first_intra is None:
        print("first_intra_gpu_drift\tnone")
    else:
        stage, diff, run_idx = first_intra
        print(f"first_intra_gpu_drift\t{stage}\t{diff:.6f}\trun={run_idx}")


if __name__ == "__main__":
    main()
