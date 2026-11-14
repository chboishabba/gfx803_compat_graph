#!/usr/bin/env python3
"""Build source-owned HIP/HSA smoke, then execute each case in isolated process.

Run existing TheRock/original ROCm rocrtst, kfdtest, HIP-tests with the separate
pinned CTest runner for comprehensive vendor conformance. This small assay
targets WhisperX-derived D2H/H2D, async wait, HSA signal and GPU queue seams.
It NEVER resets the GPU or treats short smoke success as long-workload safety.
"""
from __future__ import annotations
import argparse
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

ROOT=Path(__file__).resolve().parents[1]
NATIVE=ROOT/"qualification/native"
SOURCES={"hip":"gfx803_hip_runtime_smoke.hip.cpp",
         "hsa":"gfx803_hsa_runtime_smoke.cpp"}
CASES={"hip":("h2d-d2h","stream-event-copy","kernel-dispatch","pinned-host-copy"),
       "hsa":("agent-enumeration","signal-wait","queue-create-destroy")}
STATES=("unassayed","interrupted","passed","nonzero-exit","fault","timeout",
        "invalid-output","kernel-fault-observed")
STORE=re.compile(r"^/nix/store/[0-9a-z]{32}-[^/]+$")
FOOT=re.compile(r"^GFX803_ASSAY case=([^ ]+) .*result=PASS$",re.M)

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def persist(path,obj):
    temp=path.with_name(path.name+".tmp")
    with temp.open("w") as f:
        json.dump(obj,f,sort_keys=True,indent=2);f.write("\n")
        f.flush();os.fsync(f.fileno())
    os.replace(temp,path)

def inputs(old_build):
    b=json.loads(old_build.read_text())
    if b.get("source_sha")!="8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78" or b.get("status")!="built":
        raise ValueError("original accepted Schaka MIOpen build receipt required")
    prefix=Path(b["rocm_prefix"]).resolve()
    compiler=Path(b["hipcc"]).resolve()
    if not str(prefix).startswith("/nix/store/") or not str(compiler).startswith("/nix/store/"):
        raise ValueError("immutable Nix ROCm and hipcc required")
    if not compiler.is_file() or digest(compiler)!=b["hipcc_sha256"]:
        raise ValueError("pinned compiler unavailable/changed")
    for lib in ("libamdhip64.so","libhsa-runtime64.so"):
        if not (prefix/"lib"/lib).exists():
            raise ValueError("missing direct-runtime library "+lib)
    for hdr in ("hip/hip_runtime.h","hsa/hsa.h"):
        if not (prefix/"include"/hdr).exists():
            raise ValueError("missing matching development header "+hdr)
    return str(prefix),str(compiler),b

def child(command,cwd,env,out,err,timeout):
    with out.open("wb") as stdout,err.open("wb") as stderr:
        p=subprocess.Popen(command,cwd=cwd,env=env,stdout=stdout,
                           stderr=stderr,start_new_session=True)
        try:rc=p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.wait();rc=None
        except BaseException:
            if p.poll() is None:
                os.killpg(p.pid,signal.SIGKILL);p.wait()
            raise
    return rc

def classify(suite,name,rc,stdout,stderr):
    output=(stdout+stderr).decode("utf8","replace")
    base={"returncode":rc}
    if rc is None:return dict(base,status="timeout")
    if rc<0 or rc>=128:return dict(base,status="fault")
    if rc!=0:return dict(base,status="nonzero-exit")
    matches=FOOT.findall(output)
    if matches!=[name]:return dict(base,status="invalid-output",markers=matches)
    if suite=="hip":
        count=re.findall(r"GFX803_ASSAY case="+re.escape(name)+r" count=(\d+) wrong=(\d+)",output)
        if count!=[("8192","0")]:return dict(base,status="invalid-output",numeric=count)
    return dict(base,status="passed")

