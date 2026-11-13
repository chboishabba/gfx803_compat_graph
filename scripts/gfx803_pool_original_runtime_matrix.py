#!/usr/bin/env python3
"""Compare the ORIGINAL 42-case MIOpen pool binary across HIP/HSA controls.

Unlike derived-prefix assays this runs the exact original pool_sweep binary
recorded by the original Schaka MIOpen build receipt. Each configuration runs
in its own process; no automatic retry after a fault/timeout/failed test.
Captures kernel messages and live /proc/<pid>/maps where permitted. Doorbell
patches are host-kernel hypotheses, never claimed to be fixed by env flags.
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
MIOPEN="tools/correctness-suite/pool_sweep.cpp"
SUM=re.compile(r"SUMMARY:\s*(\d+)\s+cases\s+tested,\s*(\d+)\s+WRONG")
CONTROLS={
 "baseline":{},
 "serialize":{"AMD_SERIALIZE_KERNEL":"3","AMD_SERIALIZE_COPY":"3"},
 "fragment-off":{"HSA_DISABLE_FRAGMENT_ALLOCATOR":"1"},
 "sdma-off":{"HSA_ENABLE_SDMA":"0"},
 "irq-poll":{"HSA_ENABLE_INTERRUPT":"0"},
 "logging":{"AMD_LOG_LEVEL":"4","MIOPEN_ENABLE_LOGGING":"1","MIOPEN_LOG_LEVEL":"6",\n            "HSAKMT_DEBUG_LEVEL":"6"},
}
CONTROL_KEYS=("AMD_SERIALIZE_KERNEL","AMD_SERIALIZE_COPY",
  "HSA_DISABLE_FRAGMENT_ALLOCATOR","HSA_ENABLE_SDMA","HSA_ENABLE_INTERRUPT",
  "AMD_LOG_LEVEL","MIOPEN_ENABLE_LOGGING","MIOPEN_LOG_LEVEL",\n  "HSAKMT_DEBUG_LEVEL",
  "HSA_DISABLE_CACHE","HIP_LAUNCH_BLOCKING","GPU_MAX_HW_QUEUES")
STATES=("unassayed","running-interrupted","pass","numeric-fail",
        "missing-summary","fault","timeout","setup-fail","kernel-fault-observed")

def sha_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def persist(path,obj):
    temp=path.with_name(path.name+".tmp")
    with temp.open("w") as f:
        json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        f.flush();os.fsync(f.fileno())
    os.replace(temp,path)

def validate_build(buildfile):
    obj=json.loads(buildfile.read_text())
    if obj.get("source_sha")!=PIN or obj.get("status")!="built":
        raise ValueError("expected original Schaka compiled build receipt")
    source=Path(obj["source"]).resolve()
    original=source/MIOPEN
    got=subprocess.run(["git","-C",str(source),"rev-parse","HEAD"],
                       capture_output=True,text=True)
    if got.returncode or got.stdout.strip()!=PIN:
        raise ValueError("original source revision drift")
    if not original.is_file() or not (source/"tools/correctness-suite/common.hpp").is_file():
        raise ValueError("missing original Schaka sources")
    dirty=subprocess.run(["git","-C",str(source),"status","--porcelain","--",
                          MIOPEN,"tools/correctness-suite/common.hpp"],
                          capture_output=True,text=True)
    if dirty.returncode or dirty.stdout.strip():
        raise ValueError("original pool sources dirty")
    binary=Path(obj["binaries"]["pool_sweep"]["path"]).resolve()
    if not binary.is_file() or not os.access(binary,os.X_OK):
        raise ValueError("missing original built pooling binary")
    if sha_file(binary)!=obj["binaries"]["pool_sweep"]["sha256"]:
        raise ValueError("original binary hash drift")
    prefix=Path(obj["rocm_prefix"]).resolve()
    if not str(prefix).startswith("/nix/store/") or not (prefix/"lib/libMIOpen.so").exists():
        raise ValueError("original staged ROCm prefix unavailable")
    return obj,binary,prefix,original

def classify(rc,stdout,stderr):
    log=(stdout+stderr).decode("utf8","replace")
    matches=SUM.findall(log)
    base={"returncode":rc}
    if rc is None:return dict(base,status="timeout")
    if rc<0 or rc>=128:return dict(base,status="fault")
    if len(matches)!=1:return dict(base,status="missing-summary" if rc==0 else "setup-fail")
    total,wrong=map(int,matches[0])
    base.update(tested=total,wrong=wrong)
    if total!=42:return dict(base,status="missing-summary")
    return dict(base,status="pass" if rc==0 and wrong==0 else "numeric-fail")

def kernel_logs(since,output):
    # This deliberately does NOT use sudo or modify the host's journal.
    # A denied journal is evidence of unavailable observability, not no faults.
    cmd=["journalctl","-k","--since",f"@{int(since)}","--no-pager","-o","short-iso"]
    try:
        p=subprocess.run(cmd,capture_output=True,timeout=15)
        output.write_bytes(p.stdout+b"\nSTDERR:\n"+p.stderr)
        return {"available":p.returncode==0,"returncode":p.returncode,
                "sha256":sha_file(output)}
    except (OSError,subprocess.TimeoutExpired) as e:
        output.write_text("journal collection unavailable: "+str(e))
        return {"available":False,"error":str(e),"sha256":sha_file(output)}

def run_one(binary,prefix,case,output,timeout):
    env=os.environ.copy()
    for key in CONTROL_KEYS:env.pop(key,None)
    # Prefer the literal staged closure; inherited extras are recorded as
    # potential confounders, not treated as evidence of exact loader binding.
    prior=env.get("LD_LIBRARY_PATH","")
    env["LD_LIBRARY_PATH"]=str(prefix/"lib")+(os.pathsep+prior if prior else "")
    env.pop("LD_PRELOAD",None)
    env.update(CONTROLS[case])
    path=output/case
    path.mkdir()
    stdout=path/"stdout.log";stderr=path/"stderr.log"
    start=time.time()
    with stdout.open("wb") as so,stderr.open("wb") as se:
        p=subprocess.Popen([str(binary)],stdout=so,stderr=se,
                           env=env,start_new_session=True)
        maps=path/"proc-maps.txt"
        try:
            # Capture dynamic loader mappings repeatedly (early and late).
            # No ptrace, root access or process modification.
            with maps.open("w") as capture:
                for _ in range(12):
                    if p.poll() is not None:break
                    try:
                        lines=Path(f"/proc/{p.pid}/maps").read_text().splitlines()
                        libs=sorted(set(line.rsplit(" ",1)[-1] for line in lines
                          if any(x in line.lower() for x in
                            ("miopen","libamdhip","libhsa","libhsakmt","rocblas"))))
                        capture.write(f"t={time.time():.6f} "+json.dumps(libs)+"\n")
                    except OSError as e:
                        capture.write("unavailable: "+str(e)+"\n")
                    capture.flush()
                    time.sleep(0.1)
            remaining=max(0.01,timeout-(time.time()-start))
            rc=p.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.wait();rc=None
        except BaseException:
            if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
            raise
    outb=stdout.read_bytes();errb=stderr.read_bytes()
    result=classify(rc,outb,errb)
    result.update({"environment_override":CONTROLS[case],
         "inherited_ld_library_path":prior,
         "start_unix":start,"elapsed_seconds":round(time.time()-start,3),
         "stdout_sha256":sha_file(stdout),"stderr_sha256":sha_file(stderr),
         "maps_sha256":sha_file(maps)})
    result["kernel_journal"]=kernel_logs(start-2,path/"kernel.log")
    if result["kernel_journal"]["available"]:
        # A child can return success after an asynchronous device fault.
        # Journal events might originate with another tenant; halt for
        # attribution without declaring this test's kernel causal.
        lines=(path/"kernel.log").read_text(errors="replace").splitlines()
        matches=[line for line in lines if re.search(
            r"gpu.*(vm fault|page.not.present|fault)|VM_CONTEXT.*PROTECTION_FAULT|"
            r"ring .*timeout|scheduler .*not ready|GPU reset|kernel BUG|Oops:",
            line,re.I)]
        result["kernel_fault_signals"]=matches[-30:]
        if matches and result["status"]=="pass":
            result["status"]="kernel-fault-observed"
            result["note"]="journal contains possible host-wide GPU fault; attribution to child is not established"
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build-receipt",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--resume",action="store_true")
    p.add_argument("--timeout",type=int,default=180)
    p.add_argument("--batch-size",type=int,default=1)
    a=p.parse_args(argv)
    if a.timeout<1 or a.batch_size<1:p.error("positive bounds required")
    try:
        build,binary,prefix,original=validate_build(a.build_receipt)
    except (OSError,KeyError,ValueError,json.JSONDecodeError) as exc:p.error(str(exc))
    identity={"schema":1,"original_build_receipt_sha256":sha_file(a.build_receipt),
      "original_source_sha256":sha_file(original),
      "original_binary_sha256":sha_file(binary),"original_binary":str(binary),
      "rocm_prefix":str(prefix),"source_sha":PIN,"controls":CONTROLS,
      "host_uname":os.uname().release,"cases":list(CONTROLS)}
    dest=a.out.resolve()
    if a.resume:
        if not (dest/"matrix.json").is_file():p.error("no prior diagnostic matrix")
    elif dest.exists():p.error("must use fresh output directory")
    else:dest.mkdir(parents=True)
    with (dest/"lock").open("a+") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:p.error("experiment already running")
        matrix=dest/"matrix.json"
        if a.resume:
            state=json.loads(matrix.read_text())
            if any(state.get(k)!=v for k,v in identity.items()):
                p.error("original build/control/kernel drift")
            if set(state.get("results",{}))!=set(CONTROLS):
                p.error("missing case evidence")
            if any(v.get("status") not in STATES for v in state["results"].values()):
                p.error("invalid case result")
        else:
            state={**identity,"results":{k:{"status":"unassayed"} for k in CONTROLS},
              "status":"planned","release_admitted":False,"gpu_validated":False}
            persist(matrix,state)
        if not a.execute:
            print(json.dumps({"controls":list(CONTROLS),"original_binary_sha256":sha_file(binary),
                              "gpu_executed":False}));return 0
        if any(r["status"] in ("running-interrupted","fault","timeout")
               for r in state["results"].values()):
            p.error("previous device fault/interruption requires new experiment after health check")
        done=0
        for name in CONTROLS:
            if state["results"][name]["status"]!="unassayed":continue
            state["results"][name]={"status":"running-interrupted","started_unix":time.time()}
            state["status"]="running";persist(matrix,state)
            result=run_one(binary,prefix,name,dest,a.timeout)
            state["results"][name]=result;persist(matrix,state)
            done+=1
            if result["status"]!="pass":
                state["status"]="halted-for-investigation";break
            if done>=a.batch_size:break
        else:state["status"]="all-controls-attempted"
        if state["status"]=="running":state["status"]="batch-checkpointed"
        state["status_counts"]={x:sum(r["status"]==x for r in state["results"].values())
                                for x in STATES}
        state["gpu_validated"]=False;state["release_admitted"]=False
        persist(matrix,state)
        print(json.dumps({"status":state["status"],"run":done,
                          "counts":state["status_counts"]},sort_keys=True))
        return 2 if state["status"]=="halted-for-investigation" else 0

if __name__=="__main__":sys.exit(main())
