#!/usr/bin/env python3
"""K2.07 read-only exact-v7.3-reference non-MES eviction/fence source audit.

Uses ONLY explicitly supplied files. Identifies source log sites and function
context; maps possible errors but does NOT fill the missing incident errno,
assert exact CachyOS patchset equality, or probe a GPU. Provides instructions
for a separate host trace only after safety qualification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

TERMS=("amdkfd_fence_wait_timeout","unmap_queues_cpsch",
       "evict_process_queues_cpsch",
       "unsuccessful queues preemption",
       "Failed to quiesce KFD",
       "enable_mes","enable_uni_mes")
MAX_SIZE=3*1024*1024

def scan(path:Path)->dict:
    if not path.is_file() or path.stat().st_size>MAX_SIZE:
        raise ValueError("missing or too large source file: "+str(path))
    raw=path.read_bytes()
    lines=raw.decode("utf8",errors="replace").splitlines()
    hits={}
    for term in TERMS:
        matches=[i+1 for i,line in enumerate(lines) if term in line]
        if matches:
            hits[term]=[{"line":i,"context":"\n".join(
                f"{j+1}: {lines[j][:350]}" for j in
                range(max(0,i-4),min(len(lines),i+3)))} for i in matches[:24]]
    return {"path":str(path),"sha256":hashlib.sha256(raw).hexdigest(),
            "term_hits":hits}

def assemble(items:list[dict],handoff:dict)->dict:
    ref=handoff.get("reference_source",{})
    nonmes=any("unsuccessful queues preemption" in x["term_hits"] for x in items)
    fence=any("amdkfd_fence_wait_timeout" in x["term_hits"] for x in items)
    return {"schema":1,"mode":"offline-kfd-source-audit",
            "reference_revision":ref.get("revision"),
            "exact_cachyos_source_match":bool(handoff.get("source_package_exact_match")),
            "source_files":items,
            "reference_log_site_found":nonmes,
            "fence_function_name_found":fence,
            "reference_non_mes_path":"evict_process_queues_cpsch -> unmap_queues_cpsch -> amdkfd_fence_wait_timeout",
            "incident_return_code":None,
            "actual_incident_caller":None,
            "diagnostic_strength":"consistent with non-MES fence timeout in cited reference source"
                                   if nonmes and fence else "insufficient source files to crosscheck",
            "limits":["source text does not capture incident-time stack or errno",
                      "current source is not necessarily exact CachyOS patchset",
                      "no GPU tracing or kernel modifications"]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,action="append",required=True,
                   help="exact targeted C source files; repeat; never recursively search")
    p.add_argument("--handoff",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():p.error("no overwrite")
    try:
        files=[scan(x) for x in a.source]
        result=assemble(files,json.loads(a.handoff.read_text()))
    except (OSError,KeyError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("KFD source mapping saved; incident return remains unknown")
if __name__=="__main__":main()
