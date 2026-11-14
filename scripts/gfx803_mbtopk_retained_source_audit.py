#!/usr/bin/env python3
"""T1.10 offline pre-review mbtopk source/launch and provenance assessment.

Hashes the exact retained source and candidate binary identifiers before
extracting lexical function bodies/launch terms. This is a *static*
audit, not a C++ parser, compiled launch trace, or proof of linkage.
Only specified files searched. No recursive filesystem/NFS walk.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

FUNCTIONS=("should_use_multiblock","mbtopk","launch_mbtopk",
           "gatherTopK","topk_impl","topk_kernel","warptopk",
           "sbtopk")
TOKENS=("hipLaunchKernelGGL","<<<","dim3","grid","block","workgroup",
        "HIP_KERNEL_NAME","mbtopk","should_use_multiblock",
        "num_slices","slice_size","block_size","num_blocks",
        "temporary","workspace","cudaMalloc","hipMalloc",
        "getCurrentHIPStream","getCurrentCUDAStream")
MAX_FILE=8*1024*1024

def sha256(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def function_spans(source:str,name:str)->list[dict]:
    """Heuristic balanced brace extraction, explicit uncertainty."""
    result=[]
    token=re.compile(r"\b"+re.escape(name)+r"\s*(?:<[^;{}]{0,256}>)?\s*\(",re.M)
    for m in token.finditer(source):
        cursor=m.end()
        depth=1
        while cursor<len(source) and depth>0:
            if source[cursor]=="(":depth+=1
            if source[cursor]==")":depth-=1
            cursor+=1
        if depth:continue
        brace=source.find("{",cursor,min(len(source),cursor+600))
        semi=source.find(";",cursor,min(len(source),cursor+600))
        if brace<0 or (semi>=0 and semi<brace):continue
        d=1;j=brace+1
        while j<len(source) and d>0:
            if source[j]=="{":d+=1
            elif source[j]=="}":d-=1
            j+=1
        if d:continue
        before=source[:m.start()].count("\n")+1
        after=source[:j].count("\n")+1
        excerpt=source[m.start():j]
        result.append({"function":name,"line_start":before,
                       "line_end":after,"text_sha256":hashlib.sha256(excerpt.encode()).hexdigest(),
                       "excerpt":excerpt[:15000],"truncated":len(excerpt)>15000})
        if len(result)>=8:break
    return result

def audit(source_path:Path,receipt:dict)->dict:
    old=receipt["t1_04_static_candidate"]["retained_pre_review_source"]
    if source_path.stat().st_size>MAX_FILE:raise ValueError("source exceeds bounded size")
    binary=source_path.read_bytes()
    source_hash=hashlib.sha256(binary).hexdigest()
    if source_hash!=old["sha256"]:
        raise ValueError("retained TensorTopK.hip SHA mismatch")
    text=binary.decode("utf8",errors="replace")
    matched=[]
    for i,line in enumerate(text.splitlines(),1):
        if any(token in line for token in TOKENS):
            matched.append({"line":i,"text":line[:700]})
    spans=[block for fun in FUNCTIONS for block in function_spans(text,fun)]
    return {"schema":1,"mode":"static-retained-source",
            "source_path":str(source_path),"sha256":source_hash,
            "source_verified":True,
            "route_from_retained_attribution":{
                "row_1":"mbtopk candidate","row_32":"mbtopk candidate",
                "proof_scope":"retained source-level shape predicate only"},
            "selected_source_terms":matched[:2000],
            "matching_line_count":len(matched),
            "function_spans":spans,
            "source_binary_build_link_proven":False,
            "actual_kernel_launch":None,
            "launch_parameters_proven_for_incident":False,
            "bounds":{"row_1":{"elements":151936,"f32_bytes":607744},
                      "row_32":{"elements":4861952,"f32_bytes":19447808}},
            "limits":["text brace extraction is heuristic, not C++ semantic analysis",
                      "source route is not evidence of benchmark-loaded ELF",
                      "grid, workspaces and synchronization must be interpreted from source and compiled descriptors",
                      "no HIP or GPU workload"]}

def inspect_log(path:Path,expected_source:str,expected_elf:str)->dict:
    if path.stat().st_size>8*1024*1024:
        raise ValueError("build log/manifest exceeds strict read bound")
    text=path.read_text(errors="replace")
    return {"path":str(path),"sha256":sha256(path),
            "source_hash_literal_found":expected_source in text,
            "elf_hash_literal_found":expected_elf in text,
            "candidate_lines":[{"line":i,"text":line[:400]}
                  for i,line in enumerate(text.splitlines(),1)
                  if any(s in line for s in (expected_source,expected_elf,
                         "TensorTopK.hip","libtorch_hip.so","hipcc",
                         "clang++","ROCM_PATH","HIP_PATH","CMAKE_HIP_ARCHITECTURES"))][:200],
            "build_link_verdict":"not-proven",
            "note":"two hashes in a log alone may be incidental; require build invocation and output lineage"}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--attribution-receipt",type=Path,required=True)
    p.add_argument("--build-log",type=Path,action="append",default=[],
                   help="explicit retained original logs/manifests, no recursive search")
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():p.error("refuse overwrite")
    try:
        attribution=json.loads(args.attribution_receipt.read_text())
        result=audit(args.source,attribution)
        elfsha=attribution["t1_04_static_candidate"]["binary"]["sha256"]
        result["retained_build_artifacts"]=[
            inspect_log(path,result["sha256"],elfsha) for path in args.build_log]
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as e:p.error(str(e))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("source verified; original source-binary build link still unknown; GPU calls 0")
if __name__=="__main__":main()