def build_binaries(out,prefix,compiler,timeout):
    found={}
    for suite,filename in SOURCES.items():
        binary=out/("gfx803_"+suite+"_smoke")
        stdout=out/(suite+".build.stdout")
        stderr=out/(suite+".build.stderr")
        command=[compiler,"-O2","-I"+str(Path(prefix)/"include"),
                 "-L"+str(Path(prefix)/"lib"),
                 "-Wl,-rpath,"+str(Path(prefix)/"lib")]
        if suite=="hip":command+=["-x","hip",str(NATIVE/filename),"-o",str(binary)]
        else:command+=["-x","c++",str(NATIVE/filename),"-o",str(binary),"-lhsa-runtime64"]
        env=os.environ.copy()
        env["PATH"]=str(Path(compiler).parent)+os.pathsep+env.get("PATH","")
        env.pop("LD_PRELOAD",None)
        rc=child(command,out,env,stdout,stderr,timeout)
        found[suite]={"status":"built" if rc==0 and binary.is_file() else "build-failed",
                      "returncode":rc,"binary":str(binary),
                      "sha256":digest(binary) if rc==0 and binary.is_file() else None,
                      "stdout_sha256":digest(stdout),"stderr_sha256":digest(stderr)}
        if found[suite]["status"]!="built":break
    return found

