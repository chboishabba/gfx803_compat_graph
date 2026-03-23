#!/usr/bin/env python3
import argparse
import __main__
import sys
from pathlib import Path

import torch


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


def main():
    parser = argparse.ArgumentParser(description="Generate Leech token ids from pre-encoded prompt ids.")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--prompt-ids", required=True)
    parser.add_argument("--vocab-size", type=int, required=True)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--kv-cache", action="store_true")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cfg = LeechConfig(vocab_size=args.vocab_size)
    model = LeechGPT(cfg).to(device)
    checkpoint = load_checkpoint_compat(args.checkpoint, device)
    model.load_state_dict(extract_model_state_dict(checkpoint))
    model.eval()

    prompt_ids = [int(x) for x in args.prompt_ids.split(",") if x.strip()]
    context = torch.tensor([prompt_ids], dtype=torch.long, device=device)
    block_size = model.cfg.block_size

    use_kv_cache = bool(args.kv_cache) and (context.size(1) <= block_size)
    past_key_values = None
    generated = []

    with torch.no_grad():
        if use_kv_cache:
            _, _, _, past_key_values = model(context, use_cache=True, past_key_values=None)

        for _ in range(args.max_tokens):
            if use_kv_cache:
                idx_in = context[:, -1:]
                logits, _, _, past_key_values = model(idx_in, use_cache=True, past_key_values=past_key_values)
                logits = logits[0, -1, :].clone()
            else:
                idx_cond = context[:, -block_size:]
                logits, _, _, _ = model(idx_cond, use_cache=False, past_key_values=None)
                logits = logits[0, -1, :].clone()

            if args.temperature <= 0:
                next_token = torch.argmax(logits, dim=-1, keepdim=True)
            else:
                logits = logits / args.temperature
                probs = torch.softmax(logits, dim=-1)
                if args.top_k > 0:
                    v, _ = torch.topk(probs, min(args.top_k, probs.size(-1)))
                    probs[probs < v[-1]] = 0.0
                if 0.0 < args.top_p < 1.0:
                    sorted_probs, sorted_indices = torch.sort(probs, descending=True)
                    cumsum_probs = torch.cumsum(sorted_probs, dim=-1)
                    mask = cumsum_probs > args.top_p
                    mask[..., 1:] = mask[..., :-1].clone()
                    mask[..., 0] = 0
                    probs[sorted_indices[mask]] = 0.0
                probs_sum = probs.sum()
                if probs_sum > 0:
                    probs /= probs_sum
                next_token = torch.multinomial(probs, num_samples=1)

            context = torch.cat((context, next_token.unsqueeze(0)), dim=1)
            generated.append(next_token.item())

    print("device=" + device.type)
    print("generated_ids=" + ",".join(str(x) for x in generated))


if __name__ == "__main__":
    main()
