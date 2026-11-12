#!/usr/bin/env python3
"""Execute ALL collected upstream OpInfo nodes, with safe resume and receipts.

Consumes the EXACT no-GPU collection matrix. No re-enumeration or selective
dropping. Each pytest node is a separate subprocess/process group, and results
are durably checkpointed before the next node. --resume requires the same
collection bytes and exact source/runtime identities. Faults/timeouts halt
until an explicit operator review/resume; never auto-reset the GPU.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

# The runner is also loaded directly by offline contract tests.  In that
# context Python does not add this file's directory to ``sys.path`` as it does
# when the script is invoked by pathname, so make the sibling assay helpers
# discoverable in both supported entry modes.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from gfx803_upstream_assay import check_source, check_runtime, classify, clean_env, persist

STATES=("pass","fail","unsupported","fault","timeout","unassayed","interrupted")
HALT=("fault","timeout","interrupted")
def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()
def load_collection(path:Path):
    raw=path.read_bytes()
    doc=json.loads(raw)
    ids=doc.get("selected")
    if doc.get("schema")!=1 or doc.get("status")!="collected":
        raise ValueError("requires a completed, non-executed original collection")
    if not isinstance(ids,list) or len(ids)!=1774 or len(set(ids))!=len(ids):
        raise ValueError("expected all 1,774 unique generated OpInfo nodes")
    if doc.get("collected_total")!=len(ids) or set(doc.get("cases",{}))!=set(ids):
        raise ValueError("collection case universe differs from selected test identities")
    if any(doc["cases"][i].get("status")!="unassayed" for i in ids):
        raise ValueError("collection includes existing execution; refuse mixing")
    if not all(isinstance(i,str) and i.startswith("test/test_ops.py::TestCommonCUDA::")
               and "_cuda_" in i for i in ids):
        raise ValueError("unexpected or non-CUDA generated test ID")
    return doc,raw

def validate_profile(collection,source,wrapper,rocm):
    expected={**check_source(source),**check_runtime(wrapper,rocm)}
    if collection.get("provenance")!=expected:
        raise ValueError("collection provenance differs from exact source/runtime")
    return expected

def new_matrix(collection,raw):
    nodes=collection["selected"]
    return {"schema":1,"status":"pending","collection_sha256":digest(raw),
            "provenance":collection["provenance"],
            "selected":nodes,"collected_total":len(nodes),
            "cases":{node:{"status":"unassayed"} for node in nodes},
            "gpu_validated":False,"release_admitted":False,
            "scope":"all 1774 pinned OpInfo nodes; only observed outcomes are evidence"}

def validate_resume(state,collection,raw):
    if state.get("schema")!=1 or state.get("collection_sha256")!=digest(raw):
        raise ValueError("collection hash differs; refuse resume")
    if state.get("provenance")!=collection["provenance"] or state.get("selected")!=collection["selected"]:
        raise ValueError("source/runtime/case universe changed; refuse resume")
    if set(state.get("cases",{}))!=set(collection["selected"]):
        raise ValueError("missing or extra cases")
    for row in state["cases"].values():
        if not isinstance(row,dict) or row.get("status") not in STATES:
            raise ValueError("corrupt case state")
    if state.get("gpu_validated") is not False or state.get("release_admitted") is not False:
        raise ValueError("promotion flag corruption")
    return state

def counts(state):
    statuses=[row["status"] for row in state["cases"].values()]
    return {k:statuses.count(k) for k in STATES}

def unacknowledged_hazards(state):
    """Return hazardous nodes not covered by a prior explicit recovery.

    A recovery acknowledgement is bound to the exact fault/timeout/interrupted
    node set seen at the time of inspection.  It must never implicitly bless a
    later hazardous result merely because a long-running supervisor resumes.
    """
    acknowledged=state.get("recovery_acknowledged_hazards",[])
    if not isinstance(acknowledged,list) or not all(isinstance(node,str) for node in acknowledged):
        raise ValueError("corrupt recovery acknowledgement")
    acknowledged=set(acknowledged)
    return [node for node in state["selected"]
            if state["cases"][node]["status"] in HALT and node not in acknowledged]

def run_one(node,number,source,wrapper,root,timeout,output):
    stdout=output/f"{number:06d}.stdout"
    stderr=output/f"{number:06d}.stderr"
    started=time.monotonic()
    command=[str(wrapper),"-m","pytest","-q",node]
    env=clean_env()
    with stdout.open("wb") as o,stderr.open("wb") as e:
        proc=subprocess.Popen(command,cwd=source,env=env,
                              stdout=o,stderr=e,start_new_session=True)
        try:
            exitcode=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL)
            proc.wait()
            exitcode=None
        except BaseException:
            # An interrupted supervisor must not orphan a live GPU tenant.
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait()
            raise
    evidence=(stdout.read_bytes()+b"\n"+stderr.read_bytes()).decode("utf-8","replace")
    outcome="timeout" if exitcode is None else classify(exitcode,evidence)
    return {"status":outcome,"returncode":exitcode,
            "stdout_file":stdout.name,"stderr_file":stderr.name,
            "stdout_sha256":digest(stdout.read_bytes()),
            "stderr_sha256":digest(stderr.read_bytes()),
            "elapsed_seconds":round(time.monotonic()-started,3)}

def read_discovery_journal(path, nodes, returncode):
    """Map durable worker events; an unfinished current node is a candidate fault."""
    rows={}; active=None
    if path.exists():
        for line in path.read_text().splitlines():
            event=json.loads(line)
            if event["nodeid"] not in nodes: raise ValueError("foreign discovery node")
            if event["event"]=="start": active=event["nodeid"]
            elif event["event"]=="result":
                outcome=event["outcome"]
                rows[event["nodeid"]]={"status":{"passed":"pass","skipped":"unsupported","failed":"fail"}.get(outcome,"fail"),"evidence_lane":"long-lived-discovery"}
                if active==event["nodeid"]: active=None
    if returncode is not None and (returncode < 0 or returncode >= 128) and active and active not in rows:
        rows[active]={"status":"fault","evidence_lane":"long-lived-discovery","fault_candidate":True}
    return rows

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--collection",required=True,type=Path)
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--python-wrapper",required=True,type=Path)
    p.add_argument("--rocm-root",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--execute",action="store_true",
                   help="mandatory explicit consent for GPU execution")
    p.add_argument("--resume",action="store_true")
    p.add_argument("--recover-after-fault",action="store_true",
                   help="manual post-recovery acknowledgement; no automatic GPU reset")
    p.add_argument("--batch-size",type=int,default=24)
    p.add_argument("--timeout",type=int,default=180)
    p.add_argument("--long-lived-discovery",action="store_true",help="one worker; restart only after a recorded fault")
    a=p.parse_args(argv)
    if a.timeout<1 or a.batch_size<1:p.error("timeout and batch-size must be positive")
    if a.recover_after_fault and not a.resume:p.error("recovery only applies to resume")
    try:
        collection,raw=load_collection(a.collection)
        profile=validate_profile(collection,a.source,a.python_wrapper,a.rocm_root)
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as exc:
        p.error(str(exc))
    out=a.out.resolve()
    if a.resume:
        if not (out/"matrix.json").is_file():p.error("resume requires prior matrix.json")
    elif out.exists():p.error("fresh output path required; use --resume")
    else:out.mkdir(parents=True)
    with (out/"runner.lock").open("a+") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:p.error("another assay process owns this output")
        matrix_path=out/"matrix.json"
        if a.resume:
            try:
                state=validate_resume(json.loads(matrix_path.read_text()),collection,raw)
            except (ValueError,KeyError,json.JSONDecodeError) as exc:p.error(str(exc))
        else:
            state=new_matrix(collection,raw)
            persist(matrix_path,state)
        if not a.execute:
            print(json.dumps({"ready":True,"remaining":counts(state)["unassayed"],
                              "execution":False}))
            return 0
        pending_hazards=unacknowledged_hazards(state)
        if pending_hazards and not a.recover_after_fault:
            p.error("prior fault/timeout/interruption; inspect GPU health before --recover-after-fault")
        if pending_hazards:
            state["recovery_acknowledged_hazards"]=sorted(
                set(state.get("recovery_acknowledged_hazards",[])) | set(pending_hazards)
            )
        if a.long_lived_discovery:
            nodes=[node for node in state["selected"] if state["cases"][node]["status"]=="unassayed"]
            if not nodes: print(json.dumps({"status":state["status"],"counts":counts(state)})); return 0
            journal=out/f"discovery-{int(time.time())}.jsonl"; stdout=journal.with_suffix(".stdout"); stderr=journal.with_suffix(".stderr")
            worker=Path(__file__).with_name("gfx803_opinfo_discovery_worker.py")
            state["status"]="running"; state["discovery_active_nodes"]=nodes; persist(matrix_path,state)
            with stdout.open("wb") as o, stderr.open("wb") as e:
                proc=subprocess.Popen([str(profile["python_wrapper"]),str(worker),"--journal",str(journal),*nodes],cwd=profile["source"],env=clean_env(),stdout=o,stderr=e,start_new_session=True)
                try: rc=proc.wait(timeout=a.timeout*len(nodes))
                except subprocess.TimeoutExpired: os.killpg(proc.pid,signal.SIGKILL); proc.wait(); rc=None
            for node,row in read_discovery_journal(journal,nodes,rc).items(): state["cases"][node]=row
            state.pop("discovery_active_nodes",None); state["counts"]=counts(state)
            state["status"]="halted-for-gpu-inspection" if state["counts"]["fault"] else "batch-checkpointed"
            state["halted_after"]=next((n for n in nodes if state["cases"][n]["status"]=="fault"),None)
            state["gpu_validated"]=False; state["release_admitted"]=False; persist(matrix_path,state)
            print(json.dumps({"status":state["status"],"counts":state["counts"]},sort_keys=True)); return 2 if state["counts"]["fault"] else 0
        count=0
        for i,node in enumerate(state["selected"]):
            if state["cases"][node]["status"]!="unassayed":continue
            # Persist a transition before launching so power loss is not
            # misrepresented as an unassayed case with no previous GPU activity.
            state["cases"][node]={"status":"interrupted","start_unix":time.time()}
            state["status"]="running"
            persist(matrix_path,state)
            row=run_one(node,i,profile["source"],profile["python_wrapper"],
                        profile["rocm_root"],a.timeout,out)
            state["cases"][node]=row
            state["counts"]=counts(state)
            persist(matrix_path,state)
            count+=1
            if row["status"] in HALT:
                state["status"]="halted-for-gpu-inspection"
                state["halted_after"]=node
                persist(matrix_path,state)
                break
            if count>=a.batch_size:break
        else:
            state["status"]="all-cases-attempted"
        state["counts"]=counts(state)
        if state["counts"]["unassayed"]==0 and state["counts"]["interrupted"]==0:
            state["status"]="complete-with-results"
        elif state["status"]=="running":
            state["status"]="batch-checkpointed"
        state["selected_nodes_all_pass"]=state["counts"]["pass"]==len(state["selected"])
        state["gpu_validated"]=False
        state["release_admitted"]=False
        persist(matrix_path,state)
        print(json.dumps({"status":state["status"],"batch_executed":count,
                          "counts":state["counts"]},sort_keys=True))
        return 0 if state["status"] in ("batch-checkpointed","complete-with-results","all-cases-attempted") else 2
if __name__=="__main__":sys.exit(main())
