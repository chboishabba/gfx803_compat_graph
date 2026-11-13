#!/usr/bin/env python3
"""Original Schaka pooling with ONLY documented do_backward=false workspace cut.

The diagnostic preserves CPU reference, 42 cases, queue handling, and all
other MIOpen operations. Replaces the original true-workspace allocation
with null workspace + size 0 as required by MIOpen forward-only API.
A passing run does not attribute historic faults to the workspace path.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from gfx803_pool_original_runtime_matrix import validate_build, classify, sha_file, persist, kernel_logs

WORKSPACE_OLD="""    size_t ws_size = 0;
    miopenPoolingGetWorkSpaceSizeV2(poolDesc, yDesc, &ws_size);
    void* d_ws = nullptr;
    if (ws_size > 0) CHECK_HIP(hipMalloc(&d_ws, ws_size));"""
WORKSPACE_NEW="""    size_t ws_size = 0;
    void* d_ws = nullptr;  // forward-only MIOpen contract"""
CALL_OLD="d_y, true, d_ws, ws_size);"
CALL_NEW="d_y, false, nullptr, 0);"

def derivative(source):
    if source.count(WORKSPACE_OLD)!=1 or source.count(CALL_OLD)!=1:
        raise ValueError("original pooling workspace/call layout changed")
    result=source.replace(WORKSPACE_OLD,WORKSPACE_NEW).replace(CALL_OLD,CALL_NEW)
    if result.count(CALL_NEW)!=1 or "size_t ws_size = 0;" not in result:
        raise ValueError("invalid modified forward-only semantics")
    return result

def run_command(command,cwd,env,out,err,timeout):
    with out.open("wb") as o,err.open("wb") as e:
        p=subprocess.Popen(command,cwd=cwd,env=env,stdout=o,stderr=e,start_new_session=True)
        try:rc=p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.wait();rc=None
        except BaseException:
            if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
            raise
    return rc

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build-receipt",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--build",action="store_true")
    ap.add_argument("--execute",action="store_true")
    ap.add_argument("--timeout",type=int,default=180)
    ap.add_argument("--build-timeout",type=int,default=900)
    a=ap.parse_args(argv)
    if a.timeout<1 or a.build_timeout<1:ap.error("positive timeouts required")
    if a.out.exists() and a.build:ap.error("fresh directory required for build")
    try:
        build,original_bin,prefix,original=validate_build(a.build_receipt)
        original_text=original.read_text()
        code=derivative(original_text)
        hipcc=Path(build["hipcc"]).resolve()
        if not hipcc.is_file() or not str(hipcc).startswith("/nix/store/"):
            raise ValueError("original immutable Nix compiler missing")
        ident={"schema":1,"old_build_sha256":sha_file(a.build_receipt),
               "original_source_sha256":sha_file(original),
               "original_pool_binary_sha256":sha_file(original_bin),
               "derived_source_sha256":hashlib.sha256(code.encode()).hexdigest(),
               "hipcc":str(hipcc),"hipcc_sha256":sha_file(hipcc),
               "rocm_prefix":str(prefix),
               "workspace_contract":"do_backward=false and workspace=null/size=0"}
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as exc:ap.error(str(exc))
    out=a.out.resolve()
    if not out.exists():out.mkdir(parents=True)
    source=out/"pool_forward_only.cpp"
    binary=out/"pool_forward_only"
    receipt=out/"build.json"
    if a.build:
        source.write_text(code)
        env=os.environ.copy()
        env["PATH"]=str(hipcc.parent)+os.pathsep+env.get("PATH","")
        cmd=[str(hipcc),"-O2","-I"+str(original.parent),
             "-I"+str(prefix/"include"),str(source),"-o",str(binary),
             "-L"+str(prefix/"lib"),"-lMIOpen","-lm",
             "-Wl,-rpath,"+str(prefix/"lib")]
        rc=run_command(cmd,out,env,out/"compile.stdout",out/"compile.stderr",a.build_timeout)
        result={**ident,"build_returncode":rc,
                "status":"built" if rc==0 and binary.is_file() else "build-failed",
                "binary_sha256":sha_file(binary) if rc==0 and binary.is_file() else None,
                "release_admitted":False}
        persist(receipt,result)
        if result["status"]!="built":return 2
    if not receipt.is_file():ap.error("no compiled derivative; run --build first")
    previous=json.loads(receipt.read_text())
    if any(previous.get(k)!=v for k,v in ident.items()) or previous.get("status")!="built":
        ap.error("original source/build/runtime identity drift")
    if not binary.is_file() or sha_file(binary)!=previous.get("binary_sha256"):
        ap.error("derivative binary hash mismatch")
    if not source.is_file() or source.read_text()!=code:
        ap.error("source derivative mismatch")
    if not a.execute:
        print(json.dumps({"built":True,"gpu_executed":False,
                          "do_backward":False,"workspace_bytes":0}));return 0
    result_file=out/"matrix.json"
    if result_file.exists():ap.error("refuse rerunning an existing GPU evidence receipt")
    env=os.environ.copy()
    env.pop("LD_PRELOAD",None)
    old=env.get("LD_LIBRARY_PATH","")
    env["LD_LIBRARY_PATH"]=str(prefix/"lib")+(os.pathsep+old if old else "")
    start=time.time()
    rc=run_command([str(binary)],out,env,out/"stdout.log",out/"stderr.log",a.timeout)
    row=classify(rc,(out/"stdout.log").read_bytes(),(out/"stderr.log").read_bytes())
    row.update(ident)
    row["elapsed_seconds"]=round(time.time()-start,3)
    row["original_binary_not_run"]=True
    row["stdout_sha256"]=sha_file(out/"stdout.log")
    row["stderr_sha256"]=sha_file(out/"stderr.log")
    row["kernel_journal"]=kernel_logs(start-2,out/"kernel.log")
    row["release_admitted"]=False
    row["gpu_validated"]=False
    persist(result_file,row)
    print(json.dumps({"status":row["status"],"returncode":rc,
                      "workspace_contract":ident["workspace_contract"]}))
    return 0 if row["status"]=="pass" else 2

if __name__=="__main__":sys.exit(main())
