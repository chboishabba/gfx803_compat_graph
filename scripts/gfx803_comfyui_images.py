#!/usr/bin/env python3
"""Recheck the original ComfyUI 5.7-good/6.4-bad image class on patched 10.1.

User-supplied *actual* output images and exact workflow/model/seed are
mandatory. Pixel comparison is a bounded image canary, not a proof of
universal neural-network correctness. Tolerances must be selected explicitly
for the matched workflow before declaring a pass.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def sha256_file(path: Path) -> str:
    dig = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            dig.update(block)
    return dig.hexdigest()


def normalized_rmse(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        raise ValueError("Image dimensions differ across matched ComfyUI runs")
    # Compare the same three visible colour channels; no alpha compositing.
    rgb_a, rgb_b = a.convert("RGB"), b.convert("RGB")
    rms = ImageStat.Stat(ImageChops.difference(rgb_a, rgb_b)).rms
    return math.sqrt(sum(x * x for x in rms) / 3.0) / 255.0


def compare(reference: Path, broken: Path, candidate: Path, *,
            workflow: Path, model: Path, seed: int,
            max_rmse: float, improvement_ratio: float) -> dict:
    if not 0 <= max_rmse < 1:
        raise ValueError("max_rmse must be explicit within [0,1)")
    if not 0 <= improvement_ratio < 1:
        raise ValueError("improvement_ratio must be within [0,1)")
    sources = {"reference_rocm57": reference, "broken_rocm64": broken,
               "candidate_rocm101": candidate}
    if len({str(Path(p).resolve()) for p in sources.values()}) != 3:
        raise ValueError("need three distinct source images")
    with (Image.open(reference) as ref, Image.open(broken) as bad,
          Image.open(candidate) as new):
        if ref.size != bad.size or ref.size != new.size:
            raise ValueError("matched ComfyUI images must share dimensions")
        baseline_drift = normalized_rmse(ref, bad)
        candidate_drift = normalized_rmse(ref, new)
        dimensions = ref.size
    if baseline_drift == 0:
        raise ValueError("broken 6.4 reference equals good 5.7 reference; invalid negative control")
    allowed_ratio = improvement_ratio * baseline_drift
    passed = candidate_drift <= max_rmse and candidate_drift < allowed_ratio
    return {
        "schema_version": 1,
        "test": "first-party-comfyui-image-regression-replay",
        "status": "pass" if passed else "fail",
        "origin": "gfx803_compat_graph and prior gfx803 ComfyUI testing",
        "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "workflow_sha256": sha256_file(workflow),
        "model_sha256": sha256_file(model),
        "seed": seed,
        "dimensions": list(dimensions),
        "image_sha256": {key: sha256_file(path) for key, path in sources.items()},
        "normalized_rmse_bad_64_vs_good_57": baseline_drift,
        "normalized_rmse_candidate_101_vs_good_57": candidate_drift,
        "selected_max_rmse": max_rmse,
        "selected_improvement_ratio": improvement_ratio,
        "accepted_only_if": "candidate <= max_rmse and candidate < improvement_ratio * historical_bad",
        "scope": "matched model/seed/workflow/image only",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference57", type=Path, required=True)
    p.add_argument("--broken64", type=Path, required=True)
    p.add_argument("--candidate101", type=Path, required=True)
    p.add_argument("--workflow", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--max-rmse", type=float, required=True,
                   help="explicit normalized pixel RMSE tolerance; not inferred")
    p.add_argument("--improvement-ratio", type=float, default=0.5,
                   help="must be strictly closer to good image than this fraction of old bad drift")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        receipt = compare(args.reference57, args.broken64, args.candidate101,
                          workflow=args.workflow, model=args.model,
                          seed=args.seed, max_rmse=args.max_rmse,
                          improvement_ratio=args.improvement_ratio)
    except (OSError, ValueError) as exc:
        p.exit(2, "NO IMAGE VERDICT: " + str(exc) + "\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print("COMFYUI_IMAGE_RESULT:" + json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "pass" else 3


if __name__ == "__main__":
    raise SystemExit(main())
