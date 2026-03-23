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
    from tokenizer.tokenizer_utils import load_tokenizer
except ImportError:
    load_tokenizer = None

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
    first_err = None
    try:
        return torch.load(path, map_location=map_device, weights_only=True)
    except Exception as exc:
        first_err = exc

    compat_cfg, backup_cfg = resolve_leech_config_for_torch_load()
    try:
        return torch.load(path, map_location=map_device, weights_only=False)
    except Exception:
        if first_err is not None:
            raise first_err
        raise
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
    model_state_dict = extract_model_state_dict(checkpoint)
    model.load_state_dict(model_state_dict)
    model.eval()
    return model


def max_abs_diff(cpu_tensor: torch.Tensor, gpu_tensor: torch.Tensor) -> float:
    return (cpu_tensor.detach().float().cpu() - gpu_tensor.detach().float().cpu()).abs().max().item()


def run_stages(model: LeechGPT, prompt_ids):
    idx = torch.tensor([prompt_ids], dtype=torch.long, device=next(model.parameters()).device)
    stages = {}

    b, t = idx.size()
    x = model.tok_emb(idx) + model.pos_emb[:, :t, :]
    stages["embed_plus_pos"] = x

    for i, block in enumerate(model.blocks):
        ln1 = block.ln1(x)
        stages[f"block{i}.ln1"] = ln1

        attn = block.attn
        B, T, _ = ln1.shape
        qkv = attn.qkv(ln1).reshape(B, T, 3, attn.n_heads, attn.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)
        q, k, v = qkv.unbind(0)
        stages[f"block{i}.q_raw"] = q
        stages[f"block{i}.k_raw"] = k
        stages[f"block{i}.v_raw"] = v

        q = q.view(B, attn.n_heads, T, attn.num_blocks, 24)
        k = k.view(B, attn.n_heads, T, attn.num_blocks, 24)
        kernel = attn.W_leech[0:24, 0:24]
        q = torch.einsum("...i,ij->...j", q, kernel)
        k = torch.einsum("...i,ij->...j", k, kernel)
        q = q.reshape(B, attn.n_heads, T, attn.head_dim)
        k = k.reshape(B, attn.n_heads, T, attn.head_dim)
        stages[f"block{i}.q_rot"] = q
        stages[f"block{i}.k_rot"] = k

        scores = (q @ k.transpose(-2, -1)) * attn.scale
        scores = scores.masked_fill(attn.causal_mask[:, :, :T, :T] == 0, float("-inf"))
        stages[f"block{i}.scores"] = scores
        attn_probs = F.softmax(scores, dim=-1)
        stages[f"block{i}.attn_probs"] = attn_probs
        attn_weighted = attn_probs @ v
        stages[f"block{i}.attn_weighted"] = attn_weighted
        attn_heads_transposed = attn_weighted.transpose(1, 2)
        stages[f"block{i}.attn_heads_transposed"] = attn_heads_transposed

        # Probe three flatten paths to isolate layout/reshape instability
        attn_out_view = attn_heads_transposed.reshape(B, T, -1)
        attn_out_contig_view = attn_heads_transposed.contiguous().reshape(B, T, -1)
        attn_out_perm_view = attn_heads_transposed.permute(0, 2, 1, 3).contiguous().reshape(B, T, -1)
        stages[f"block{i}.attn_out_preproj_view"] = attn_out_view
        stages[f"block{i}.attn_out_preproj_contig"] = attn_out_contig_view
        stages[f"block{i}.attn_out_preproj_perm"] = attn_out_perm_view

        # Use the current model path for downstream correctness comparison
        attn_out = attn_out_perm_view
        out_weight = attn.out.weight
        out_bias = attn.out.bias
        attn_out_manual = torch.matmul(attn_out, out_weight.t())
        if out_bias is not None:
            attn_out_manual = attn_out_manual + out_bias
        stages[f"block{i}.attn_out_manual"] = attn_out_manual
        attn_out = attn_out_manual
        stages[f"block{i}.attn_out"] = attn_out

        x = x + attn_out
        stages[f"block{i}.resid1"] = x
        ln2 = block.ln2(x)
        stages[f"block{i}.ln2"] = ln2
        ffn_out = block.ffn(ln2)
        stages[f"block{i}.ffn_out"] = ffn_out
        x = x + ffn_out
        stages[f"block{i}.resid2"] = x

    x = model.final_norm(x)
    stages["final_norm"] = x
    logits = model.head(x)
    stages["logits"] = logits
    return stages


def main():
    parser = argparse.ArgumentParser(description="Layerwise CPU/GPU divergence probe for LeechTransformer.")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-ids")
    parser.add_argument("--vocab-size", type=int)
    parser.add_argument("--repeats", type=int, default=1, help="Number of GPU runs to detect intra-GPU nondeterminism")
    parser.add_argument("--intra-eps", type=float, default=1e-6, help="Threshold to flag intra-GPU drift")
    parser.add_argument("--no-cpu", action="store_true", help="Skip CPU baseline (only intra-GPU drift)")
    args = parser.parse_args()

    if args.prompt_ids:
        prompt_ids = [int(x) for x in args.prompt_ids.split(",") if x.strip()]
    else:
        if load_tokenizer is None:
            raise RuntimeError("sentencepiece/tokenizer support unavailable; pass --prompt-ids and --vocab-size")
        if args.prompt is None:
            raise RuntimeError("either --prompt or --prompt-ids is required")
        sp = load_tokenizer()
        prompt_ids = sp.encode(args.prompt)
        if not prompt_ids:
            prompt_ids = [sp.bos_id() if sp.bos_id() != -1 else sp.unk_id()]
        if args.vocab_size is None:
            args.vocab_size = sp.get_piece_size()

    if args.vocab_size is None:
        raise RuntimeError("--vocab-size is required when using --prompt-ids")

    if args.repeats < 1:
        raise ValueError("--repeats must be >= 1")

    cpu = None
    if not args.no_cpu:
        cpu_model = load_model(args.checkpoint, torch.device("cpu"), args.vocab_size)
        cpu = run_stages(cpu_model, prompt_ids)

    gpu_model = load_model(args.checkpoint, torch.device("cuda"), args.vocab_size)

    first_gpu = run_stages(gpu_model, prompt_ids)
    stage_names = list(first_gpu.keys())

    cpu_gpu_diff = {}
    for name in stage_names:
        if cpu is None:
            cpu_gpu_diff[name] = None
        else:
            cpu_gpu_diff[name] = max_abs_diff(cpu[name], first_gpu[name])

    intra_max = {name: 0.0 for name in stage_names}
    first_intra = None  # (stage, diff, run_idx)

    for run_idx in range(1, args.repeats):
        gpu_run = run_stages(gpu_model, prompt_ids)
        for name in stage_names:
            diff = max_abs_diff(first_gpu[name], gpu_run[name])
            if diff > intra_max[name]:
                intra_max[name] = diff
            if first_intra is None and diff > args.intra_eps:
                first_intra = (name, diff, run_idx + 1)

    for name in stage_names:
        cpu_part = f"{cpu_gpu_diff[name]:.6f}" if cpu_gpu_diff[name] is not None else "NA"
        print(f"{name}\t{cpu_part}\t{intra_max[name]:.6f}")

    if first_intra is None:
        print("first_intra_gpu_drift\tnone")
    else:
        stage, diff, run_idx = first_intra
        print(f"first_intra_gpu_drift\t{stage}\t{diff:.6f}\trun={run_idx}")


if __name__ == "__main__":
    main()
