#!/usr/bin/env python3
"""Offline exact-module KFD branch disassembly receipt.

Reads only the provided .ko or .ko.zst; no kernel or GPU calls.
Requires GNU objdump/readelf and optionally zstd. Module hashes are
checked against the committed KFD handoff. Failed identity = no claim.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

FUNCTIONS=(
    "evict_process_queues_cpsch",
    "unmap_queues_cpsch",
    "remove_queue_mes_on_reset_option.constprop.0",
    "reset_queues_mes",
)
TARGETS=("remove_queue_mes","remove_hw_queue","unmap_queues_cpsch",
         "reset_queues_mes","evict_process_queues_cpsch")
MAX_OUTPUT=1200000

def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def execute(args:list[str],timeout=35)->dict:
    try:
        r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         text=True,timeout=timeout,check=False)
        return {"exit":r.returncode,"stdout":r.stdout[:MAX_OUTPUT],
                "stderr":r.stderr[:8192],"truncated":len(r.stdout)>MAX_OUTPUT}
    except (OSError,subprocess.TimeoutExpired) as e:
        return {"exit":None,"error":str(e),"stdout":"","stderr":""}

def dissect(text:str)->dict:
    lines=text.splitlines()
    calls=[]
    branches=[]
    for line in lines:
        if re.search(r"\b(callq?|jmpq?)\b",line) and any(n in line for n in TARGETS):
            calls.append(line.strip())
        if re.search(r"\b(j[a-z]{1,3})\s",line) and not re.search(r"\b(jmpq?)\s",line):
            branches.append(line.strip())
    return {"named_call_sites":calls[:160],
            "conditional_jumps":branches[:300],
            "warning":"static instruction evidence; no incident-time path selection"}

def audit(module:Path, handoff:dict)->dict:
    expected=handoff.get("running_module",{})
    actual=digest(module)
    compressed=module.name.endswith(".zst")
    wanted=expected.get("sha256") if compressed else expected.get("decompressed_sha256")
    if actual != wanted:
        raise ValueError("module SHA mismatch with handoff: source/binary identity refused")
    with tempfile.TemporaryDirectory(prefix="gfx803-offline-module-") as t:
        elf=Path(t)/"amdgpu.ko"
        if compressed:
            if not shutil.which("zstd"):raise ValueError("zstd required for .ko.zst")
            with elf.open("wb") as out:
                # A module decompression only; does not load/execute kernel code.
                res=subprocess.run(["zstd","-dc",str(module)],stdout=out,
                                   stderr=subprocess.PIPE,timeout=50,check=False)
            if res.returncode:raise ValueError("zstd failed: "+res.stderr.decode(errors="replace")[:200])
        else:
            shutil.copyfile(module,elf)
        uncompressed=digest(elf)
        if uncompressed != expected.get("decompressed_sha256"):
            raise ValueError("decompressed ELF does not match committed module SHA")
        note=execute(["readelf","-n",str(elf)])
        bid=re.search(r"Build ID:\s*([a-fA-F0-9]+)",note["stdout"])
        buildid=bid.group(1) if bid else None
        if not buildid or buildid.lower()!=str(expected.get("build_id","")).lower():
            raise ValueError("module Build ID mismatch or unavailable")
        sections={}
        for name in FUNCTIONS:
            result=execute(["objdump","-drwC","--disassemble="+name,str(elf)],timeout=50)
            sections[name]={
                "exit":result["exit"],
                "contains_function_header":any(name in l for l in result["stdout"].splitlines()[:60]),
                "analysis":dissect(result["stdout"]),
                "stdout_truncated":result.get("truncated",False),
                "stderr":result.get("stderr","")[:800]}
        return {"schema":1,"mode":"offline-binary-disassembly",
                "module_path":str(module),"module_sha256":actual,
                "elf_sha256":uncompressed,"build_id":buildid,
                "reference_source_exact_match":bool(handoff.get("source_package_exact_match")),
                "compiled_functions":sections,"incident_branch":None,
                "incident_return":None,
                "notes":[
                    "objdump checks compiled branch availability, never execution",
                    "compiler-inlined/renamed functions may not be resolved with requested symbol",
                    "relocations and call sites require manual review against exact source",
                    "no GPU operation, live kernel probe, reset or interface manipulation"]}

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--module",type=Path,required=True)
    p.add_argument("--handoff",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():p.error("refusing to overwrite prior evidence")
    if not a.module.is_file() or not a.handoff.is_file():p.error("missing input")
    try:
        result=audit(a.module,json.loads(a.handoff.read_text()))
    except (ValueError,OSError,subprocess.TimeoutExpired) as e:p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("wrote",a.out,"exact module matched, no GPU work")
if __name__=="__main__":raise SystemExit(main())
