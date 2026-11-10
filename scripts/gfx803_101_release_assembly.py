#!/usr/bin/env python3
"""Candidate-only Schaka 10.1 + patched torch attestation. Never publish/promote.

Checks exact image, imported store roots, wheel bytes and torch wheel identity.
Creates a machine-readable assembly receipt; no writes into the Nix store.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

WHEEL_STORE="/nix/store/0l9bysk6xfx9dsndx9diwqf44x0h6zf2-torch-2.14.0-gfx803-topk-sort-fallback-20261110"
WHEEL_SHA256="0968548982ba69858d2dfe4ec0090ef1ce41ed610f0f9b3b9f38aebe0f0319eb"
IMAGE="ghcr.io/schaka/rocm-migraphx-ort-torch-builder@sha256:60ac8963d7d43899d242973e1a346233f350816971419f423883a46609b116ca"
SOURCE_REV="8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78"
TORCH_REV="d70fd61bab718a3d49b053efa8058efc0566b2b0"
STORE=re.compile(r"^/nix/store/[0-9a-z]{32}-[A-Za-z0-9+._?=-]+$")

def store_path(value):
    if not isinstance(value,str) or not STORE.fullmatch(value):
        raise ValueError("noncanonical Nix store path: "+repr(value))
    return Path(value)

def validate_selector(s, wheel_store=WHEEL_STORE):
    if s.get("immutable_image") != IMAGE or s.get("source_revision") != SOURCE_REV:
        raise ValueError("source/image do not match the pinned Schaka 10.1 runtime")
    rocm=store_path(s.get("rocm_root"))
    venv=store_path(s.get("venv_root"))
    wheel=store_path(wheel_store)
    if s.get("shim")!=str(rocm/"lib/libgfx803_sgemm_shim.so"):
        raise ValueError("SGEMM shim mismatch")
    python=s.get("chosen_python")
    if not isinstance(python,str) or not python.startswith(str(venv)+"/"):
        raise ValueError("Python not within imported venv")
    if s.get("required_ld_library_path")!=[str(rocm/"lib"),str(rocm/"core-10.1/lib")]:
        raise ValueError("mixed or missing ROCm library paths")
    return {"schema":1,"state":"candidate-not-admitted",
            "original_image":IMAGE,"upstream_source":SOURCE_REV,
            "pytorch_source":TORCH_REV,"rocm_store":str(rocm),
            "venv_store":str(venv),"wheel_store":str(wheel),
            "wheel_sha256":WHEEL_SHA256,
            "gpu_training_admitted":False,"release_admitted":False,
            "unpaid_checks":["full-topk-semantics", "operator-conformance",
                             "long-run-gpu-stability","clean-client-nix-restore",
                             "strict-original-evidence-promotion"]}

def inspect_wheel(path):
    wheels=sorted(path.rglob("*.whl")) if path.is_dir() else ([path] if path.suffix==".whl" else [])
    if len(wheels)!=1:
        raise ValueError("require exactly one published wheel")
    wheel=wheels[0]
    digest=hashlib.sha256(wheel.read_bytes()).hexdigest()
    if digest!=WHEEL_SHA256:
        raise ValueError("wheel SHA256 differs from upstream PR #8 validated artifact")
    with zipfile.ZipFile(wheel) as z:
        if not wheel.name.startswith("torch-2.14.0") or sum(n.endswith(".dist-info/WHEEL") for n in z.namelist())!=1:
            raise ValueError("wrong wheel identity")
    return {"file":str(wheel),"sha256":digest,"bytes":wheel.stat().st_size}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selector",type=Path,required=True)
    p.add_argument("--wheel-store",default=WHEEL_STORE)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():p.error("output exists: refusing evidence overwrite")
    try:
        s=json.loads(a.selector.read_text())
        manifest=validate_selector(s,a.wheel_store)
        for key in ("rocm_store","venv_store","wheel_store"):
            if not Path(manifest[key]).exists():raise ValueError("store path absent: "+key)
        manifest["wheel"]=inspect_wheel(Path(manifest["wheel_store"]))
        manifest["selector_sha256"]=hashlib.sha256(a.selector.read_bytes()).hexdigest()
        manifest["upstream_pr"]="https://github.com/Schaka/rocm-gfx803/pull/8"
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
        print("CANDIDATE ONLY:",a.out)
    except (ValueError,OSError,KeyError,zipfile.BadZipFile) as exc:p.error(str(exc))
if __name__=="__main__":main()
