#!/usr/bin/env python3
"""Fail-closed runtime environment contract for Schaka's OCI-to-Nix import.

Schaka's final ROCm 10.x image depends on an FP32 SGEMM LD_PRELOAD shim
*in addition* to its ISA803 assembly WorkGroupMapping patch. Copying
/opt/rocm into Nix without re-expressing this environment is NOT
functionally equivalent to the original tested container.

This static inspection checks the publisher's declared OCI environment
and staged in-tree shim, but CANNOT claim that a real host successfully
preloaded it or passed gfx803 hardware tests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SHIM_OCI = "/opt/rocm/lib/libgfx803_sgemm_shim.so"
REQUIRED_IMAGE_ENV = {
    "HSA_OVERRIDE_GFX_VERSION": "8.0.3",
    "ROC_ENABLE_PRE_VEGA": "1",
    "TORCH_BLAS_PREFER_HIPBLASLT": "0",
    "LD_PRELOAD": SHIM_OCI,
}


class RuntimeEnvironmentError(ValueError):
    pass


def inspect_env_values(inspection: dict) -> dict[str, str]:
    values = inspection.get("Env")
    if not isinstance(values, list):
        raise RuntimeEnvironmentError("OCI inspect must contain an Env list")
    parsed: dict[str, str] = {}
    for item in values:
        if not isinstance(item, str) or "=" not in item:
            raise RuntimeEnvironmentError("malformed OCI Env entry")
        name, value = item.split("=", 1)
        if name in parsed:
            raise RuntimeEnvironmentError("duplicate OCI environment entry: " + name)
        parsed[name] = value
    return parsed


def inspect_runtime(inspection: dict, *, rocm_stage: Path | None = None,
                    rocm_store: str | None = None) -> dict:
    values = inspect_env_values(inspection)
    for name, wanted in REQUIRED_IMAGE_ENV.items():
        if values.get(name) != wanted:
            raise RuntimeEnvironmentError(
                f"required image runtime environment mismatch: {name} "
                f"observed={values.get(name)!r} expected={wanted!r}")
    if values.get("GFX803_SGEMM_SHIM_DISABLE") not in (None, "0", ""):
        raise RuntimeEnvironmentError("published image disables required SGEMM shim")
    if rocm_stage is not None:
        stage = Path(rocm_stage)
        shim = stage / "lib/libgfx803_sgemm_shim.so"
        openblas_alias = stage / "lib/libopenblas.so.0"
        # This test deliberately follows only the selected staged Nix subtree.
        if not shim.is_file():
            raise RuntimeEnvironmentError("staged ROCm tree lacks the SGEMM preload library")
        if not shim.resolve().is_relative_to(stage.resolve()):
            raise RuntimeEnvironmentError("SGEMM preload escapes selected staged ROCm tree")
        if not openblas_alias.is_file() or not openblas_alias.resolve().is_relative_to(stage.resolve()):
            raise RuntimeEnvironmentError("staged ROCm tree lacks in-tree OpenBLAS compatibility alias")
    if rocm_store is not None and not rocm_store.startswith("/nix/store/"):
        raise RuntimeEnvironmentError("expected canonical Nix store runtime root")
    nix_shim = f"{rocm_store}/lib/libgfx803_sgemm_shim.so" if rocm_store else None
    return {
        "schema_version": 1,
        "source": "Schaka original published OCI image Env",
        "validated_required_container_environment": dict(REQUIRED_IMAGE_ENV),
        "shim_enabled_in_image": True,
        "shim_container_path": SHIM_OCI,
        "shim_nix_preload_path": nix_shim,
        "shim_staged_file_observed": rocm_stage is not None,
        "openblas_compatibility_alias": (
            f"{rocm_store}/lib/libopenblas.so.0" if rocm_store else None),
        "runtime_relocation": "unverified",
        "runtime_preload_execution": "unverified",
        "gpu_numerical_parity": "unverified",
        "notes": [
            "WGM8 assembly miscompute and pervasive FP32 SGEMM miscompute are distinct.",
            "A Nix consumer must preload the relocated shim, not the original /opt path.",
            "Preload candidate rocBLAS before the shim to prevent its /opt RUNPATH selecting host ROCm.",
            "Do not append arbitrary foreign LD_PRELOAD libraries to the accepted runtime.",
            "GFX803_SGEMM_SHIM_DISABLE=1 is for isolated negative-control tests only.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inspect", type=Path, required=True)
    p.add_argument("--stage", type=Path)
    p.add_argument("--store", type=str)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        result = inspect_runtime(json.loads(args.inspect.read_text()),
                                 rocm_stage=args.stage, rocm_store=args.store)
    except (RuntimeEnvironmentError, ValueError, OSError) as exc:
        p.exit(3, f"NOT EQUIVALENT TO SCHAKA OCI: {exc}\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(str(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
