#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

import torch


THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[1]
LEECH_ROOT = Path("/home/c/Documents/code/DASHIg/LeechTransformer")
if str(LEECH_ROOT) not in sys.path:
    sys.path.insert(0, str(LEECH_ROOT))
if str(LEECH_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(LEECH_ROOT / "scripts"))

from config.config import LeechConfig
from inference.generate import generate
from models.model import LeechGPT
from run_inference import _extract_model_state_dict, _load_checkpoint_compat
from tokenizer.tokenizer_utils import load_tokenizer


def load_model(checkpoint_path: str, device: torch.device):
    sp = load_tokenizer()
    cfg = LeechConfig(vocab_size=sp.get_piece_size())
    model = LeechGPT(cfg).to(device)
    checkpoint = _load_checkpoint_compat(checkpoint_path, device)
    model_state_dict = _extract_model_state_dict(checkpoint)
    model.load_state_dict(model_state_dict)
    model.eval()
    return model, sp


def run_generation(device: torch.device, checkpoint_path: str, prompt: str, max_tokens: int, use_kv_cache: bool):
    model, sp = load_model(checkpoint_path, device)
    text = generate(
        model,
        sp,
        start_str=prompt,
        max_tokens=max_tokens,
        temperature=1.0,
        top_k=1,
        top_p=1.0,
        repetition_penalty=1.0,
        repetition_window=1,
        device=device,
        use_resonator=False,
        use_kv_cache=use_kv_cache,
        return_stats=False,
        print_tokens=False,
    )
    return text


def inspect_first_step(device: torch.device, checkpoint_path: str, prompt: str):
    model, sp = load_model(checkpoint_path, device)
    prompt_ids = sp.encode(prompt)
    if not prompt_ids:
        prompt_ids = [sp.bos_id() if sp.bos_id() != -1 else sp.unk_id()]
    context = torch.tensor([prompt_ids], dtype=torch.long, device=device)
    with torch.no_grad():
        logits, _, _, _ = model(context, use_resonator=False, use_cache=False, past_key_values=None)
    next_logits = logits[0, -1, :].detach().float().cpu()
    values, indices = torch.topk(next_logits, 5)
    top = []
    for score, idx in zip(values.tolist(), indices.tolist()):
        top.append((idx, sp.id_to_piece(idx), score))
    return next_logits, top


def first_difference(a: str, b: str):
    limit = min(len(a), len(b))
    for idx in range(limit):
        if a[idx] != b[idx]:
            return idx
    if len(a) != len(b):
        return limit
    return -1


def main():
    parser = argparse.ArgumentParser(description="Compare Leech CPU vs GPU deterministic output.")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max_tokens", type=int, default=64)
    parser.add_argument("--kv_cache", action="store_true")
    args = parser.parse_args()

    cpu_device = torch.device("cpu")
    gpu_device = torch.device("cuda")

    cpu_text = run_generation(cpu_device, args.checkpoint, args.prompt, args.max_tokens, args.kv_cache)
    gpu_text = run_generation(gpu_device, args.checkpoint, args.prompt, args.max_tokens, args.kv_cache)
    cpu_logits, cpu_top = inspect_first_step(cpu_device, args.checkpoint, args.prompt)
    gpu_logits, gpu_top = inspect_first_step(gpu_device, args.checkpoint, args.prompt)

    diff_at = first_difference(cpu_text, gpu_text)
    print(f"cpu_text={cpu_text!r}")
    print(f"gpu_text={gpu_text!r}")
    print(f"first_difference={diff_at}")
    print(f"first_step_max_abs_logit_diff={(cpu_logits - gpu_logits).abs().max().item():.6f}")
    print(f"cpu_top5={cpu_top!r}")
    print(f"gpu_top5={gpu_top!r}")
    if diff_at >= 0:
        start = max(0, diff_at - 20)
        end = diff_at + 20
        print(f"cpu_window={cpu_text[start:end]!r}")
        print(f"gpu_window={gpu_text[start:end]!r}")


if __name__ == "__main__":
    main()
