#!/usr/bin/env python3
"""Isolated gfx803 TopK semantic matrix; no release or training admission.

The known native TopK fault can wedge hardware. Use ONLY the patched wheel,
with kernel logging, on a controlled host. One subprocess per case.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

# 120 cases: dtype x width/k x direction x output-order x values.
CASES=[(dt,n,k,largest,ordered,pattern)
       for dt in ("float32","float16")
       for n,k in ((4,1),(4,2),(4,4),(8,3),(64,8))
       for largest in (True,False)
       for ordered in (True,False)
       for pattern in ("unique","ties","nan")]

def label(c):
    dt,n,k,largest,ordered,pattern=c
    return f"{dt}-2x{n}-k{k}-{'largest' if largest else 'smallest'}-{'sorted' if ordered else 'unsorted'}-{pattern}"

def values(c,torch):
    dt,n,k,largest,ordered,pattern=c
    x=torch.arange(2*n,dtype=getattr(torch,dt)).reshape(2,n)/(2*n)
    if pattern=="ties":x=torch.floor(x*4)
    if pattern=="nan":
        x[0,0]=float("nan")
        x[1,-1]=float("nan")
    return x

def exercise(c,torch):
    dt,n,k,largest,ordered,pattern=c
    cpu=values(c,torch)
    ref,ref_idx=torch.topk(cpu,k,dim=1,largest=largest,sorted=ordered)
    reps=[]
    for i in range(3):
        v,idx=torch.topk(cpu.cuda(),k,dim=1,largest=largest,sorted=ordered)
        torch.cuda.synchronize()
        reps.append((v.cpu(),idx.cpu()))
    def legal(v,idx):
        if idx.shape!=(2,k) or v.shape!=(2,k):return False
        if not bool(((idx>=0)&(idx<n)).all()):return False
        if any(len(set(row.tolist()))!=k for row in idx):return False
        if not bool(torch.allclose(cpu.gather(1,idx),v,atol=0,rtol=0,equal_nan=True)):return False
        # Index identity on ties is deliberately not required.
        a=torch.sort(v,dim=1)[0]
        b=torch.sort(ref,dim=1)[0]
        if not bool(torch.allclose(a,b,atol=0,rtol=0,equal_nan=True)):return False
        if ordered and pattern!="nan":
            monotone=(v[:,1:]<=v[:,:-1]) if largest else (v[:,1:]>=v[:,:-1])
            if not bool(monotone.all()):return False
        return True
    parity=all(legal(*r) for r in reps)
    deterministic=all(torch.equal(reps[0][1],idx) and
                      torch.allclose(reps[0][0],v,atol=0,rtol=0,equal_nan=True)
                      for v,idx in reps[1:])
    # Compare analytic scatter gradients independently for CPU and HIP.
    grad_ok=True
    for device in ("cpu","cuda"):
        x=cpu.to(device).detach().clone().requires_grad_(True)
        v,idx=torch.topk(x,k,dim=1,largest=largest,sorted=ordered)
        v.backward(torch.ones_like(v))
        expected=torch.zeros_like(x).scatter_(1,idx,1)
        if not torch.equal(x.grad,expected):grad_ok=False
    torch.cuda.synchronize()
    return {"passed":parity and grad_ok,"valid_values_and_indices":parity,
            "analytic_backward":grad_ok,"repeats_same_indices":bool(deterministic),
            "indices_equal_cpu":all(torch.equal(idx,ref_idx) for _,idx in reps),
            "tie_or_nan_policy":"CPU multiset parity; exact tie/NaN index matching not required"}

def worker(index,root):
    import torch
    row={"case":label(CASES[index]),"status":"fail"}
    try:
        props=torch.cuda.get_device_properties(0)
        arch=getattr(props,"gcnArchName",None) or getattr(props,"gcn_arch_name",None)
        if not torch.version.hip or not str(arch).startswith("gfx803"):
            raise RuntimeError("HIP gfx803 required")
        row.update({"arch":str(arch),"torch":torch.__version__,"hip":torch.version.hip})
        row["checks"]=exercise(CASES[index],torch)
        mapped=sorted(set(line.split()[-1] for line in Path("/proc/self/maps").read_text().splitlines()
                          if len(line.split())>=6 and
                          any(lib in line.split()[-1] for lib in
                              ("libamdhip64.so","librocblas.so","libhsa-runtime64.so"))))
        expected=os.path.realpath(root).rstrip("/")+"/"
        row["mapped_rocm"]=mapped
        row["runtime_coherent"]=bool(mapped) and all(os.path.realpath(m).startswith(expected) for m in mapped)
        row["status"]="pass" if row["checks"]["passed"] and row["runtime_coherent"] else "fail"
    except Exception as exc:row["error"]=repr(exc)
    print(json.dumps(row,sort_keys=True),flush=True)
    return 0 if row["status"]=="pass" else 1

def write(path,obj):
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n")
    os.replace(tmp,path)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rocm-root",required=True)
    p.add_argument("--out",type=Path)
    p.add_argument("--timeout",type=int,default=45)
    p.add_argument("--worker",type=int,choices=range(len(CASES)))
    p.add_argument("--continue-after-fault",action="store_true")
    a=p.parse_args()
    if a.worker is not None:return worker(a.worker,a.rocm_root)
    if a.timeout<1 or a.out is None:p.error("--out and positive timeout required")
    if not a.rocm_root.startswith("/nix/store/") or not Path(a.rocm_root).is_dir():
        p.error("existing candidate Nix ROCm root required")
    if a.out.exists():p.error("output exists; refusing overwrite")
    a.out.mkdir(parents=True)
    report={"schema":1,"scope":"candidate-only","rocm_root":a.rocm_root,
            "python":sys.executable,"training_admitted":False,"release_admitted":False,
            "cases":{label(c):{"status":"unassayed"} for c in CASES}}
    write(a.out/"matrix.json",report)
    for i,c in enumerate(CASES):
        name=label(c)
        t=time.monotonic()
        try:
            z=subprocess.run([sys.executable,str(Path(__file__).resolve()),"--worker",str(i),
                              "--rocm-root",a.rocm_root],
                             capture_output=True,text=True,timeout=a.timeout,
                             env={**os.environ,"PYTHONNOUSERSITE":"1"})
            (a.out/(name+".stderr")).write_text(z.stderr)
            row=json.loads(z.stdout.splitlines()[-1])
            status=row["status"]
            if z.returncode not in (0,1) or z.returncode != (0 if status=="pass" else 1):
                status="fault";row["returncode"]=z.returncode
        except subprocess.TimeoutExpired:
            status="timeout";row={"reason":"case exceeded timeout"}
        except (ValueError,IndexError,KeyError) as exc:
            status="fault";row={"reason":"missing child receipt","error":repr(exc)}
        report["cases"][name]={"status":status,
                               "seconds":round(time.monotonic()-t,3),"receipt":row}
        write(a.out/"matrix.json",report)
        if status in ("fault","timeout") and not a.continue_after_fault:
            report["stopped_after"]=name
            break
    statuses=[r["status"] for r in report["cases"].values()]
    report["summary"]={key:statuses.count(key) for key in
                       ("pass","fail","timeout","fault","unassayed")}
    report["summary"]["all_selected_cases_pass"]=all(x=="pass" for x in statuses)
    write(a.out/"matrix.json",report)
    return 0 if report["summary"]["all_selected_cases_pass"] else 2
if __name__=="__main__":sys.exit(main())
