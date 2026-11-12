#!/usr/bin/env python3
"""Plan and optionally run EXACT installed CTest cases under pinned gfx803 inputs.

TheRock provides tests for HIP, ROCr/KFD, BLAS, FFT, RAND, PRIM, MIOpen,
SOLVER and SPARSE. This adapter does not vendor them or assert availability:
point it at an ACTUALLY BUILT test directory. 'ctest --show-only=json-v1'
discovers tests without running their bodies. Execution is explicit and
fault/timeout gated; a CTest pass is NOT proof of GPU runtime coherence.
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

CATALOG=Path(__file__).resolve().parents[1]/"qualification/rocm_layers_v1.json"
HEX40=re.compile(r"^[0-9a-f]{40}$")
STORE=re.compile(r"^/nix/store/[0-9a-z]{32}-[A-Za-z0-9+._?=-]+$")
STATUS=("unassayed","interrupted","ctest-pass","ctest-fail","fault","timeout")
HAZARDS=("interrupted","fault","timeout")

def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def save(path:Path,row:dict):
    tmp=path.with_name(path.name+".tmp")
    with tmp.open("w") as f:
        json.dump(row,f,indent=2,sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp,path)

def validate_layer(name:str)->dict:
    catalog=json.loads(CATALOG.read_text())
    layers={r["id"]:r for r in catalog["layers"]}
    if name not in layers or name=="pytorch-opinfo":
        raise ValueError("unknown CTest layer or existing OpInfo runner required")
    return layers[name]

def pin_source(path:Path,sha:str)->str:
    if not HEX40.fullmatch(sha):
        raise ValueError("40-character pinned git source SHA required")
    root=path.resolve()
    cmd=["git","-C",str(root)]
    result=subprocess.run(cmd+["rev-parse","HEAD"],capture_output=True,text=True)
    if result.returncode or result.stdout.strip()!=sha:
        raise ValueError("test source is not at explicitly pinned commit")
    dirty=subprocess.run(cmd+["status","--porcelain","--untracked-files=no"],
                         capture_output=True,text=True)
    if dirty.returncode or dirty.stdout.strip():
        raise ValueError("pinned test source has tracked modifications")
    return str(root)

def pin_runtime(root:Path)->str:
    resolved=root.resolve()
    if not STORE.fullmatch(str(resolved)) or not resolved.is_dir():
        raise ValueError("selected ROCm closure must be existing immutable Nix store path")
    return str(resolved)

def pin_ctest(executable:Path)->dict:
    resolved=executable.resolve()
    if not resolved.is_file() or not os.access(resolved,os.X_OK):
        raise ValueError("missing executable CTest")
    if not str(resolved).startswith("/nix/store/"):
        raise ValueError("CTest executable must be from immutable Nix store")
    return {"ctest":str(resolved),"ctest_sha256":digest(resolved.read_bytes())}

def collect(ctest:str,directory:Path,timeout:int)->tuple[list[str],str]:
    # CTest discovery may instantiate upstream test metadata; no test bodies.
    p=subprocess.run([ctest,"--test-dir",str(directory),"--show-only=json-v1"],
                     text=True,capture_output=True,timeout=timeout)
    if p.returncode:
        raise ValueError("ctest discovery failed: "+p.stderr[-500:])
    doc=json.loads(p.stdout)
    names=[row["name"] for row in doc.get("tests",[])]
    if not names or len(set(names))!=len(names) or not all(
        isinstance(n,str) and n and "\n" not in n for n in names
    ):
        raise ValueError("empty/duplicate/malformed CTest suite")
    return names,digest(p.stdout.encode())

def initial(layer,source,source_sha,runtime,testdir,ctest,ctest_hash,names,catalog_hash):
    return {"schema":1,"layer":layer,"source":source,"source_sha":source_sha,
            "rocm_root":runtime,"test_dir":testdir,"ctest":ctest,
            "ctest_sha256":ctest_hash,"discovery_sha256":catalog_hash,
            "all_discovered_tests":names,
            "cases":{n:{"status":"unassayed"} for n in names},
            "status":"planned","gpu_validated":False,"release_admitted":False,
            "runtime_coherence_verified":False,
            "scope":"installed upstream CTest target names, not all ROCm API calls"}

def verify_resume(original,proposed):
    for key in ("schema","layer","source","source_sha","rocm_root","test_dir",
                "ctest","ctest_sha256","discovery_sha256","all_discovered_tests"):
        if original.get(key)!=proposed[key]:
            raise ValueError("source/runtime/CTest discovered universe drift: "+key)
    if set(original.get("cases",{}))!=set(proposed["cases"]):
        raise ValueError("CTest case universe changed")
    if original.get("release_admitted") is not False or original.get("gpu_validated") is not False:
        raise ValueError("invalid promotion flags")
    if any(not isinstance(r,dict) or r.get("status") not in STATUS
           for r in original["cases"].values()):
        raise ValueError("invalid prior receipt")
    return original

def run_case(ctest,testdir,name,timeout,output,index):
    started=time.monotonic()
    stdout=output/f"{index:06d}.stdout"
    stderr=output/f"{index:06d}.stderr"
    command=[ctest,"--test-dir",testdir,"--output-on-failure",
             "--timeout",str(timeout),"-R","^"+re.escape(name)+"$"]
    with stdout.open("wb") as o,stderr.open("wb") as e:
        proc=subprocess.Popen(command,stdout=o,stderr=e,start_new_session=True)
        try:rc=proc.wait(timeout=timeout+20)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL)
            proc.wait()
            rc=None
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait()
            raise
    output_text=(stdout.read_bytes()+b"\n"+stderr.read_bytes()).decode("utf8","replace")
    # Crucial: ctest -R unmatched can return zero. A pass must prove exactly
    # ONE CTest case was actually executed, not 'No tests were found'.
    matched=bool(re.search(r"100% tests passed, 0 tests failed out of 1\b",output_text))
    if rc is None:status="timeout"
    elif rc<0 or rc>=128:status="fault"
    elif rc==0 and matched:status="ctest-pass"
    else:status="ctest-fail"
    return {"status":status,"returncode":rc,"output_one_test_confirmed":matched,
            "stdout_sha256":digest(stdout.read_bytes()),
            "stderr_sha256":digest(stderr.read_bytes()),
            "stdout_file":stdout.name,"stderr_file":stderr.name,
            "elapsed_seconds":round(time.monotonic()-started,3)}

def summary(state):
    return {k:sum(v["status"]==k for v in state["cases"].values()) for k in STATUS}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--layer",required=True)
    p.add_argument("--source-dir",type=Path,required=True)
    p.add_argument("--source-sha",required=True)
    p.add_argument("--rocm-root",type=Path,required=True)
    p.add_argument("--ctest",type=Path,required=True)
    p.add_argument("--test-dir",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--resume",action="store_true")
    p.add_argument("--recovered-after-fault",action="store_true")
    p.add_argument("--batch-size",type=int,default=16)
    p.add_argument("--timeout",type=int,default=180)
    a=p.parse_args(argv)
    if a.batch_size<1 or a.timeout<1:p.error("batch-size/timeout must be positive")
    if a.recovered_after_fault and not a.resume:p.error("recovery only with --resume")
    try:
        validate_layer(a.layer)
        source=pin_source(a.source_dir,a.source_sha)
        runtime=pin_runtime(a.rocm_root)
        tool=pin_ctest(a.ctest)
        testdir=a.test_dir.resolve()
        if not testdir.is_dir() or not (testdir/"CTestTestfile.cmake").is_file():
            raise ValueError("actual configured CTest build directory required")
        names,catalog_hash=collect(tool["ctest"],testdir,a.timeout)
    except (ValueError,KeyError,OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as ex:
        p.error(str(ex))
    proposed=initial(a.layer,source,a.source_sha,runtime,str(testdir),
                     tool["ctest"],tool["ctest_sha256"],names,catalog_hash)
    out=a.out.resolve()
    if a.resume:
        if not (out/"matrix.json").is_file():p.error("resume matrix missing")
    elif out.exists():p.error("output exists; use --resume")
    else:out.mkdir(parents=True)
    with (out/"qualification.lock").open("a+") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:p.error("another process owns qualification output")
        matrix=out/"matrix.json"
        if a.resume:
            try:state=verify_resume(json.loads(matrix.read_text()),proposed)
            except (ValueError,json.JSONDecodeError) as ex:p.error(str(ex))
        else:
            state=proposed
            save(matrix,state)
        if not a.execute:
            print(json.dumps({"layer":a.layer,"collected":len(names),
                              "unassayed":summary(state)["unassayed"],
                              "executed":False}))
            return 0
        pending=[n for n in names if state["cases"][n]["status"] in HAZARDS
                 and n not in state.get("recovery_acknowledged_hazards",[])]
        if pending and not a.recovered_after_fault:
            p.error("prior GPU fault/timeout/interruption requires health inspection")
        if pending:
            state["recovery_acknowledged_hazards"]=sorted(set(
                state.get("recovery_acknowledged_hazards",[]))|set(pending))
        executed=0
        for i,name in enumerate(names):
            if state["cases"][name]["status"]!="unassayed":continue
            state["cases"][name]={"status":"interrupted","start_unix":time.time()}
            state["status"]="running"
            save(matrix,state)
            row=run_case(tool["ctest"],str(testdir),name,a.timeout,out,i)
            state["cases"][name]=row
            state["counts"]=summary(state)
            save(matrix,state)
            executed+=1
            if row["status"] in HAZARDS:
                state["status"]="halted-for-gpu-inspection"
                state["halted_after"]=name
                break
            if executed>=a.batch_size:break
        else:state["status"]="all-tests-attempted"
        if state["status"]=="running":state["status"]="batch-checkpointed"
        state["counts"]=summary(state)
        state["gpu_validated"]=False
        state["release_admitted"]=False
        state["runtime_coherence_verified"]=False
        save(matrix,state)
        print(json.dumps({"layer":a.layer,"executed":executed,
                          "status":state["status"],"counts":state["counts"]},sort_keys=True))
        return 2 if state["status"]=="halted-for-gpu-inspection" else 0

if __name__=="__main__":sys.exit(main())
