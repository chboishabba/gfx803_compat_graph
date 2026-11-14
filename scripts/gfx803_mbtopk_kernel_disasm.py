#!/usr/bin/env python3
"""T1.12 bounded static AMDGPU kernel disassembly from verified HSACO metadata.

Explicit symbol must occur in decoded kernel note metadata; no speculative
name substitution. If notes lack names, records a blocked inspection.
Never imports torch/HIP, attaches to GPU or runs the code.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

MAX_OUTPUT=2*1024*1024
def verify(hsaco:Path,notes:dict)->None:
    if notes.get("mode")!="offline-amdgpu-msgpack-note":
        raise ValueError("unrecognized AMDGPU notes receipt")
    h=hashlib.sha256()
    with hsaco.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    if h.hexdigest()!=notes.get("hsaco_sha256") or hsaco.stat().st_size!=notes.get("hsaco_size_bytes"):
        raise ValueError("HSACO integrity does not match note receipt")

def kernel_symbols(notes:dict)->list[str]:
    candidates=[]
    for k in notes.get("kernels",[]):
        if not isinstance(k,dict):continue
        name=k.get("properties",{}).get(".symbol") or k.get("name")
        if isinstance(name,str) and len(name)<1024 and name not in candidates:
            candidates.append(name)
    return candidates

def instruction_kinds(text:str)->dict:
    kinds={
        "s_barrier":r"\bs_barrier\b",
        "s_waitcnt":r"\bs_waitcnt\b",
        "global_load":r"\b(?:global|flat|buffer)_load\w*\b",
        "global_store":r"\b(?:global|flat|buffer)_store\w*\b",
        "atomic":r"\b(?:flat|global|buffer|ds)_atomic\w*\b",
        "branch":r"\b(?:s_cbranch|s_branch)\w*\b",
        "endpgm":r"\bs_endpgm\b",
    }
    return {kind:len(re.findall(rx,text)) for kind,rx in kinds.items()}

def disassemble(hsaco:Path,notes:dict,kernel:str|None,tool:str|None)->dict:
    verify(hsaco,notes)
    choices=kernel_symbols(notes)
    result={"schema":1,"mode":"offline-amdgpu-disassembly",
            "hsaco_sha256":notes["hsaco_sha256"],"available_metadata_symbols":choices[:500],
            "chosen_kernel":None,"status":"no-action","instruction_counts":None,
            "actual_incident_execution":False,"causal_defect_proven":False}
    if not kernel:
        result["status"]="no-kernel-selected; inspection requires metadata-verified symbol"
        return result
    if kernel not in choices:
        raise ValueError("explicit kernel is not in decoded metadata symbol list")
    found=tool or shutil.which("llvm-objdump") or (
        "/opt/rocm/llvm/bin/llvm-objdump" if Path("/opt/rocm/llvm/bin/llvm-objdump").is_file() else None)
    if not found:raise ValueError("llvm-objdump unavailable; kernel not disassembled")
    argv=[found,"--no-show-raw-insn","--disassemble-symbols="+kernel,str(hsaco)]
    try:
        p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise ValueError("llvm-objdump invocation failed: "+str(exc))
    if p.returncode:
        raise ValueError("llvm-objdump failed; check version/option: "+p.stderr[:500].decode(errors="replace"))
    if len(p.stdout)>MAX_OUTPUT:
        result["status"]="disassembly-output-too-large"
        result["full_output_sha256"]=hashlib.sha256(p.stdout).hexdigest()
        return result
    text=p.stdout.decode(errors="replace")
    result.update({"chosen_kernel":kernel,"status":"disassembled",
                   "tool_argv":argv,"disassembly_excerpt":text,
                   "instruction_counts":instruction_kinds(text)})
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hsaco",type=Path,required=True)
    p.add_argument("--note-metadata",type=Path,required=True)
    p.add_argument("--kernel",type=str,help="must be selected from verified AMDGPU note symbols")
    p.add_argument("--llvm-objdump",type=str)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():p.error("no overwrite")
    try:r=disassemble(a.hsaco,json.loads(a.note_metadata.read_text()),a.kernel,a.llvm_objdump)
    except (OSError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
    print("static kernel disassembly status:",r["status"],"; no GPU execution")
if __name__=="__main__":main()