def journal(start,directory):
    path=directory/"kernel-journal.txt"
    try:
        p=subprocess.run(["journalctl","-k","--since",f"@{int(start)-2}",
                          "--no-pager","-o","short-iso"],capture_output=True,timeout=15)
        path.write_bytes(p.stdout+b"\nSTDERR:\n"+p.stderr)
        lines=p.stdout.decode("utf8","replace").splitlines() if p.returncode==0 else []
        faults=[x for x in lines if re.search(
            r"ring gfx timeout|VM_CONTEXT.*PROTECTION_FAULT|page.not.present|"
            r"GPU reset|BACO reset|VRAM is lost|GPU Hang|Oops:|kernel BUG",x,re.I)]
        return {"available":p.returncode==0,"sha256":digest(path),
                "fault_signals":faults[-20:]}
    except (OSError,subprocess.TimeoutExpired) as e:
        path.write_text(str(e))
        return {"available":False,"sha256":digest(path),"fault_signals":[]}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--miopen-build-receipt",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--build",action="store_true")
    p.add_argument("--execute",action="store_true")
    p.add_argument("--resume",action="store_true")
    p.add_argument("--batch-size",type=int,default=2)
    p.add_argument("--timeout",type=int,default=60)
    p.add_argument("--build-timeout",type=int,default=900)
    a=p.parse_args(argv)
    if min(a.batch_size,a.timeout,a.build_timeout)<1:p.error("positive limits required")
    if a.build and a.resume:p.error("build with fresh destination only")
    try:prefix,compiler,prior=inputs(a.miopen_build_receipt)
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as e:p.error(str(e))
    ident={"schema":1,"source_files":{key:digest(NATIVE/file) for key,file in SOURCES.items()},
           "original_build_sha256":digest(a.miopen_build_receipt),
           "rocm_prefix":prefix,"hipcc":compiler,"hipcc_sha256":digest(Path(compiler)),
           "case_order":[f"{k}:{n}" for k,names in CASES.items() for n in names]}
    out=a.out.resolve()
    if a.resume:
        if not (out/"matrix.json").is_file():p.error("resume matrix unavailable")
    elif out.exists():p.error("fresh destination required")
    else:out.mkdir(parents=True)
    with (out/"runner.lock").open("a+") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:p.error("output already owned")
        buildfile=out/"build.json"
        if a.build:
            builds=build_binaries(out,prefix,compiler,a.build_timeout)
            manifest={**ident,"binaries":builds,
                      "status":"built" if set(builds)==set(SOURCES) and
                      all(x["status"]=="built" for x in builds.values()) else "build-failed",
                      "gpu_executed":False,"release_admitted":False}
            persist(buildfile,manifest)
            if manifest["status"]!="built":print(json.dumps(manifest["binaries"]));return 2
        if not buildfile.is_file():p.error("build receipt missing; pass --build on new directory")
        build=json.loads(buildfile.read_text())
        if any(build.get(k)!=v for k,v in ident.items()) or build.get("status")!="built":
            p.error("build source/runtime/case universe drift")
        for suite in SOURCES:
            b=build["binaries"][suite]
            if not Path(b["binary"]).is_file() or digest(Path(b["binary"]))!=b["sha256"]:
                p.error("compiled binary hash mismatch")
        matrix=out/"matrix.json"
        if a.resume:
            state=json.loads(matrix.read_text())
            if any(state.get(k)!=v for k,v in ident.items()):
                p.error("source/runtime/case drift")
            if state.get("build_receipt_sha256")!=digest(buildfile):
                p.error("build receipt drift")
            if state.get("release_admitted") is not False:
                p.error("unexpected promotion")
            if set(state.get("results",{}))!=set(ident["case_order"]) or any(
                v.get("status") not in STATES for v in state["results"].values()):
                p.error("case evidence mismatch")
        else:
            state={**ident,"build_receipt_sha256":digest(buildfile),
                   "results":{name:{"status":"unassayed"} for name in ident["case_order"]},
                   "status":"built-not-executed","gpu_validated":False,
                   "release_admitted":False,"runtime_coherence_verified":False}
            persist(matrix,state)
        if not a.execute:
            print(json.dumps({"cases":len(state["results"]),"gpu_executed":False}));return 0
        if any(v["status"] in ("interrupted","fault","timeout","kernel-fault-observed")
               for v in state["results"].values()):
            p.error("previous fault/interruption; inspect GPU and use a new experiment")
        done=0
        for key in ident["case_order"]:
            if state["results"][key]["status"]!="unassayed":continue
            suite,name=key.split(":",1)
            state["results"][key]={"status":"interrupted","started_unix":time.time()}
            state["status"]="running";persist(matrix,state)
            case_dir=out/(f"case_{len([x for x in state['results'] if x<key])}_{suite}_{name}")
            case_dir.mkdir()
            env=os.environ.copy()
            env.pop("LD_PRELOAD",None)
            old=env.get("LD_LIBRARY_PATH","")
            env["LD_LIBRARY_PATH"]=str(Path(prefix)/"lib")+(os.pathsep+old if old else "")
            env["HSA_ENABLE_SDMA"]=env.get("HSA_ENABLE_SDMA","1")
            start=time.time()
            b=build["binaries"][suite]
            rc=child([b["binary"],name],case_dir,env,case_dir/"stdout",case_dir/"stderr",a.timeout)
            result=classify(suite,name,rc,(case_dir/"stdout").read_bytes(),
                            (case_dir/"stderr").read_bytes())
            result["kernel_journal"]=journal(start,case_dir)
            if result["kernel_journal"]["fault_signals"] and result["status"]=="passed":
                result["status"]="kernel-fault-observed"
            result.update({"dir":case_dir.name,
                           "stdout_sha256":digest(case_dir/"stdout"),
                           "stderr_sha256":digest(case_dir/"stderr"),
                           "elapsed_seconds":round(time.time()-start,3)})
            state["results"][key]=result;persist(matrix,state);done+=1
            if result["status"]!="passed":
                state["status"]="halted-for-investigation";break
            if done>=a.batch_size:break
        else:state["status"]="all-cases-attempted"
        if state["status"]=="running":state["status"]="batch-checkpointed"
        state["counts"]={k:sum(r["status"]==k for r in state["results"].values()) for k in STATES}
        state["gpu_validated"]=False;state["release_admitted"]=False
        persist(matrix,state)
        print(json.dumps({"status":state["status"],"executed":done,"counts":state["counts"]}))
        return 2 if state["status"]=="halted-for-investigation" else 0
if __name__=="__main__":sys.exit(main())
