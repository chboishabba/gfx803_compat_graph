#!/usr/bin/env python3
"""T1.14: batch inspect ALL CCOB members for gfx803 metadata with no GPU use.

Consumes a verified fatbin and its header-length member index, extracts
members to temporary files, invokes exact offline clang-offload-bundler
per member, and decodes AMDGPU MessagePack notes. Writes bounded JSON
checkpoints after each inspected member. No HIP or GPU access.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[0]
def load_notes():
    spec=importlib.util.spec_from_file_location("amdgpu_notes",ROOT/"gfx803_amdgpu_msgpack_notes.py")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

TARGET="hip-amdgcn-amd-amdhsa--gfx803"
MAX_SIZE=1024*1024*1024
MAX_MEMBERS=1024

def hash_bytes(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def run(argv:list[str],timeout=60)->dict:
    try:
        result=subprocess.run(argv,capture_output=True,timeout=timeout,check=False)
        return {"exit":result.returncode,
                "stdout":result.stdout[:50000].decode(errors="replace"),
                "stderr":result.stderr[:1200].decode(errors="replace")}
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {"exit":None,"error":str(exc)}

def summarize(data:bytes,decoder)->dict:
    # Actual wrapper may represent an archive or multiple code objects.
    # Only ELF AMDGPU+parseable metadata is admitted.
    r={"sha256":hash_bytes(data),"size_bytes":len(data),
       "elf_amdgpu":False,"metadata_kernels":None,"topk_named":[]}
    if data[:4]!=b"\x7fELF":return r
    try:
        notes=decoder.notes(data)
        kernels=decoder.kernels_from_notes(notes)
    except (ValueError,IndexError) as e:
        r["decode_error"]=str(e)
        return r
    r["elf_amdgpu"]=True
    r["metadata_kernels"]=len(kernels)
    r["topk_named"]=[{"name":k["name"],"properties":k.get("properties",{})}
                     for k in kernels if k.get("topk_name_match")][:30]
    return r

def checkpoint(out:Path,report:dict)->None:
    part=out.with_suffix(".partial")
    part.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    part.replace(out)

def analyze(fatbin:Path,members:dict,bundler:Path,out:Path,*,limit:int|None=None)->dict:
    if out.exists():raise ValueError("refusing to overwrite an existing receipt")
    if not bundler.is_file():raise ValueError("bundler executable does not exist")
    if fatbin.stat().st_size>MAX_SIZE:raise ValueError("oversized fatbin")
    original=fatbin.read_bytes()
    if hash_bytes(original)!=members.get("fatbin_sha256"):
        raise ValueError("indexed fatbin identity mismatch")
    entries=members.get("members",[])
    if not entries or len(entries)>MAX_MEMBERS:
        raise ValueError("invalid member count or missing index")
    decoder=load_notes()
    if limit is not None and (limit<1 or limit>len(entries)):
        raise ValueError("invalid --limit")
    selected=entries[:limit] if limit else entries
    report={"schema":1,"mode":"offline-per-member-offload-attribution",
            "fatbin_sha256":members["fatbin_sha256"],
            "expected_ccob_members":len(entries),
            "inspected_ccob_members":0,
            "target":TARGET,"results":[],
            "complete":False,
            "matched_topk_members":[],
            "runtime_selected_kernel":None,
            "source_binary_build_link_proven":False,
            "limitations":["per-member inclusion does not prove incident kernel launch",
                           "topk name absence does not refute inlined/mangled kernel",
                           "failed bundle parse is recorded, not treated as negative evidence",
                           "no HIP/GPU execution"]}
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gfx803-ccob-offline-") as root:
        temp=Path(root)
        for e in selected:
            start=e["offset"]
            end=start+e["compressed_member_bytes"]
            data=original[start:end]
            if hash_bytes(data)!=e["sha256"]:
                raise ValueError("member SHA mismatch at index "+str(e["index"]))
            member=temp/"member.ccob"
            object_file=temp/"gfx803.o"
            member.write_bytes(data)
            if object_file.exists():object_file.unlink()
            listed=run([str(bundler),"--type=o",f"--input={member}","--list"])
            result={"index":e["index"],"member_sha256":e["sha256"],
                    "list_exit":listed["exit"],"targets":listed.get("stdout","").splitlines()[:10],
                    "status":"not-inspected"}
            if listed["exit"]==0 and TARGET in result["targets"]:
                extracted=run([str(bundler),"--type=o",f"--input={member}",
                               f"--targets={TARGET}",f"--output={object_file}","--unbundle"])
                result["unbundle_exit"]=extracted["exit"]
                if extracted["exit"]==0 and object_file.is_file() and object_file.stat().st_size<=MAX_SIZE:
                    summary=summarize(object_file.read_bytes(),decoder)
                    result.update(summary)
                    result["status"]="inspected-amdgpu-elf" if summary["elf_amdgpu"] else "non-elf-or-unsupported-codeobject"
                else:
                    result["status"]="unbundle-error"
                    result["unbundle_stderr"]=extracted.get("stderr",extracted.get("error",""))[:400]
            elif listed["exit"]!=0:
                result["status"]="list-error"
                result["list_stderr"]=listed.get("stderr",listed.get("error",""))[:400]
            else:
                result["status"]="gfx803-target-not-listed"
            report["results"].append(result)
            report["inspected_ccob_members"]=len(report["results"])
            if result.get("topk_named"):
                report["matched_topk_members"].append(result["index"])
            checkpoint(out,report)
    report["complete"]=len(report["results"])==len(entries)
    checkpoint(out,report)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fatbin",type=Path,required=True)
    p.add_argument("--index-receipt",type=Path,required=True)
    p.add_argument("--bundler",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--limit",type=int,help="optional bounded development run; not complete acceptance")
    a=p.parse_args()
    try:
        result=analyze(a.fatbin,json.loads(a.index_receipt.read_text()),a.bundler,a.out,limit=a.limit)
    except (OSError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
    print("member inspection complete:",result["inspected_ccob_members"],
          "of",result["expected_ccob_members"],
          "topk-named member indexes:",result["matched_topk_members"],
          "GPU calls 0")
if __name__=="__main__":main()
