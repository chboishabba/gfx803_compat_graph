#!/usr/bin/env python3
"""Isolated, opt-in RX 580 complex unary fault reproducer.

A single test per process. Do NOT run on a live training host or before
recovering from the previous VM fault. This is a differential diagnosis,
not a workaround, release test, or claim that CPU/GPU results will agree.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OPS=("acos","acosh","asin","asinh","atan","atanh","sin","sinh","cos","cosh","log","sqrt")
PROFILES=("complex64-contiguous","complex64-strided","complex64-empty",
          "complex128-contiguous","float32-contiguous")
def sample(torch,profile):
    if profile=="complex64-empty":
        return torch.empty(0,dtype=torch.complex64)
    if profile.endswith("-strided"):
        base=torch.tensor([complex(0.2,0.3),complex(-0.4,0.1),
                           complex(1.2,-0.2),complex(-1.1,0.4),
                           complex(0.1,-0.5),complex(-0.2,-0.2)],
                          dtype=torch.complex64)
        return base[::2]
    if profile.startswith("complex128"):
        dtype=torch.complex128
    elif profile.startswith("complex64"):
        dtype=torch.complex64
    else:
        return torch.tensor([0.25,0.5,0.75],dtype=torch.float32)
    return torch.tensor([complex(0.2,0.3), complex(-0.4,0.1),
                         complex(1.2,-0.2)],dtype=dtype)

def worker(op,profile,rocm):
    import torch
    props=torch.cuda.get_device_properties(0)
    arch=getattr(props,"gcnArchName",None) or getattr(props,"gcn_arch_name",None)
    if not torch.version.hip or not str(arch).startswith("gfx803"):
        raise RuntimeError("require actual HIP gfx803")
    cpu=sample(torch,profile)
    f=getattr(torch,op)
    expected=f(cpu)
    torch.cuda.synchronize()
    actual=f(cpu.cuda())
    torch.cuda.synchronize()
    actual=actual.cpu()
    ok=bool(torch.allclose(actual,expected,atol=2e-5,rtol=2e-5,equal_nan=True))
    maps=Path("/proc/self/maps").read_text().splitlines()
    libs=sorted({s[-1] for line in maps if len(s:=line.split())>=6 and
                 any(t in s[-1] for t in ("libamdhip64.so","libhsa-runtime64.so","librocblas.so"))})
    expected_root=str(Path(rocm).resolve())+"/"
    coherent=bool(libs) and all(str(Path(x).resolve()).startswith(expected_root) for x in libs)
    return {"operation":op,"profile":profile,"torch":torch.__version__,
            "hip":torch.version.hip,"arch":str(arch),"forward_parity":ok,
            "runtime_coherent":coherent,"mapped_libraries":libs,
            "expected_shape":list(expected.shape),
            "status":"pass" if ok and coherent else "fail"}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--python-wrapper",type=Path,required=True)
    p.add_argument("--rocm-root",type=Path,required=True)
    p.add_argument("--op",required=True,choices=OPS)
    p.add_argument("--profile",required=True,choices=PROFILES)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--timeout",type=int,default=40)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    a=p.parse_args()
    if a.timeout<=0:p.error("positive timeout required")
    if a.worker:
        try:
            print(json.dumps(worker(a.op,a.profile,str(a.rocm_root)),sort_keys=True),flush=True)
            return 0
        except Exception as e:
            print(json.dumps({"status":"fail","error":repr(e)}),flush=True)
            return 1
    if a.out.exists():p.error("output exists: original logs immutable")
    root=a.rocm_root.resolve()
    wrapper=a.python_wrapper.resolve()
    if not str(root).startswith("/nix/store/") or not root.is_dir():
        p.error("selected immutable ROCm closure required")
    if not str(wrapper).startswith("/nix/store/") or not wrapper.is_file():
        p.error("selected immutable PyTorch wrapper required")
    a.out.mkdir(parents=True)
    receipt={"schema":1,"status":"not-executed","operation":a.op,"profile":a.profile,
             "python_wrapper":str(wrapper),"rocm_root":str(root),
             "hardware_fault_not_excluded":True,"release_admitted":False}
    path=a.out/"receipt.json"
    path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    if not a.execute:
        print("SOURCE/ARGUMENTS ONLY. Pass --execute after host recovery review.")
        return 0
    cmd=[str(wrapper),str(Path(__file__).resolve()),"--worker",
         "--python-wrapper",str(wrapper),"--rocm-root",str(root),
         "--op",a.op,"--profile",a.profile,"--out",str(a.out)]
    env=os.environ.copy()
    for key in ("PYTHONPATH","LD_LIBRARY_PATH","LD_PRELOAD"):
        env.pop(key,None)
    env["PYTHONNOUSERSITE"]="1"
    receipt["status"]="interrupted"
    path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    t=time.monotonic()
    try:
        result=subprocess.run(cmd,capture_output=True,timeout=a.timeout,env=env)
        (a.out/"stdout.log").write_bytes(result.stdout)
        (a.out/"stderr.log").write_bytes(result.stderr)
        receipt["returncode"]=result.returncode
        try:child=json.loads(result.stdout.decode("utf-8","replace").splitlines()[-1])
        except (IndexError,ValueError):child={"status":"fault","error":"missing JSON child output"}
        receipt["child"]=child
        receipt["status"]="fault" if result.returncode<0 or result.returncode>=128 else child.get("status","fault")
    except subprocess.TimeoutExpired as exc:
        receipt["status"]="timeout"
        (a.out/"stdout.log").write_bytes(exc.stdout or b"")
        (a.out/"stderr.log").write_bytes(exc.stderr or b"")
    receipt["elapsed_seconds"]=round(time.monotonic()-t,3)
    for name in ("stdout.log","stderr.log"):
        receipt[name+"_sha256"]=digest(a.out/name)
    path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    print(json.dumps(receipt,sort_keys=True))
    return 0 if receipt["status"]=="pass" else 2
if __name__=="__main__":sys.exit(main())
