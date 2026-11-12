#!/usr/bin/env python3
"""Run ORIGINAL pinned Schaka FP16 GEMM and Triton dot probes on RX 580.

Do not vendor or rewrite upstream operators. Original FP16 sweep contains
27 named cases with its own error threshold. Original Triton dot reports
max_err but DOES NOT itself apply a numerical tolerance: a subprocess
exit 0 is *execution only*, never a numerical pass.
"""
from __future__ import annotations
import argparse
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

PIN="8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78"
SCRIPTS={"fp16-gemm":"tools/correctness-suite/fp16_gemm_sweep.py",
         "triton-dot":"tools/correctness-suite/triton_dot_probe.py"}
STORE=re.compile(r"^/nix/store/[0-9a-z]{32}-[A-Za-z0-9+._?=-]+$")
STATES=("unassayed","interrupted","fault","timeout","source-verified-pass",
        "numeric-unqualified","source-reported-fail","unparseable")

def digest(data):return hashlib.sha256(data).hexdigest()

def source_pin(root):
    root=root.resolve()
    got=subprocess.run(["git","-C",str(root),"rev-parse","HEAD"],capture_output=True,text=True)
    if got.returncode or got.stdout.strip()!=PIN:
        raise ValueError("requires exact pinned Schaka source")
    changed=subprocess.run(["git","-C",str(root),"status","--porcelain","--",
                             "tools/correctness-suite"],capture_output=True,text=True)
    if changed.returncode or changed.stdout.strip():
        raise ValueError("original upstream probe files must be unchanged")
    return root

def inputs(root,suite):
    src=root/SCRIPTS[suite]
    if not src.is_file():raise ValueError("missing original Schaka test source")
    tree=ast.parse(src.read_text())
    name="CASES" if suite=="fp16-gemm" else "DTYPES"
    node=next((s.value for s in tree.body
               if isinstance(s,ast.Assign) and any(
                   isinstance(t,ast.Name) and t.id==name for t in s.targets)),None)
    if node is None:raise ValueError("upstream case list not found")
    if suite=="fp16-gemm":
        cases=ast.literal_eval(node)
        if len(cases)!=27:raise ValueError("unexpected changed FP16 test universe")
        ids=[str(i) for i in range(len(cases))]
    else:
        if not isinstance(node,ast.Dict):raise ValueError("invalid Triton dtype map")
        ids=sorted(ast.literal_eval(key) for key in node.keys)
        if ids!=["bf16","fp16","fp32","i8"]:
            raise ValueError("unexpected Triton dtype universe")
    return src,ids,digest(src.read_bytes())

def checks(wrapper,rocm):
    py=wrapper.resolve();root=rocm.resolve()
    if not str(py).startswith("/nix/store/") or not py.is_file() or not os.access(py,os.X_OK):
        raise ValueError("existing immutable Nix Python wrapper required")
    if not STORE.fullmatch(str(root)) or not root.is_dir():
        raise ValueError("selected Nix ROCm closure required")
    return str(py),str(root)

def save(path,doc):
    tmp=path.with_name(path.name+".tmp")
    with tmp.open("w") as f:
        json.dump(doc,f,sort_keys=True,indent=2);f.write("\n")
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def parse(suite,case,returncode,stdout):
    lines=stdout.decode("utf8","replace").splitlines()
    if suite=="fp16-gemm":
        matches=[]
        for line in lines:
            try:
                x=json.loads(line)
                if isinstance(x,dict) and str(x.get("i"))==case:matches.append(x)
            except json.JSONDecodeError:pass
        if len(matches)!=1:return {"status":"unparseable","reason":"missing exact upstream case JSON"}
        row=matches[0]
        result="source-verified-pass" if returncode==0 and row.get("ok") is True else "source-reported-fail"
        return {"status":result,"upstream":row,"numeric_contract":"original Schaka 0.02+0.02*scale"}
    matches=[]
    for line in lines:
        if not line.startswith("TRITONDOT "):continue
        try:
            x=json.loads(line[len("TRITONDOT "):])
            if x.get("dtype")==case:matches.append(x)
        except json.JSONDecodeError:pass
    if len(matches)!=1:return {"status":"unparseable","reason":"missing exact upstream Triton JSON"}
    row=matches[0]
    result="numeric-unqualified" if returncode==0 and row.get("ok") is True and isinstance(
        row.get("max_err"),(int,float)) else "source-reported-fail"
    return {"status":result,"upstream":row,
            "numeric_contract":"upstream ok only reports execution; max_err not thresholded"}

