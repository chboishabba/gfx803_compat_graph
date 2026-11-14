#!/usr/bin/env python3
"""T1.09: exact gfx803 HSACO offline metadata, descriptors and symbol inventory.

No torch/ROCm runtime import, GPU initialization, device node access or kernel
execution. The HSACO must match the operator's committed SHA and byte count.
Outputs are bounded. Unsupported LLVM metadata commands are reported rather
than silently promoted to success or inventing kernel launch resources.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

MAX_SIZE = 128 * 1024 * 1024
MAX_OUTPUT = 3 * 1024 * 1024
MAX_MATCH = 2000
PATTERN = re.compile(r"(mbtopk|topk|gather|amdhsa\.kernels|gfx803)", re.I)
TOOL_CANDIDATES = ("llvm-readobj", "/opt/rocm/llvm/bin/llvm-readobj",
                   "/usr/bin/llvm-readobj")
OBJDUMP_CANDIDATES = ("llvm-objdump", "/opt/rocm/llvm/bin/llvm-objdump",
                      "/usr/bin/llvm-objdump")

def hash_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def find_tool(names:tuple[str,...])->str|None:
    for name in names:
        found = shutil.which(name) if "/" not in name else (name if Path(name).is_file() else None)
        if found:return found
    return None

def run(args:list[str],*,limit:int=MAX_OUTPUT)->dict:
    """Bound output without subprocess.run buffering unbounded stdout."""
    try:
        proc=subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdout
        retained=bytearray()
        match_lines=[]
        count=0
        for line in proc.stdout:
            count += 1
            if len(retained)<limit:
                retained.extend(line[:max(0,limit-len(retained))])
            if PATTERN.search(line.decode(errors="replace")) and len(match_lines)<MAX_MATCH:
                match_lines.append(line[:768].decode(errors="replace").rstrip())
        err=proc.stderr.read(4096) if proc.stderr else b""
        ret=proc.wait(timeout=120)
        return {"argv":args,"status":"ok" if ret==0 else "nonzero",
                "exit":ret,"stdout":retained.decode(errors="replace"),
                "truncated":count>retained.count(10)+2,
                "matching_lines":match_lines,"line_count":count,
                "stderr":err.decode(errors="replace")}
    except (OSError,subprocess.TimeoutExpired) as exc:
        if "proc" in locals():
            proc.kill()
            proc.wait()
        return {"argv":args,"status":"error","error":str(exc)}

def detect_header(header:str)->dict:
    machine=re.search(r"Machine:\s*(.*)",header)
    flags=re.search(r"Flags:\s*(.*)",header)
    return {"machine":machine.group(1).strip() if machine else None,
            "flags":flags.group(1).strip() if flags else None,
            "amdgpu_machine_reported":bool(machine and ("AMDGPU" in machine.group(1).upper() or "AMD GPU" in machine.group(1).upper())),
            "gfx803_text_reported":bool(flags and "gfx803" in flags.group(1).lower())}

def parse_sections(text:str)->list[dict]:
    out=[]
    rx=re.compile(r"^\s*\[\s*(\d+)\]\s+(\S+)\s+(\S+)\s+"
                  r"[0-9a-fA-F]+\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)", re.M)
    for m in rx.finditer(text):
        name=m.group(2)
        if name.startswith((".note",".text",".symtab",".strtab",".rodata")):
            out.append({"name":name,"type":m.group(3),"offset":int(m.group(4),16),
                        "size_bytes":int(m.group(5),16)})
    return out

def parse_kernels(text:str)->list[dict]:
    """Extract conservative YAML-like .name blocks; NO metadata values fabricated."""
    kernels=[]
    for m in re.finditer(r"(?m)^\s*(?:-\s*)?\.name:\s*(.+)$",text):
        name=m.group(1).strip().strip("'\"")
        section=text[m.end():m.end()+2500]
        if re.search(r"(?m)^\s*(?:-\s*)?\.name:",section):
            section=section[:re.search(r"(?m)^\s*(?:-\s*)?\.name:",section).start()]
        fields={}
        for key in ("sgpr_count","vgpr_count","group_segment_fixed_size",
                    "private_segment_fixed_size","kernarg_segment_size",
                    "wavefront_size","max_flat_workgroup_size","symbol"):
            q=re.search(r"(?m)^\s*\."+re.escape(key)+r":\s*([^\n#]+)",section)
            if q:fields[key]=q.group(1).strip()[:128]
        kernels.append({"name":name,"fields":fields})
    return kernels[:MAX_MATCH]

def analyze(path:Path,receipt:dict,*,llvm_readobj:str|None=None)->dict:
    expected=receipt.get("unbundled_output") or {}
    if not expected.get("sha256") or not expected.get("size_bytes"):
        raise ValueError("receipt lacks exact unbundled HSACO identity")
    if not path.is_file() or path.stat().st_size>MAX_SIZE:
        raise ValueError("HSACO missing or size exceeds strict bound")
    if path.stat().st_size!=expected["size_bytes"]:
        raise ValueError("HSACO size mismatch")
    actual=hash_file(path)
    if actual!=expected["sha256"]:
        raise ValueError("HSACO SHA mismatch; refuse candidate attribution")
    with path.open("rb") as stream:
        ehdr=stream.read(64)
    if ehdr[:4]!=b"\x7fELF" or len(ehdr)<64:
        raise ValueError("unbundled target not a valid ELF header")
    if int.from_bytes(ehdr[18:20],"little")!=224:
        raise ValueError("unbundled ELF machine is not AMDGPU (224)")
    if not shutil.which("readelf"):
        raise ValueError("GNU readelf required")
    calls={
        "header":run(["readelf","-h",str(path)]),
        "sections":run(["readelf","-WS",str(path)]),
        "notes":run(["readelf","-n",str(path)]),
        "symbols":run(["readelf","-Ws",str(path)],limit=512*1024),
    }
    if calls["header"]["status"]!="ok" or calls["sections"]["status"]!="ok":
        raise ValueError("ELF header and sections must be readable")
    hdr=detect_header(calls["header"].get("stdout",""))
    hdr["machine_code"]=224
    hdr["machine_verified_from_elf_header"]=True
    opt=llvm_readobj or find_tool(TOOL_CANDIDATES)
    metadata={"status":"tool-unavailable","commands":[]}
    if opt:
        attempts=[
            run([opt,"--amdgpu-code-object-metadata",str(path)],limit=MAX_OUTPUT),
            run([opt,"--notes","--file-headers",str(path)],limit=MAX_OUTPUT),
        ]
        metadata={
            "status":"metadata-output-available" if attempts[0]["status"]=="ok" else "specific-metadata-option-unavailable",
            "commands":[{"argv":x.get("argv"),"status":x["status"],
                         "stderr":x.get("stderr",""),
                         "truncated":x.get("truncated",False)} for x in attempts],
            "raw_excerpt":attempts[0].get("stdout","")[:MAX_OUTPUT] if attempts[0]["status"]=="ok" else attempts[1].get("stdout","")[:MAX_OUTPUT],
            "kernel_blocks":parse_kernels(attempts[0].get("stdout","")) if attempts[0]["status"]=="ok" else [],
            "matching_lines":attempts[0].get("matching_lines",[]) if attempts[0]["status"]=="ok" else attempts[1].get("matching_lines",[])
        }
    note_text=calls["notes"].get("stdout","")
    kernel_names=metadata.get("kernel_blocks",[])
    topk=[k for k in kernel_names if PATTERN.search(k["name"])]
    return {"schema":1,"mode":"offline-hsaco-metadata",
            "path":str(path),"sha256":actual,"size_bytes":path.stat().st_size,
            "identity_verified":True,"target_from_bundle":receipt.get("gfx803_candidates",[]),
            "header":hdr,"sections":parse_sections(calls["sections"]["stdout"]),
            "note_matching_lines":calls["notes"].get("matching_lines",[]),
            "symbol_matching_lines":calls["symbols"].get("matching_lines",[]),
            "metadata":metadata,
            "metadata_kernel_count_parsed":len(kernel_names),
            "topk_kernel_blocks":topk,
            "topk_kernel_detected":bool(topk),
            "incident_execution_verified":False,
            "actual_incident_kernel":None,
            "actual_grid":None,
            "source_binary_build_link_verified":False,
            "limits":["gfx803 inclusion != incident GPU execution",
                      "stripped or mangled kernels may have no readable TopK names",
                      "metadata parser extracts only named blocks in supported YAML-like presentation",
                      "readelf and LLVM version differences may leave counts incomplete",
                      "no actual launch, block size or wave occupancy recorded"]}

def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hsaco",type=Path,required=True)
    p.add_argument("--container-receipt",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--llvm-readobj",type=str)
    a=p.parse_args()
    if a.out.exists():p.error("refusing overwrite")
    try: result=analyze(a.hsaco,json.loads(a.container_receipt.read_text()),
                        llvm_readobj=a.llvm_readobj)
    except (OSError,KeyError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("HSACO checked; TopK named metadata:",len(result["topk_kernel_blocks"]),
          "GPU runs: 0")
if __name__=="__main__":main()
