#!/usr/bin/env python3
"""Isolate Schaka MIOpen pool_sweep VM fault by ORIGINAL mode/shape case.

Compiles a mechanically transformed COPY of source-pinned pool_sweep.cpp;
only the main-loop selector is changed. The original run_one, CPU reference,
MIOpen calls, memory layout and numeric acceptance remain byte-identical.
Runs one case per process.  With --auto-recover, a fault is persisted and
the supervisor execs into a clean Python environment before continuing the
remaining cases.  It never retries the faulting case and never claims that a
new process repaired the GPU/driver.
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
SOURCE="tools/correctness-suite/pool_sweep.cpp"
MATRIX=re.compile(r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}")
OLD="""    for (auto mode : modes) for (auto& c : cases) {
        total++;
        if (!run_one(mode, c.C,c.H,c.W,c.kh,c.kw,c.stride,c.pad)) wrong++;
    }"""
NEW="""    const char* selected_text = std::getenv("GFX803_POOL_CASE");
    if (!selected_text) { std::fprintf(stderr, "missing selected case\\n"); return 3; }
    char* end = nullptr;
    long selected = std::strtol(selected_text, &end, 10);
    if (*end != '\\0' || selected < 0 || selected >= 42) {
        std::fprintf(stderr, "invalid selected case\\n"); return 3;
    }
    int index=0;
    for (auto mode : modes) for (auto& c : cases) {
        if (index++ != selected) continue;
        std::printf("GFX803_POOL_CASE_BEGIN index=%ld mode=%d C=%d H=%d W=%d k=%dx%d stride=%d pad=%d\\n",
                    selected, static_cast<int>(mode), c.C,c.H,c.W,c.kh,c.kw,c.stride,c.pad);
        std::fflush(stdout);
        total++;
        if (!run_one(mode, c.C,c.H,c.W,c.kh,c.kw,c.stride,c.pad)) wrong++;
    }"""
STATES=("unassayed","interrupted","pass","numeric-fail","invalid-result","fault","timeout")
SUMMARY=re.compile(r"SUMMARY:\s*(\d+)\s+cases\s+tested,\s*(\d+)\s+WRONG")
STORE=re.compile(r"^/nix/store/[0-9a-z]{32}-[^/]+$")

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def persist(file,row):
    temp=file.with_name(file.name+".tmp")
    with temp.open("w") as f:
        json.dump(row,f,indent=2,sort_keys=True);f.write("\n")
        f.flush();os.fsync(f.fileno())
    os.replace(temp,file)

def pin(source,rocm,hipcc):
    source=source.resolve();rocm=rocm.resolve();hipcc=hipcc.resolve()
    git=subprocess.run(["git","-C",str(source),"rev-parse","HEAD"],capture_output=True,text=True)
    if git.returncode or git.stdout.strip()!=PIN:raise ValueError("Schaka checkout not at original pinned SHA")
    original=source/SOURCE
    if not original.is_file():raise ValueError("original pool_sweep.cpp missing")
    status=subprocess.run(["git","-C",str(source),"status","--porcelain","--",SOURCE,
                           "tools/correctness-suite/common.hpp"],
                          capture_output=True,text=True)
    if status.returncode or status.stdout.strip():raise ValueError("upstream pooling files modified")
    if not rocm.is_dir() or not str(rocm).startswith("/nix/store/"):
        raise ValueError("selected Nix ROCm prefix required")
    if not (rocm/"include/miopen/miopen.h").is_file() or not (rocm/"lib/libMIOpen.so").exists():
        raise ValueError("selected ROCm prefix missing MIOpen headers or library")
    if not hipcc.is_file() or not str(hipcc).startswith("/nix/store/"):
        raise ValueError("immutable Nix hipcc required")
    return source,original,rocm,hipcc

def transformed(original):
    src=original.read_text()
    if src.count(OLD)!=1:raise ValueError("source main-loop contract drift")
    # All original modes and shape definitions are preserved. Verify 14 rows.
    case_section=src.split("Case cases[] = {",1)
    if len(case_section)!=2:raise ValueError("source case declarations drift")
    section=case_section[1].split("};",1)[0]
    rows=[tuple(map(int,m.groups())) for m in MATRIX.finditer(section)]
    if len(rows)!=14:raise ValueError("expected 14 original shapes")
    if "miopenPoolingMax, miopenPoolingAverage, miopenPoolingAverageInclusive" not in src:
        raise ValueError("original three modes drift")
    new=src.replace(OLD,NEW)
    # Do not modify run_one or CPU reference for the diagnostic derivative.
    if new.split("int main() {",1)[0]!=src.split("int main() {",1)[0]:
        raise ValueError("unexpected modification outside entrypoint")
    return new,rows

def run_child(args,cwd,env,stdout,stderr,timeout):
    with stdout.open("wb") as o,stderr.open("wb") as e:
        proc=subprocess.Popen(args,cwd=cwd,env=env,stdout=o,stderr=e,start_new_session=True)
        try:rc=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL);proc.wait();rc=None
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            raise
    return rc

def assess(index,rc,stdout,stderr):
    content=(stdout+stderr).decode("utf8","replace")
    if rc is None:return {"status":"timeout","returncode":None}
    if rc<0 or rc>=128:return {"status":"fault","returncode":rc}
    if not re.search(r"GFX803_POOL_CASE_BEGIN index="+str(index)+r"\b",content):
        return {"status":"invalid-result","returncode":rc,"reason":"missing exact case-start marker"}
    match=SUMMARY.findall(content)
    if len(match)!=1 or int(match[0][0])!=1:
        return {"status":"invalid-result","returncode":rc,"reason":"missing one-case summary"}
    wrong=int(match[0][1])
    passed=rc==0 and wrong==0 and "  OK" in content and "<-- WRONG" not in content
    return {"status":"pass" if passed else "numeric-fail",
            "returncode":rc,"wrong":wrong,"tested":1}

def recovery_argv(argv):
    """Return a fresh invocation that resumes after a saved device fault."""
    kept=[]
    for item in argv:
        if item in ("--build", "--recovered-after-fault"):
            continue
        kept.append(item)
    if "--resume" not in kept: kept.append("--resume")
    if "--execute" not in kept: kept.append("--execute")
    kept.append("--recovered-after-fault")
    return kept

def recovery_env():
    """Minimal, explicit parent environment for a post-fault fresh worker."""
    keys=("HOME","PATH","LANG","LC_ALL","TERM","XDG_RUNTIME_DIR",
          "HSA_OVERRIDE_GFX_VERSION","ROC_ENABLE_PRE_VEGA")
    env={key:os.environ[key] for key in keys if key in os.environ}
    env["PYTHONNOUSERSITE"]="1"
    # Deliberately do not inherit preload/library overrides from a faulting run.
    return env

def build_args(hipcc, rocm, changed, binary, source_dir):
    """Compile the entrypoint-only derivative with Schaka's local headers."""
    return [str(hipcc),"-O2","-I"+str(rocm/"include"),"-I"+str(source_dir),
            str(changed),"-o",str(binary),"-L"+str(rocm/"lib"),"-lMIOpen","-lm",
            "-Wl,-rpath,"+str(rocm/"lib")]

