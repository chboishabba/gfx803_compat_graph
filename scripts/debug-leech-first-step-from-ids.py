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


def load_model(checkpoint_path: str, device: torch.device, vocab_size: int):
    cfg = LeechConfig(vocab_size=vocab_size)
    model = LeechGPT(cfg).to(device)
    checkpoint = load_checkpoint_compat(checkpoint_path, device)
    model.load_state_dict(extract_model_state_dict(checkpoint))
    model.eval()
    return model


def first_step_logits(model: LeechGPT, prompt_ids):
    idx = torch.tensor([prompt_ids], dtype=torch.long, device=next(model.parameters()).device)
    with torch.no_grad():
        logits, _, _, _ = model(idx, use_cache=False, past_key_values=None)
    return logits[0, -1, :].detach().float().cpu()


def topk_pairs(logits: torch.Tensor, k: int):
    vals, idxs = torch.topk(logits, k)
    return list(zip(idxs.tolist(), vals.tolist()))


def main():
    parser = argparse.ArgumentParser(description="Compare first-step Leech CPU/GPU logits from pre-encoded prompt ids.")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--vocab-size", type=int, required=True)
    parser.add_argument("--prompt-ids", required=True)
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()

    prompt_ids = [int(x) for x in args.prompt_ids.split(",") if x.strip()]
    cpu_model = load_model(args.checkpoint, torch.device("cpu"), args.vocab_size)
    gpu_model = load_model(args.checkpoint, torch.device("cuda"), args.vocab_size)

    cpu_logits = first_step_logits(cpu_model, prompt_ids)
    gpu_logits_runs = [first_step_logits(gpu_model, prompt_ids) for _ in range(args.repeats)]
    gpu_logits = gpu_logits_runs[0]

    diff = (cpu_logits - gpu_logits).abs()
    print(f"max_abs_diff={diff.max().item():.9f}")
    print(f"argmax_cpu={int(cpu_logits.argmax().item())}")
    print(f"argmax_gpu={int(gpu_logits.argmax().item())}")
    print("cpu_topk=" + repr(topk_pairs(cpu_logits, args.topk)))
    print("gpu_topk=" + repr(topk_pairs(gpu_logits, args.topk)))
    for idx, logits in enumerate(gpu_logits_runs[1:], start=2):
        intra = (gpu_logits - logits).abs().max().item()
        print(f"intra_gpu_run{idx}_max_abs_diff={intra:.9f}")
        print(f"argmax_gpu_run{idx}={int(logits.argmax().item())}")


if __name__ == "__main__":
    main()
