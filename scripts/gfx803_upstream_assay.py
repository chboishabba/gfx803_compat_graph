#!/usr/bin/env python3
"""Execute *upstream* PyTorch OpInfo CPU-comparison tests on gfx803.

No PyTorch tests vendored. Collect generated CUDA test IDs first (no kernels);
only --execute permits GPU work. Isolate each selected pytest test in a child
process and persist its result before proceeding. Never implies release admission.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

PIN="d70fd61bab718a3d49b053efa8058efc0566b2b0"
TARGET="test/test_ops.py"
TEMPLATES=("test_compare_cpu","test_variant_consistency_eager")
STORE=re.compile(r"^/nix/store/[0-9a-z]{32}-[A-Za-z0-9+._?=-]+$")

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check_source(source):
    source=source.resolve()
    if not (source/TARGET).is_file():
        raise ValueError("missing pinned PyTorch test/test_ops.py")
    x=subprocess.run(["git","-C",str(source),"rev-parse","HEAD"],capture_output=True,text=True)
    if x.returncode or x.stdout.strip()!=PIN:
        raise ValueError("PyTorch checkout must match exact pinned revision")
    y=subprocess.run(["git","-C",str(source),"status","--porcelain","--",TARGET,
                      "torch/testing/_internal"],capture_output=True,text=True)
    if y.returncode or y.stdout.strip():
        raise ValueError("upstream test sources modified")
    return {"source":str(source),"pytorch_source":PIN,
            "test_sha256":sha(source/TARGET)}

def check_runtime(wrapper,rocm):
    wrapper=wrapper.resolve();rocm=rocm.resolve()
    if not STORE.fullmatch(str(rocm)) or not rocm.is_dir():
        raise ValueError("selected ROCm closure must be an existing Nix store path")
    if not str(wrapper).startswith("/nix/store/") or not wrapper.is_file() or not os.access(wrapper,os.X_OK):
        raise ValueError("must use the immutable composed Python wrapper")
    return {"python_wrapper":str(wrapper),"rocm_root":str(rocm)}

def ids_from_collection(output):
    return sorted(set(line.strip() for line in output.splitlines()
                      if line.strip().startswith("test/test_ops.py::")
                      and "CUDA" in line and "cuda" in line.lower()
                      and any(t in line for t in TEMPLATES)))

def classify(rc,output):
    if rc==0:return "pass"
    if rc<0 or rc>=128:return "fault"
    if re.search(r"\bskipped\b",output,re.I) and "FAILED" not in output:
        return "unsupported"
    return "fail"

def persist(path,data):
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    os.replace(tmp,path)

def clean_env():
    env=os.environ.copy()
    for k in ("PYTHONPATH","LD_LIBRARY_PATH","LD_PRELOAD","PYTEST_ADDOPTS"):
        env.pop(k,None)
    env["PYTHONNOUSERSITE"]="1"
    return env

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--python-wrapper",type=Path,required=True)
    p.add_argument("--rocm-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--max-cases",type=int,default=0,
                   help="0 = all collected tests; use small bound initially")
    p.add_argument("--timeout",type=int,default=180)
    p.add_argument("--continue-after-fault",action="store_true")
    a=p.parse_args(argv)
    if a.max_cases<0 or a.timeout<1:p.error("invalid max-cases/timeout")
    if a.out.exists():p.error("refusing to overwrite prior evidence")
    try:prov={**check_source(a.source),**check_runtime(a.python_wrapper,a.rocm_root)}
    except ValueError as e:p.error(str(e))
    out=a.out.resolve();out.mkdir(parents=True)
    result={"schema":1,"status":"collecting","provenance":prov,
            "claimed_scope":"upstream PyTorch generated CUDA OpInfo CPU comparison",
            "gpu_validated":False,"release_admitted":False,"cases":{}}
    persist(out/"matrix.json",result)
    cmd=[str(a.python_wrapper),"-m","pytest","-q","--collect-only",TARGET,
         "-k"," or ".join(TEMPLATES)]
    try:
        collected=subprocess.run(cmd,cwd=prov["source"],capture_output=True,
                                 text=True,timeout=a.timeout,env=clean_env())
    except subprocess.TimeoutExpired:
        result["status"]="collection-timeout";persist(out/"matrix.json",result);return 2
    (out/"collection.stdout").write_text(collected.stdout)
    (out/"collection.stderr").write_text(collected.stderr)
    ids=ids_from_collection(collected.stdout)
    if collected.returncode or not ids:
        result.update({"status":"collection-failed","returncode":collected.returncode})
        persist(out/"matrix.json",result);return 2
    chosen=ids[:a.max_cases] if a.max_cases else ids
    result.update({"status":"collected","collected_total":len(ids),
                   "selected":chosen,
                   "cases":{node:{"status":"unassayed"} for node in chosen}})
    persist(out/"matrix.json",result)
    if not a.execute:return 0
    result["status"]="running";persist(out/"matrix.json",result)
    for i,node in enumerate(chosen):
        started=time.monotonic()
        try:
            run=subprocess.run([str(a.python_wrapper),"-m","pytest","-q",node],
                               cwd=prov["source"],capture_output=True,text=True,
                               timeout=a.timeout,env=clean_env())
            (out/f"{i:06d}.stdout").write_text(run.stdout)
            (out/f"{i:06d}.stderr").write_text(run.stderr)
            status=classify(run.returncode,run.stdout+"\n"+run.stderr)
            row={"status":status,"returncode":run.returncode,
                 "stdout_sha256":sha(out/f"{i:06d}.stdout"),
                 "stderr_sha256":sha(out/f"{i:06d}.stderr")}
        except subprocess.TimeoutExpired as ex:
            status="timeout";row={"status":status,"error":repr(ex)}
        row["elapsed_seconds"]=round(time.monotonic()-started,3)
        result["cases"][node]=row
        persist(out/"matrix.json",result)
        if status in ("fault","timeout") and not a.continue_after_fault:
            result["stopped_after"]=node;break
    statuses=[row["status"] for row in result["cases"].values()]
    result["counts"]={k:statuses.count(k) for k in
                      ("pass","fail","unsupported","fault","timeout","unassayed")}
    result["status"]="completed" if all(k=="pass" for k in statuses) else "incomplete-or-failed"
    result["gpu_validated"]=result["status"]=="completed"
    persist(out/"matrix.json",result)
    return 0 if result["status"]=="completed" else 2
if __name__=="__main__":sys.exit(main())