def case_metadata(shapes):
    modes=("MAX","AVG","AVG_INCL")
    # Use JSON-native lists so an in-memory identity equals its persisted form.
    return {str(i):{"mode":modes[i//14],"shape":list(shapes[i%14])}
            for i in range(42)}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--rocm-prefix",type=Path,required=True)
    p.add_argument("--hipcc",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--build",action="store_true")
    p.add_argument("--execute",action="store_true")
    p.add_argument("--resume",action="store_true")
    p.add_argument("--recovered-after-fault",action="store_true")
    p.add_argument("--auto-recover",action="store_true",
                   help="after persisting a fault, exec a clean worker for remaining cases")
    p.add_argument("--timeout",type=int,default=90)
    p.add_argument("--build-timeout",type=int,default=900)
    p.add_argument("--batch-size",type=int,default=4)
    a=p.parse_args(argv)
    if min(a.timeout,a.build_timeout,a.batch_size)<1:
        p.error("positive timeout and batch-size required")
    if a.build and a.resume:p.error("cannot rebuild a previous original receipt")
    if a.recovered_after_fault and not a.resume:p.error("recovery requires --resume")
    try:
        source,original,rocm,hipcc=pin(a.source,a.rocm_prefix,a.hipcc)
        derived,shapes=transformed(original)
    except (ValueError,OSError) as exc:p.error(str(exc))
    out=a.out.resolve()
    if a.resume:
        if not (out/"matrix.json").is_file():p.error("missing resume receipt")
    elif out.exists():p.error("new output directory required")
    else:out.mkdir(parents=True)
    ids=[str(i) for i in range(42)]
    identities={"schema":1,"source_sha":PIN,"source":str(source),
                "original_path":str(original),"original_sha256":sha(original),
                "derived_sha256":hashlib.sha256(derived.encode()).hexdigest(),
                "rocm_prefix":str(rocm),"hipcc":str(hipcc),
                "hipcc_sha256":sha(hipcc),"selected":ids,
                "metadata":case_metadata(shapes)}
    with (out/"lock").open("a+") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:p.error("output in use")
        buildrec=out/"build.json";binary=out/"pool_case"
        if a.build:
            changed=out/"pool_case.cpp"
            changed.write_text(derived)
            env=os.environ.copy()
            env["PATH"]=str(hipcc.parent)+os.pathsep+env.get("PATH","")
            cmd=build_args(hipcc,rocm,changed,binary,original.parent)
            rc=run_child(cmd,out,env,out/"build.stdout",out/"build.stderr",a.build_timeout)
            receipt={**identities,"build_returncode":rc,
                     "build_stdout_sha256":sha(out/"build.stdout"),
                     "build_stderr_sha256":sha(out/"build.stderr"),
                     "status":"built" if rc==0 and binary.is_file() else "build-failed",
                     "binary_sha256":sha(binary) if rc==0 and binary.is_file() else None,
                     "gpu_executed":False,"release_admitted":False}
            persist(buildrec,receipt)
            if receipt["status"]!="built":
                print(json.dumps({"status":"build-failed","returncode":rc}));return 2
        if not buildrec.is_file():p.error("original derivative build receipt missing")
        build=json.loads(buildrec.read_text())
        if any(build.get(k)!=v for k,v in identities.items()):
            p.error("source/toolchain/shape universe drift")
        if build.get("status")!="built" or not binary.is_file() or sha(binary)!=build.get("binary_sha256"):
            p.error("derived binary missing or hash drift")
        matrix=out/"matrix.json"
        if a.resume:
            state=json.loads(matrix.read_text())
            if any(state.get(k)!=v for k,v in identities.items()):
                p.error("original experiment identity drift")
            if state.get("build_receipt_sha256")!=sha(buildrec):p.error("build receipt drift")
            if set(state.get("cases",{}))!=set(ids) or any(
                r.get("status") not in STATES for r in state["cases"].values()):
                p.error("case status drift")
        else:
            if matrix.exists():p.error("existing diagnostic matrix must be resumed")
            state={**identities,"build_receipt_sha256":sha(buildrec),
                   "cases":{i:{"status":"unassayed"} for i in ids},
                   "status":"built-not-executed","gpu_executed":False,
                   "release_admitted":False}
            persist(matrix,state)
        if not a.execute:
            print(json.dumps({"status":state["status"],"total_cases":42,
                              "gpu_executed":False}));return 0
        hazard=[i for i in ids if state["cases"][i]["status"] in
                ("fault","timeout","interrupted") and
                i not in state.get("recovery_acknowledged",[])]
        if hazard and not a.recovered_after_fault:
            p.error("prior fault/timeout/interruption: physical GPU inspection required")
        if hazard:
            state["recovery_acknowledged"]=sorted(set(
                state.get("recovery_acknowledged",[]))|set(hazard))
        done=0
        for i in ids:
            if state["cases"][i]["status"]!="unassayed":continue
            n=int(i);stdout=out/(i.zfill(3)+".stdout");stderr=out/(i.zfill(3)+".stderr")
            state["cases"][i]={"status":"interrupted","started_unix":time.time()}
            state["status"]="running";persist(matrix,state)
            env=os.environ.copy();env["GFX803_POOL_CASE"]=i
            env.pop("LD_PRELOAD",None)
            previous=env.get("LD_LIBRARY_PATH","")
            env["LD_LIBRARY_PATH"]=str(rocm/"lib")+(os.pathsep+previous if previous else "")
            t=time.monotonic()
            rc=run_child([str(binary)],out,env,stdout,stderr,a.timeout)
            row=assess(n,rc,stdout.read_bytes(),stderr.read_bytes())
            row.update({"stdout":stdout.name,"stderr":stderr.name,
                        "stdout_sha256":sha(stdout),"stderr_sha256":sha(stderr),
                        "elapsed_seconds":round(time.monotonic()-t,3)})
            state["cases"][i]=row
            persist(matrix,state)
            done+=1
            if row["status"] in ("fault","timeout"):
                state["status"]="halted-for-device-inspection";break
            if done>=a.batch_size:break
        else:state["status"]="all-cases-attempted"
        if state["status"]=="running":state["status"]="batch-checkpointed"
        state["counts"]={v:sum(r["status"]==v for r in state["cases"].values())
                         for v in STATES}
        state["gpu_executed"]=done>0
        state["release_admitted"]=False
        persist(matrix,state)
        print(json.dumps({"status":state["status"],"executed":done,
                          "counts":state["counts"]},sort_keys=True))
        if state["status"]=="halted-for-device-inspection" and a.auto_recover:
            # exec replaces this potentially contaminated coordinator process;
            # the recorded fault remains immutable and is skipped on resume.
            os.execvpe(sys.executable, recovery_argv(sys.argv), recovery_env())
        return 2 if state["status"]=="halted-for-device-inspection" else 0

if __name__=="__main__":sys.exit(main())
