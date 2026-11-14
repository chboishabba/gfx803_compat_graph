#!/usr/bin/env python3
"""Join offline KFD and TopK evidence into conservative K2.05/T1 gate verdicts.

No hardware operations; all input files are read-only and required.
"""
import argparse
import hashlib
import json
from pathlib import Path

def load(path:Path)->dict:
    data=json.loads(path.read_text())
    if not isinstance(data,dict):raise ValueError(f"not JSON object: {path}")
    return data

def report(incident:dict, trace:dict, topk:dict, handoff:dict,
           attribution:dict|None=None, elf:dict|None=None)->dict:
    if incident.get("matches_receipt_hash") is not True:
        raise ValueError("incident journal SHA not validated")
    if incident.get("incident_journal_sha256") != handoff.get("journal_sha256"):
        raise ValueError("incident journal not matching original handoff SHA")
    if incident.get("actual_incident_branch") not in (None,"MES","non-MES"):
        raise ValueError("invalid incident branch")
    if topk.get("mode")!="static-only" or incident.get("mode")!="read-only":
        raise ValueError("mixed unsafe/unrecognized evidence kind")
    events=incident.get("first_log_events",{})
    quiesce=events.get("quiesce",{}).get("first")
    preempt=events.get("preemption",{}).get("first")
    branch=incident.get("actual_incident_branch")
    # Never promote a branch from its log wording, current settings or probe inventory.
    gates={
       "K2.03":{"status":"source-mapped","evidence":"original quiescence source path"},
       "K2.04":{"status":"conditional-branches-compiled",
                "reason":"both MES and non-MES exist; historical setting not established"},
       "K2.05":{"status":"open",
                "incident_branch":branch,
                "actual_return":incident.get("actual_evict_return"),
                "reason":"retained journal has no incident-time DQM return or trace"},
       "T1":{"status":"open","first_kernel":topk.get("incident",{}).get("first_dispatched_kernel"),
             "reason":"static wheel/source inventory cannot prove incident GPU dispatch"},
       "J1":{"status":"open","reason":"no paired incident-time GPU dispatch and KFD return"},
       "F1":{"status":"blocked","reason":"no causal kernel/queue repair attributed"},
       "release":{"status":"blocked","reason":"persistent GPU wedge/Wayland loss after unsuccessful recovery"}
    }
    if attribution:
        source=attribution.get("k2_06_reference_attribution",{})
        t1=attribution.get("t1_04_static_candidate",{})
        if not source or not t1:raise ValueError("invalid source attribution receipt")
        gates["K2.06"]={"status":"reference-source-mapped",
            "path":"evict_process_queues_cpsch -> unmap_queues_cpsch -> amdkfd_fence_wait_timeout",
            "incident_return":None,
            "exact_cachyos_match":bool(source.get("reference_source",{}).get("exact_cachyos_package_match"))}
        gates["T1.04"]={"status":"source-candidate",
                        "candidate":"mbtopk","executed_kernel":None,
                        "build_link_proven":False}
    if elf:
        if elf.get("mode")!="offline-binary":raise ValueError("expected offline-binary TopK receipt")
        if not attribution:raise ValueError("must provide source attribution to check ELF identity")
        identity=attribution["t1_04_static_candidate"]["binary"]
        if elf.get("sha256")!=identity.get("sha256") or elf.get("build_id")!=identity.get("build_id"):
            raise ValueError("TopK ELF identity mismatch")
        gates["T1.05"]={"status":"binary-inventory","elf_build_id":elf.get("build_id"),
                         "fatbin_sections":len(elf.get("offload_sections",[])),
                         "actual_executed_hsaco":None,"build_link_proven":False}
    return {"schema":1,"scope":"offline-only","gates":gates,
            "chronology":{"quiesce":quiesce,"non_mes_text":preempt},
            "trace_probe_inventory":trace.get("probes",[]),
            "trace_unresolved":trace.get("unresolved",[]),
            "wheel_provenance":topk.get("torch"),
            "warning":"neither incident branch nor DQM return is established",
            "gpu_rerun":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for s in ("incident","trace","topk","handoff","out"):
        p.add_argument("--"+s,type=Path,required=True)
    p.add_argument("--source-attribution",type=Path)
    p.add_argument("--topk-elf",type=Path)
    a=p.parse_args()
    if a.out.exists():p.error("will not overwrite existing gate report")
    try: data=report(load(a.incident),load(a.trace),load(a.topk),load(a.handoff),
                     load(a.source_attribution) if a.source_attribution else None,
                     load(a.topk_elf) if a.topk_elf else None)
    except (ValueError,OSError,KeyError) as e:p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    print("wrote",a.out,"K2.05=OPEN T1=OPEN; no GPU work")
if __name__=="__main__":main()
