#!/usr/bin/env python3
"""Source-bound in-process prefix diagnostic for Schaka MIOpen pool_sweep.

Unlike the single-case runner, one child executes N *consecutive* original
pooling cases with the original run_one, allocations, handles, CPU reference,
and numerical check. The only source edit is the main-loop selection and
flushable boundary markers. The parent stops on ANY nonpassing child.
Each prefix is a fresh process; no automatic retry/reset of a failed prefix.
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
ORIGINAL="tools/correctness-suite/pool_sweep.cpp"
OLD="""    for (auto mode : modes) for (auto& c : cases) {
        total++;
        if (!run_one(mode, c.C,c.H,c.W,c.kh,c.kw,c.stride,c.pad)) wrong++;
    }"""
NEW="""    const char* cap_text = std::getenv("GFX803_POOL_PREFIX");
    if (!cap_text) { std::fprintf(stderr, "missing prefix count\\n"); return 3; }
    char* end = nullptr;
    long cap = std::strtol(cap_text, &end, 10);
    if (*end != '\\0' || cap < 1 || cap > 42) {
        std::fprintf(stderr, "invalid prefix count\\n"); return 3;
    }
    int index=0;
    for (auto mode : modes) for (auto& c : cases) {
        if (index >= cap) break;
        std::printf("POOL_BEGIN index=%d prefix=%ld mode=%d C=%d H=%d W=%d k=%dx%d stride=%d pad=%d\\n",
            index, cap, static_cast<int>(mode), c.C,c.H,c.W,c.kh,c.kw,c.stride,c.pad);
        std::fflush(stdout);
        total++;
        if (!run_one(mode, c.C,c.H,c.W,c.kh,c.kw,c.stride,c.pad)) wrong++;
        std::printf("POOL_END index=%d\\n",index);
        std::fflush(stdout);
        index++;
    }"""
DEFAULT=(1,2,4,8,14,16,21,28,35,42)
SUMMARY=re.compile(r"SUMMARY:\s*(\d+)\s+cases\s+tested,\s*(\d+)\s+WRONG")
STATES=("unassayed","interrupted","passed","numeric-fail","fault","timeout","invalid-result")

def hashfile(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def save(path,doc):
    tmp=path.with_name(path.name+".tmp")
    with tmp.open("w") as f:
        json.dump(doc,f,sort_keys=True,indent=2);f.write("\n")
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def derived(original):
    if original.count(OLD)!=1:raise ValueError("original Schaka pool main loop changed")
    if "miopenPoolingMax, miopenPoolingAverage, miopenPoolingAverageInclusive" not in original:
        raise ValueError("original three pooling modes changed")
    out=original.replace(OLD,NEW)
    if out.split("int main() {",1)[0]!=original.split("int main() {",1)[0]:
        raise ValueError("pooling kernel/API/reference unexpectedly altered")
    return out

def classify(prefix,rc,stdout,stderr):
    data=(stdout+stderr).decode("utf8","replace")
    completed=[int(n) for n in re.findall(r"POOL_END index=(\d+)\b",data)]
    started=[int(n) for n in re.findall(r"POOL_BEGIN index=(\d+)\b",data)]
    row={"returncode":rc,"completed_indices":completed,"started_indices":started,
         "last_started_index":started[-1] if started else None}
    if rc is None:row["status"]="timeout";return row
    if rc<0 or rc>=128:row["status"]="fault";return row
    if (started!=list(range(prefix)) or completed!=list(range(prefix))):
        row["status"]="invalid-result" if rc==0 else "fault"
        return row
    foot=SUMMARY.findall(data)
    if len(foot)!=1 or int(foot[0][0])!=prefix:
        row["status"]="invalid-result" if rc==0 else "fault"
        return row
    wrong=int(foot[0][1])
    row["wrong"]=wrong
    row["status"]="passed" if rc==0 and wrong==0 else "numeric-fail"
    return row

def run(command,cwd,env,out,err,timeout):
    with out.open("wb") as o,err.open("wb") as e:
        p=subprocess.Popen(command,cwd=cwd,env=env,stdout=o,stderr=e,start_new_session=True)
        try:rc=p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.wait();rc=None
        except BaseException:
            if p.poll() is None:
                os.killpg(p.pid,signal.SIGKILL);p.wait()
            raise
    return rc

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ("source","build-receipt","out"):
        ap.add_argument("--"+key,type=Path,required=True)
    ap.add_argument("--prefixes",default=",".join(map(str,DEFAULT)))
    ap.add_argument("--build",action="store_true")
    ap.add_argument("--execute",action="store_true")
    ap.add_argument("--resume",action="store_true")
    ap.add_argument("--timeout",type=int,default=180)
    ap.add_argument("--build-timeout",type=int,default=900)
    ap.add_argument("--batch-size",type=int,default=2)
    a=ap.parse_args()
    if min(a.timeout,a.build_timeout,a.batch_size)<1:ap.error("invalid limits")
    if a.build and a.resume:ap.error("cannot rebuild a previous receipt")
    try:
        prefixes=[int(n) for n in a.prefixes.split(",")]
        if not prefixes or sorted(set(prefixes))!=prefixes or min(prefixes)<1 or max(prefixes)>42:
            raise ValueError("prefixes must be increasing distinct values 1..42")
        source=a.source.resolve()
        gp=subprocess.run(["git","-C",str(source),"rev-parse","HEAD"],
                          capture_output=True,text=True)
        if gp.returncode or gp.stdout.strip()!=PIN:raise ValueError("original source pin mismatch")
        src=source/ORIGINAL
        if not src.is_file():raise ValueError("original pool source missing")
        dirty=subprocess.run(["git","-C",str(source),"status","--porcelain","--",
                              ORIGINAL,"tools/correctness-suite/common.hpp"],
                             capture_output=True,text=True)
        if dirty.returncode or dirty.stdout.strip():raise ValueError("original pool sources modified")
        original=src.read_text()
        changed=derived(original)
        prior=json.loads(a.build_receipt.read_text())
        if prior.get("source_sha")!=PIN and prior.get("source_sha") is not None:
            raise ValueError("old MIOpen build source pin differs")
        if prior.get("source")!=str(source):raise ValueError("old MIOpen source root mismatch")
        prefix=Path(prior["rocm_prefix"]).resolve()
        hipcc=Path(prior["hipcc"]).resolve()
        if not str(prefix).startswith("/nix/store/") or not str(hipcc).startswith("/nix/store/"):
            raise ValueError("old build must use staged Nix ROCm")
        if not hipcc.is_file() or not (prefix/"include/miopen/miopen.h").is_file():
            raise ValueError("old build runtime/compiler no longer available")
        ids=list(map(str,prefixes))
        identity={"schema":1,"source_sha":PIN,"original_pool_sha256":hashfile(src),
                  "derived_sha256":hashlib.sha256(changed.encode()).hexdigest(),
                  "old_build_receipt_sha256":hashfile(a.build_receipt),
                  "rocm_prefix":str(prefix),"hipcc":str(hipcc),
                  "hipcc_sha256":hashfile(hipcc),"prefixes":prefixes}
    except (ValueError,OSError,KeyError,TypeError) as ex:ap.error(str(ex))
    dest=a.out.resolve()
    if a.resume:
        if not (dest/"matrix.json").is_file():ap.error("cannot resume missing output")
    elif dest.exists():ap.error("output exists; choose new directory")
    else:dest.mkdir(parents=True)
    with (dest/"runner.lock").open("a+") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:ap.error("output already in use")
        binary=dest/"pool_prefix"
        buildfile=dest/"build.json"
        if a.build:
            (dest/"pool_prefix.cpp").write_text(changed)
            command=[str(hipcc),"-O2","-I"+str(src.parent),
                     "-I"+str(prefix/"include"),str(dest/"pool_prefix.cpp"),
                     "-o",str(binary),"-L"+str(prefix/"lib"),"-lMIOpen","-lm",
                     "-Wl,-rpath,"+str(prefix/"lib")]
            env=os.environ.copy()
            env["PATH"]=str(hipcc.parent)+os.pathsep+env.get("PATH","")
            rc=run(command,dest,env,dest/"build.stdout",dest/"build.stderr",a.build_timeout)
            result={**identity,"status":"built" if rc==0 and binary.is_file() else "build-failed",
                    "returncode":rc,"binary_sha256":hashfile(binary)
                    if rc==0 and binary.is_file() else None,
                    "release_admitted":False}
            save(buildfile,result)
            if result["status"]!="built":return 2
        if not buildfile.is_file():ap.error("build receipt missing")
        build=json.loads(buildfile.read_text())
        if any(build.get(k)!=v for k,v in identity.items()) or build.get("status")!="built":
            ap.error("build identity drift")
        if not binary.is_file() or hashfile(binary)!=build.get("binary_sha256"):
            ap.error("built binary drift")
        matrix=dest/"matrix.json"
        if a.resume:
            state=json.loads(matrix.read_text())
            if any(state.get(k)!=v for k,v in identity.items()):
                ap.error("resume source/build/sequence drift")
            if state.get("build_sha256")!=hashfile(buildfile):
                ap.error("build receipt changed")
            if set(state.get("cases",{}))!=set(ids) or any(
                x.get("status") not in STATES for x in state["cases"].values()):
                ap.error("invalid previous case universe")
        else:
            state={**identity,"build_sha256":hashfile(buildfile),
                   "cases":{i:{"status":"unassayed"} for i in ids},
                   "status":"built-not-executed","release_admitted":False,
                   "gpu_validated":False}
            save(matrix,state)
        if not a.execute:
            print(json.dumps({"source_pinned":True,"prefixes":prefixes,
                              "gpu_executed":False}));return 0
        if any(v["status"] in ("fault","timeout","interrupted") for v in state["cases"].values()):
            ap.error("prior fault or interrupted run; use a NEW experiment after GPU health inspection")
        ran=0
        for n in prefixes:
            key=str(n)
            if state["cases"][key]["status"]!="unassayed":continue
            state["cases"][key]={"status":"interrupted","start_unix":time.time()}
            state["status"]="running";save(matrix,state)
            out=dest/f"{n:02d}.stdout";err=dest/f"{n:02d}.stderr"
            env=os.environ.copy()
            env.pop("LD_PRELOAD",None)
            env["GFX803_POOL_PREFIX"]=key
            env["LD_LIBRARY_PATH"]=str(prefix/"lib")+(
                os.pathsep+env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
            t=time.monotonic()
            rc=run([str(binary)],dest,env,out,err,a.timeout)
            row=classify(n,rc,out.read_bytes(),err.read_bytes())
            row.update({"elapsed_seconds":round(time.monotonic()-t,3),
                        "stdout_file":out.name,"stderr_file":err.name,
                        "stdout_sha256":hashfile(out),"stderr_sha256":hashfile(err)})
            state["cases"][key]=row;save(matrix,state)
            ran+=1
            if row["status"]!="passed":
                state["status"]="halted-for-investigation";break
            if ran>=a.batch_size:break
        else:state["status"]="all-prefixes-attempted"
        if state["status"]=="running":state["status"]="batch-checkpointed"
        state["counts"]={s:sum(x["status"]==s for x in state["cases"].values()) for s in STATES}
        state["gpu_validated"]=False;state["release_admitted"]=False
        save(matrix,state)
        print(json.dumps({"status":state["status"],"executed":ran,
                          "counts":state["counts"]},sort_keys=True))
        return 2 if state["status"]=="halted-for-investigation" else 0

if __name__=="__main__":sys.exit(main())
