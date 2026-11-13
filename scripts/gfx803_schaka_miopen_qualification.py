#!/usr/bin/env python3
"""Build and qualify the ORIGINAL Schaka MIOpen correctness suite.

Source pinned to Schaka 8fdcf7b. Compiles with upstream build.sh and the
chosen hipcc; runs one original sweep or one forced-convolution solver per
process with checkpointed, original CPU-reference receipts. No Docker.
No unverified source copying, test selection, auto GPU resets or promotions.
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

PIN="8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78"
DIR="tools/correctness-suite"
OPS=("activ_sweep","pool_sweep","bn_sweep","softmax_sweep",
     "layernorm_sweep","groupnorm_sweep","tensorop_sweep","reduce_sweep",
     "reduce_extreme_sweep","glu_sweep","cat_sweep","rope_sweep",
     "kthvalue_sweep")
EXPECTED=OPS+("conv_solver_sweep",)
BETA=("reduce_sweep","reduce_extreme_sweep","layernorm_sweep",
      "groupnorm_sweep","glu_sweep","cat_sweep","rope_sweep",
      "kthvalue_sweep")
STATES=("unassayed","interrupted","passed","failed","fault","timeout",
        "empty-results","missing-binary")
SUMMARY=re.compile(r"SUMMARY:\s*(\d+)\s+(?:cases|shapes)\s+tested,\s*(\d+)\s+WRONG")
STORE=re.compile(r"^/nix/store/[0-9a-z]{32}-[A-Za-z0-9+._?=-]+$")
HAZARDS=("interrupted","fault","timeout")

def sha(data):return hashlib.sha256(data).hexdigest()

def sha_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def persist(path,doc):
    temp=path.with_name(path.name+".tmp")
    with temp.open("w") as f:
        json.dump(doc,f,sort_keys=True,indent=2);f.write("\n")
        f.flush();os.fsync(f.fileno())
    os.replace(temp,path)

def source_identity(source):
    source=source.resolve()
    p=subprocess.run(["git","-C",str(source),"rev-parse","HEAD"],capture_output=True,text=True)
    if p.returncode or p.stdout.strip()!=PIN:
        raise ValueError("Schaka source must be exactly "+PIN)
    suite=source/DIR
    if not (suite/"build.sh").is_file() or not (suite/"run_all.sh").is_file():
        raise ValueError("missing original Schaka correctness suite")
    check=subprocess.run(["git","-C",str(source),"status","--porcelain","--",DIR],
                         capture_output=True,text=True)
    if check.returncode or check.stdout.strip():
        raise ValueError("original Schaka suite is modified or untracked")
    cpp={p.stem:p for p in suite.glob("*.cpp")}
    if set(cpp)!=set(EXPECTED):
        raise ValueError("upstream C++ test target universe drift: "+repr(sorted(cpp)))
    shapes=sorted((suite/"shapes").glob("*.txt"))
    if not shapes:raise ValueError("no original per-solver shapes")
    for p in shapes:
        if not p.read_text().strip():raise ValueError("empty upstream solver shape list")
    originals=[suite/"build.sh",suite/"run_all.sh",suite/"common.hpp",
               *sorted(cpp.values()),*shapes]
    hashes={str(p.relative_to(source)):sha_file(p) for p in originals}
    tasks={name:{"binary":name,"stdin":None,"solver":None} for name in OPS}
    for shape in shapes:
        name="conv:"+shape.stem
        tasks[name]={"binary":"conv_solver_sweep",
                     "stdin":str(shape.resolve()),"solver":shape.stem}
    return source,suite,hashes,tasks

def runtime_identity(prefix,hipcc):
    prefix=prefix.resolve();hipcc=hipcc.resolve()
    if not prefix.is_dir() or "/nix/store/" not in str(prefix):
        raise ValueError("ROCm prefix must be inside the selected Nix store closure")
    root=prefix
    while not STORE.fullmatch(str(root)):
        if root.parent==root:raise ValueError("ROCm prefix is not a Nix store subpath")
        root=root.parent
    if not (prefix/"lib/libMIOpen.so").exists():
        raise ValueError("selected prefix lacks MIOpen shared library")
    if not (prefix/"include/miopen/miopen.h").is_file():
        raise ValueError("selected prefix lacks MIOpen headers; cannot build against this closure")
    if not hipcc.is_file() or not os.access(hipcc,os.X_OK) or not str(hipcc).startswith("/nix/store/"):
        raise ValueError("hipcc must resolve to an executable immutable Nix store file")
    return str(root),str(prefix),str(hipcc),sha_file(hipcc)

def run_child(args,cwd,env,stdout,stderr,timeout,stdin=None):
    with stdout.open("wb") as out,stderr.open("wb") as err:
        with stdin.open("rb") if stdin is not None else open(os.devnull,"rb") as inp:
            proc=subprocess.Popen(args,cwd=cwd,env=env,stdin=inp,stdout=out,
                                  stderr=err,start_new_session=True)
            try:rc=proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait();rc=None
            except BaseException:
                if proc.poll() is None:
                    os.killpg(proc.pid,signal.SIGKILL);proc.wait()
                raise
    return rc

def build(suite,hipcc,prefix,out,timeout,identity):
    bin_dir=out/"bin"
    if bin_dir.exists():raise ValueError("existing build destination")
    bin_dir.mkdir(parents=True)
    env=os.environ.copy()
    env["PATH"]=str(Path(hipcc).parent)+os.pathsep+env.get("PATH","")
    env["PYTHONNOUSERSITE"]="1"
    env.pop("ONLY",None)
    log_out=out/"build.stdout";log_err=out/"build.stderr"
    rc=run_child(["sh",str(suite/"build.sh"),str(bin_dir),prefix],
                 suite,env,log_out,log_err,timeout)
    binaries={}
    for name in EXPECTED:
        file=bin_dir/name
        if file.is_file() and os.access(file,os.X_OK):
            binaries[name]={"path":str(file),"sha256":sha_file(file)}
        else:
            binaries[name]={"status":"missing-binary"}
    record={**identity,"status":"built" if rc==0 and len(binaries)==len(EXPECTED)
            and all("sha256" in value for value in binaries.values()) else
            "build-failed","returncode":rc,"binaries":binaries,
            "build_stdout_sha256":sha_file(log_out),
            "build_stderr_sha256":sha_file(log_err),
            "gpu_executed":False,"release_admitted":False}
    persist(out/"build.json",record)
    return record

def evaluate(rc,stdout,stderr):
    text=(stdout+stderr).decode("utf8","replace")
    found=SUMMARY.findall(text)
    if rc is None:return {"status":"timeout"}
    if rc<0 or rc>=128:return {"status":"fault"}
    if len(found)!=1:return {"status":"empty-results" if rc==0 else "failed",
                             "reason":"missing or ambiguous original upstream summary"}
    total,wrong=map(int,found[0])
    if total<=0:return {"status":"empty-results","tested":total,
                        "effective_tested":0,"wrong":wrong}
    skip_count=len(re.findall(r"\bSKIP\b",text))
    # A solver can report its input shape count in the summary while every
    # shape is inapplicable.  That is not a numerical pass.
    effective_tested=max(0,total-skip_count)
    if effective_tested==0:
        return {"status":"empty-results","tested":total,
                "effective_tested":0,"wrong":wrong,
                "upstream_skip_lines":skip_count}
    return {"status":"passed" if rc==0 and wrong==0 else "failed",
            "tested":total,"effective_tested":effective_tested,
            "wrong":wrong,"upstream_skip_lines":skip_count,
            "numeric_contract":"original Schaka host CPU reference and solver applicability"}

def execute(task,name,buildrec,out,index,timeout,source):
    binary=buildrec["binaries"].get(task["binary"],{})
    if "path" not in binary:
        return {"status":"missing-binary","binary":task["binary"]}
    exe=Path(binary["path"])
    if not exe.is_file() or sha_file(exe)!=binary["sha256"]:
        return {"status":"missing-binary","reason":"binary unavailable or hash drift"}
    env=os.environ.copy()
    env.pop("LD_PRELOAD",None)
    env.pop("ONLY",None)
    # Prefer the explicit tested ROCm prefix without deleting Nix wrapper
    # dependencies. This is a loader preference, not proof of loaded maps.
    prefix=buildrec["rocm_prefix"]
    old_paths=env.get("LD_LIBRARY_PATH","")
    env["LD_LIBRARY_PATH"]=str(Path(prefix)/"lib")+(
        os.pathsep+old_paths if old_paths else "")
    if task["solver"]:
        env["MIOPEN_DEBUG_FIND_ONLY_SOLVER"]=task["solver"]
        env["MIOPEN_FIND_MODE"]="normal"
    else:
        env.pop("MIOPEN_DEBUG_FIND_ONLY_SOLVER",None)
    stdout=out/f"{index:04d}.stdout"
    stderr=out/f"{index:04d}.stderr"
    t=time.monotonic()
    rc=run_child([str(exe)],source,env,stdout,stderr,timeout,
                 Path(task["stdin"]) if task["stdin"] else None)
    result=evaluate(rc,stdout.read_bytes(),stderr.read_bytes())
    result.update({"returncode":rc,"stdout":stdout.name,"stderr":stderr.name,
                   "stdout_sha256":sha_file(stdout),"stderr_sha256":sha_file(stderr),
                   "binary_sha256":binary["sha256"],
                   "elapsed_seconds":round(time.monotonic()-t,3)})
    return result

def make_identity(source,suite,hashes,tasks,rocmroot,prefix,hipcc,hipccsha):
    return {"schema":1,"source_sha":PIN,"source":str(source),
            "suite_dir":str(suite),"source_files_sha256":hashes,
            "tasks":tasks,"selected":sorted(tasks),
            "rocm_root":rocmroot,"rocm_prefix":prefix,
            "hipcc":hipcc,"hipcc_sha256":hipccsha}

def validate_resume(state,identity):
    if any(state.get(key)!=value for key,value in identity.items()):
        raise ValueError("source/runtime/target universe changed")
    if set(state.get("cases",{}))!=set(identity["selected"]):
        raise ValueError("missing or additional suite cases")
    if any(not isinstance(x,dict) or x.get("status") not in STATES
           for x in state["cases"].values()):
        raise ValueError("corrupt case status")
    if state.get("release_admitted") is not False:
        raise ValueError("invalid release status")
    return state

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--rocm-prefix",type=Path,required=True)
    p.add_argument("--hipcc",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--build",action="store_true",help="explicitly invoke original upstream build.sh")
    p.add_argument("--execute",action="store_true",help="explicit GPU execution permission")
    p.add_argument("--resume",action="store_true")
    p.add_argument("--recovered-after-fault",action="store_true")
    p.add_argument("--build-timeout",type=int,default=1800)
    p.add_argument("--timeout",type=int,default=240)
    p.add_argument("--batch-size",type=int,default=4)
    a=p.parse_args(argv)
    if min(a.timeout,a.batch_size,a.build_timeout)<1:p.error("timeouts/batch positive")
    if a.build and a.resume:p.error("building existing receipt forbidden; fresh destination")
    if a.recovered_after_fault and not a.resume:p.error("recovery only during resume")
    try:
        source,suite,hashes,tasks=source_identity(a.source)
        root,prefix,hipcc,ccsha=runtime_identity(a.rocm_prefix,a.hipcc)
    except (ValueError,OSError) as ex:p.error(str(ex))
    identity=make_identity(source,suite,hashes,tasks,root,prefix,hipcc,ccsha)
    out=a.out.resolve()
    if a.resume:
        if not (out/"matrix.json").is_file():p.error("resume receipt missing")
    elif out.exists():p.error("fresh output directory required")
    else:out.mkdir(parents=True)
    with (out/"runner.lock").open("a+") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:p.error("output directory already owned")
        if a.build:
            buildrec=build(suite,hipcc,prefix,out,a.build_timeout,identity)
            if buildrec["status"]!="built":
                print(json.dumps({"status":buildrec["status"],"built":sum(
                    "sha256" in v for v in buildrec["binaries"].values())}))
                return 2
        elif (out/"build.json").exists():
            buildrec=json.loads((out/"build.json").read_text())
            if any(buildrec.get(k)!=v for k,v in identity.items()):
                p.error("prebuilt binaries' source/runtime provenance differs")
        else:
            p.error("no verified build receipt; use --build")
        if buildrec["status"]!="built":p.error("build incomplete, cannot run")
        for binary in buildrec["binaries"].values():
            if "sha256" not in binary or not Path(binary["path"]).is_file():
                p.error("missing source-pinned build output")
            if sha_file(Path(binary["path"]))!=binary["sha256"]:
                p.error("built binary hash drift")
        if len(buildrec.get("binaries",{}))!=len(EXPECTED):
            p.error("incomplete upstream binaries")
        matrix=out/"matrix.json"
        if a.resume:
            try:
                state=validate_resume(json.loads(matrix.read_text()),identity)
                if state.get("build_receipt_sha256")!=sha_file(out/"build.json"):
                    raise ValueError("original build receipt hash drift")
            except (ValueError,json.JSONDecodeError) as e:p.error(str(e))
        else:
            state={**identity,"status":"built-not-executed",
                   "build_receipt_sha256":sha_file(out/"build.json"),
                   "cases":{key:{"status":"unassayed"} for key in identity["selected"]},
                   "gpu_validated":False,"release_admitted":False,
                   "runtime_coherence_verified":False}
            persist(matrix,state)
        if not a.execute:
            print(json.dumps({"status":state["status"],"targets":len(state["cases"]),
                              "gpu_executed":False}))
            return 0
        hazards=[name for name in state["selected"]
                 if state["cases"][name]["status"] in HAZARDS
                 and name not in state.get("recovery_acknowledged",[])]
        if hazards and not a.recovered_after_fault:
            p.error("prior interruption/fault/timeout: check GPU before continuing")
        if hazards:
            state["recovery_acknowledged"]=sorted(set(
                state.get("recovery_acknowledged",[]))|set(hazards))
        done=0
        for i,name in enumerate(state["selected"]):
            if state["cases"][name]["status"]!="unassayed":continue
            state["cases"][name]={"status":"interrupted","started_unix":time.time()}
            state["status"]="running";persist(matrix,state)
            result=execute(tasks[name],name,buildrec,out,i,a.timeout,source)
            state["cases"][name]=result;persist(matrix,state)
            done+=1
            if result["status"] in HAZARDS:
                state["status"]="halted-for-device-inspection";break
            if done>=a.batch_size:break
        else:state["status"]="all-targets-attempted"
        if state["status"]=="running":state["status"]="batch-checkpointed"
        state["counts"]={s:sum(row["status"]==s for row in state["cases"].values())
                         for s in STATES}
        state["gpu_validated"]=False
        state["release_admitted"]=False
        persist(matrix,state)
        print(json.dumps({"status":state["status"],"batch_executed":done,
                          "counts":state["counts"]},sort_keys=True))
        return 2 if state["status"]=="halted-for-device-inspection" else 0

if __name__=="__main__":sys.exit(main())