def run_one(suite,script,wrapper,case,out,index,timeout):
    command=[wrapper,str(script)]
    command+=["--case",case] if suite=="fp16-gemm" else ["--dtype",case]
    env=os.environ.copy()
    for k in ("PYTHONPATH","LD_PRELOAD","LD_LIBRARY_PATH"):
        env.pop(k,None)
    env["PYTHONNOUSERSITE"]="1"
    stdout=out/f"{index:04d}.stdout";stderr=out/f"{index:04d}.stderr"
    start=time.monotonic()
    with stdout.open("wb") as o,stderr.open("wb") as e:
        proc=subprocess.Popen(command,stdout=o,stderr=e,env=env,start_new_session=True)
        try:rc=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL);proc.wait();rc=None
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            raise
    if rc is None:row={"status":"timeout"}
    elif rc<0 or rc>=128:row={"status":"fault","returncode":rc}
    else:row=parse(suite,case,rc,stdout.read_bytes())
    row.update({"returncode":rc,"stdout_file":stdout.name,"stderr_file":stderr.name,
                "stdout_sha256":digest(stdout.read_bytes()),
                "stderr_sha256":digest(stderr.read_bytes()),
                "elapsed_seconds":round(time.monotonic()-start,3)})
    return row

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--suite",required=True,choices=sorted(SCRIPTS))
    p.add_argument("--schaka-source",required=True,type=Path)
    p.add_argument("--python-wrapper",required=True,type=Path)
    p.add_argument("--rocm-root",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--resume",action="store_true")
    p.add_argument("--recovered-after-fault",action="store_true")
    p.add_argument("--batch-size",type=int,default=4)
    p.add_argument("--timeout",type=int,default=120)
    a=p.parse_args(argv)
    if a.batch_size<1 or a.timeout<1:p.error("invalid batch-size/timeout")
    if a.recovered_after_fault and not a.resume:p.error("recovery requires --resume")
    try:
        source=source_pin(a.schaka_source)
        script,ids,script_sha=inputs(source,a.suite)
        wrapper,rocm=checks(a.python_wrapper,a.rocm_root)
    except (ValueError,KeyError,OSError,SyntaxError) as e:p.error(str(e))
    out=a.out.resolve()
    identity={"suite":a.suite,"schaka_source":str(source),"schaka_sha":PIN,
              "upstream_script":str(script),"upstream_script_sha256":script_sha,
              "python_wrapper":wrapper,"rocm_root":rocm,"selected":ids}
    if a.resume:
        if not (out/"matrix.json").is_file():p.error("missing resume receipt")
    elif out.exists():p.error("refuse to overwrite existing receipt")
    else:out.mkdir(parents=True)
    with (out/"runner.lock").open("a+") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:p.error("output already in use")
        matrix=out/"matrix.json"
        if a.resume:
            state=json.loads(matrix.read_text())
            if any(state.get(k)!=value for k,value in identity.items()):
                p.error("source/runtime/case identity drift")
            if set(state.get("cases",{}))!=set(ids) or any(
                r.get("status") not in STATES for r in state["cases"].values()):
                p.error("invalid previous results")
            if state.get("release_admitted") is not False or state.get("gpu_validated") is not False:
                p.error("invalid prior admission flags")
        else:
            state={"schema":1,**identity,"cases":{i:{"status":"unassayed"} for i in ids},
                   "status":"planned","gpu_validated":False,
                   "release_admitted":False,"runtime_coherence_verified":False}
            save(matrix,state)
        if not a.execute:
            print(json.dumps({"suite":a.suite,"collected":len(ids),
                              "gpu_executed":False}))
            return 0
        hazards=[i for i in ids if state["cases"][i]["status"] in
                 ("fault","timeout","interrupted") and i not in
                 state.get("recovery_acknowledged_hazards",[])]
        if hazards and not a.recovered_after_fault:
            p.error("fault/timeout/interruption: inspect GPU before resume")
        if hazards:
            state["recovery_acknowledged_hazards"]=sorted(set(
                state.get("recovery_acknowledged_hazards",[]))|set(hazards))
        done=0
        for n,case in enumerate(ids):
            if state["cases"][case]["status"]!="unassayed":continue
            state["cases"][case]={"status":"interrupted","start_unix":time.time()}
            state["status"]="running";save(matrix,state)
            row=run_one(a.suite,script,wrapper,case,out,n,a.timeout)
            state["cases"][case]=row
            save(matrix,state)
            done+=1
            if row["status"] in ("fault","timeout"):
                state["status"]="halted-for-gpu-inspection";break
            if done>=a.batch_size:break
        else:state["status"]="all-cases-attempted"
        if state["status"]=="running":state["status"]="batch-checkpointed"
        state["counts"]={s:sum(r["status"]==s for r in state["cases"].values())
                         for s in STATES}
        state["gpu_validated"]=False;state["release_admitted"]=False
        save(matrix,state)
        print(json.dumps({"status":state["status"],"executed":done,
                          "counts":state["counts"]},sort_keys=True))
        return 2 if state["status"]=="halted-for-gpu-inspection" else 0

if __name__=="__main__":sys.exit(main())
