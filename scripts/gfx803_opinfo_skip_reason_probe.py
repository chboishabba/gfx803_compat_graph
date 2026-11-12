#!/usr/bin/env python3
"""Recover exact PyTorch skip annotations for the 183 original OpInfo skips.

The default 'static' phase collects pytest marks WITHOUT executing test setup
or any test body. An optional 'setup' phase examines runtime skip reasons in
isolated subprocesses, but blocks all test call bodies. Pytest setup/fixtures
may still touch a GPU: run setup only on a healthy, idle GPU host.
Original discovery matrix/receipt remains immutable.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

SOURCE_PIN="d70fd61bab718a3d49b053efa8058efc0566b2b0"
MATRIX_SHA="47c7ed58d7b549abfc038b534faaaa9ecaf6ee2fc18b3ba55addebeed02b7e36"
GUARD="GFX803_SKIP_REASON_PROBE_BLOCKED_TEST_BODY"

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_audit(path):
    data=path.read_bytes()
    audit=json.loads(data)
    rows=audit.get("rows",[])
    if audit.get("schema")!=1 or audit.get("source_matrix_sha256")!=MATRIX_SHA:
        raise ValueError("audit must be bound to the exact original discovery matrix")
    if audit.get("unsupported_count")!=183 or len(rows)!=183:
        raise ValueError("expected exactly 183 original skipped cases")
    ids=[r.get("nodeid") for r in rows]
    if len(set(ids))!=183 or not all(isinstance(i,str) and
            i.startswith("test/test_ops.py::TestCommonCUDA::") and "_cuda_" in i for i in ids):
        raise ValueError("invalid original node IDs")
    if any(r.get("original_status")!="unsupported" or r.get("reason") is not None
           for r in rows):
        raise ValueError("audit must preserve the historical reasonless skips")
    return ids,digest(data)

def guard_source(path):
    import subprocess as sp
    target=path.resolve()
    check=sp.run(["git","-C",str(target),"rev-parse","HEAD"],capture_output=True,text=True)
    if check.returncode or check.stdout.strip()!=SOURCE_PIN:
        raise ValueError("unpinned PyTorch test source")
    if not (target/"test/test_ops.py").is_file():
        raise ValueError("missing source test suite")
    dirty=sp.run(["git","-C",str(target),"status","--porcelain","--",
                  "test/test_ops.py","torch/testing/_internal"],capture_output=True,text=True)
    if dirty.returncode or dirty.stdout.strip():
        raise ValueError("test sources changed from pinned revision")
    return target

def persist(path,record):
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
    os.replace(tmp,path)

def marker_record(item):
    markers=[]
    for marker in item.iter_markers():
        if marker.name not in ("skip","skipif","xfail"):continue
        markers.append({"name":marker.name,
                        "reason":str(marker.kwargs.get("reason","")),
                        "conditions":[repr(arg) for arg in marker.args]})
    return markers

def child_complete(child,batch):
    """A collection is valid only if every requested generated node exists."""
    return (child.get("pytest_returncode")==0 and
            set(child.get("nodes",{}))==set(batch))

class Capture:
    def __init__(self,mode):
        self.mode=mode
        self.rows={}
        self.reported={}
    def pytest_collection_modifyitems(self,items):
        for item in items:
            self.rows[item.nodeid]={"markers":marker_record(item),
                                    "runtime_outcome":"not-run"}
    def pytest_runtest_call(self,item):
        import pytest
        # Even when upstream skip policy disappears, never run the op body.
        pytest.skip(GUARD)
    def pytest_runtest_logreport(self,report):
        if report.when in ("setup","call"):
            if report.skipped:
                reason=str(report.longrepr)
                self.reported[report.nodeid]={"runtime_outcome":(
                    "probe-blocked-call" if GUARD in reason else "upstream-skipped"),
                    "skip_reason":reason,"phase":report.when}
            elif report.failed:
                self.reported[report.nodeid]={"runtime_outcome":"setup-failed" if
                    report.when=="setup" else "unexpected-call-failure",
                    "details":str(report.longrepr),"phase":report.when}
    def finished(self):
        for node,row in self.rows.items():
            row.update(self.reported.get(node,{}))
        return self.rows

def worker(mode,source,nodeids,out):
    # CUDA OpInfo nodes are generated conditionally.  Do not hide the device
    # here: doing so changes the collected node IDs and cannot recover reasons
    # for the historical CUDA results.  --collect-only below still prevents
    # setup and test-body execution in static mode.
    import pytest
    cap=Capture(mode)
    args=["-q"]
    if mode=="static":args.append("--collect-only")
    args.extend(nodeids)
    rc=pytest.main(args,plugins=[cap])
    result={"schema":1,"phase":mode,"pytest_returncode":int(rc),
            "nodes":cap.finished(),"release_admitted":False,
            "gpu_body_executed":False}
    persist(out,result)
    return 0 if int(rc)==0 and set(result["nodes"])==set(nodeids) else 2

def supervise(command,cwd,timeout,outprefix):
    import subprocess as sp
    with outprefix.with_suffix(".stdout").open("wb") as stdout,\
         outprefix.with_suffix(".stderr").open("wb") as stderr:
        proc=sp.Popen(command,cwd=cwd,stdout=stdout,stderr=stderr,
                      start_new_session=True)
        try:rc=proc.wait(timeout=timeout)
        except sp.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL)
            proc.wait()
            rc=None
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait()
            raise
    return rc

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit",type=Path,required=True)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--python-wrapper",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--mode",choices=("static","setup"),default="static")
    p.add_argument("--start",type=int,default=0)
    p.add_argument("--limit",type=int,default=0,help="0 = all remaining cases")
    p.add_argument("--timeout",type=int,default=90)
    p.add_argument("--execute-setup",action="store_true")
    p.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    p.add_argument("--nodes-file",type=Path,help=argparse.SUPPRESS)
    a=p.parse_args(argv)
    if a.timeout<1 or a.start<0 or a.limit<0:p.error("invalid bounds")
    if a.worker:
        nodes=json.loads(a.nodes_file.read_text())
        return worker(a.mode,a.source,nodes,a.out)
    try:
        ids,audit_sha=read_audit(a.audit)
        source=guard_source(a.source)
    except (ValueError,OSError,KeyError) as e:p.error(str(e))
    if a.mode=="setup" and not a.execute_setup:
        p.error("setup may initialize GPU fixtures; explicit --execute-setup required")
    wrapper=a.python_wrapper.resolve()
    if not str(wrapper).startswith("/nix/store/") or not wrapper.is_file():
        p.error("require existing immutable Nix pytest Python wrapper")
    selected=ids[a.start:a.start+a.limit if a.limit else None]
    if not selected:p.error("empty selected range")
    if a.out.exists():p.error("refuse to overwrite an existing evidence directory")
    a.out.mkdir(parents=True)
    report={"schema":1,"mode":a.mode,"original_matrix_sha256":MATRIX_SHA,
            "audit_sha256":audit_sha,"pytorch_source":SOURCE_PIN,
            "python_wrapper":str(wrapper),"selected_nodes":selected,
            "status":"running","cases":{node:{"status":"unassayed"} for node in selected},
            "gpu_body_executed":False,"release_admitted":False}
    persist(a.out/"matrix.json",report)
    batches=[selected] if a.mode=="static" else [[node] for node in selected]
    for number,batch in enumerate(batches):
        prefix=a.out/f"{number:04d}"
        nodes_file=prefix.with_suffix(".nodes.json")
        nodes_file.write_text(json.dumps(batch)+"\n")
        receipt=prefix.with_suffix(".result.json")
        cmd=[str(wrapper),str(Path(__file__).resolve()),"--worker","--audit",str(a.audit),
             "--source",str(source),"--python-wrapper",str(wrapper),
             "--out",str(receipt),"--mode",a.mode,"--nodes-file",str(nodes_file)]
        if a.mode=="setup":cmd.append("--execute-setup")
        t=time.monotonic()
        rc=supervise(cmd,source,a.timeout,prefix)
        child=None
        if receipt.is_file():
            try: child=json.loads(receipt.read_text())
            except (ValueError,OSError): pass
        complete=bool(child is not None and child_complete(child,batch))
        for node in batch:
            row={"status":"missing-worker-receipt","returncode":rc}
            if complete:
                row=child["nodes"].get(node,{"status":"missing-collected-node"})
                # `runtime_outcome: not-run` is expected for --collect-only;
                # the evidence status is that its source marker was collected.
                row["status"]="collected"
            elif child is not None:
                row={"status":"incomplete-worker-receipt","returncode":rc,
                     "worker_pytest_returncode":child.get("pytest_returncode"),
                     "collected_node_count":len(child.get("nodes",{}))}
            if rc is None:row["status"]="timeout"
            elif rc<0 or rc>=128:row["status"]="fault"
            row["elapsed_batch_seconds"]=round(time.monotonic()-t,3)
            report["cases"][node]=row
        persist(a.out/"matrix.json",report)
        if not complete:
            report["status"]=("halted-for-host-inspection" if rc is None or rc<0 or rc>=128
                              else "incomplete-collection")
            break
    else:
        report["status"]="reason-probe-complete"
    persist(a.out/"matrix.json",report)
    print(json.dumps({"status":report["status"],"selected":len(selected),
                      "observed":sum(r["status"]!="unassayed" for r in report["cases"].values())}))
    return 0 if report["status"]=="reason-probe-complete" else 2

if __name__=="__main__":raise SystemExit(main())
