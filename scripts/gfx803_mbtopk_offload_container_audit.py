#!/usr/bin/env python3
"""Offline HIP .hip_fatbin container classifier and clang-offload-bundler inventory.

No GPU work, HIP import, kernel tracing or automatic decompression.
Recognizes CCOB, __CLANG_OFFLOAD_BUNDLE__, direct ELF and unknown.
Uses clang-offload-bundler --list if available; never assumes a target exists.
Bounded, read-only input inspection; optional --unbundle-gfx803 writes ONE
selected output only if exact target ID is advertised by --list.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

BUNDLE_MAGIC=b"__CLANG_OFFLOAD_BUNDLE__"
MAX_INPUT=1024*1024*1024
MAX_ENTRIES=4096
MAX_ID=512
MAX_LIST=10000

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def parse_uncompressed(prefix:bytes,size:int)->dict:
    if len(prefix)<len(BUNDLE_MAGIC)+8:
        return {"status":"incomplete-header"}
    count=struct.unpack_from("<Q",prefix,len(BUNDLE_MAGIC))[0]
    if count>MAX_ENTRIES:
        return {"status":"invalid-entry-count","count":count}
    pos=len(BUNDLE_MAGIC)+8
    entries=[]
    for i in range(count):
        if pos+24>len(prefix):
            return {"status":"header-beyond-inspection-prefix","count":count,
                    "parsed_entries":entries}
        off,n,id_len=struct.unpack_from("<QQQ",prefix,pos)
        pos+=24
        if id_len>MAX_ID or pos+id_len>len(prefix):
            return {"status":"invalid-or-incomplete-entry-id","entry_index":i,
                    "parsed_entries":entries}
        ident=prefix[pos:pos+id_len].decode("utf8",errors="replace")
        pos+=id_len
        if off+n>size or off<pos:
            # Permit empty host bundle, whose offset can be zero.
            if n!=0:
                return {"status":"invalid-entry-range","entry_index":i,
                        "parsed_entries":entries}
        entries.append({"target":ident,"offset":off,"size_bytes":n})
    return {"status":"parsed-header","entry_count":count,"entries":entries,
            "note":"Clang bundle header entries are not proof of a selected runtime kernel"}

def classify(header:bytes,size:int)->dict:
    if header.startswith(b"CCOB"):
        if len(header)<8:return {"kind":"ccob","status":"incomplete-header"}
        version,method=struct.unpack_from("<HH",header,4)
        r={"kind":"ccob","version":version,"compression_method_code":method,
           "status":"compressed-container",
           "note":"do not guess zlib/zstd from numeric method; use matching clang-offload-bundler"}
        if version==3 and len(header)>=32:
            total,unpacked=struct.unpack_from("<QQ",header,8)
            r["declared_file_size"]=total
            r["declared_uncompressed_bytes"]=unpacked
            r["declared_size_matches"]=total==size
        elif version==2 and len(header)>=24:
            total,unpacked=struct.unpack_from("<II",header,8)
            r["declared_file_size"]=total
            r["declared_uncompressed_bytes"]=unpacked
            r["declared_size_matches"]=total==size
        return r
    if header.startswith(BUNDLE_MAGIC):
        return {"kind":"clang-uncompressed-bundle",
                **parse_uncompressed(header,size)}
    if header.startswith(b"\x7fELF"):
        return {"kind":"direct-elf","status":"recognized-magic",
                "note":"direct ELF must still be checked for AMDGPU machine/target"}
    return {"kind":"unknown","status":"no-supported-container-magic",
            "note":"may be another HIP wrapper, shifted header or unsupported format"}

def bundlers()->list[str]:
    names=("clang-offload-bundler",
           "/opt/rocm/llvm/bin/clang-offload-bundler",
           "/usr/lib/llvm/bin/clang-offload-bundler")
    found=[]
    for name in names:
        p=shutil.which(name) if "/" not in name else name
        if p and Path(p).is_file() and p not in found:found.append(p)
    return found

def tool(argv:list[str])->dict:
    try:
        p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         timeout=120,check=False)
        out=p.stdout.decode(errors="replace")
        err=p.stderr.decode(errors="replace")
        return {"argv":argv,"exit":p.returncode,"stdout":out[:65536],
                "stderr":err[:4096],"stdout_truncated":len(out)>65536}
    except (subprocess.TimeoutExpired,OSError) as e:
        return {"argv":argv,"exit":None,"error":str(e)}

def target_lines(output:str)->list[str]:
    # Target IDs are printed one per line by clang-offload-bundler --list.
    # HIP bundle IDs use `hip-amdgcn...`; the former character class omitted
    # that second hyphen and silently discarded every actual HIP target.
    return [line.strip() for line in output.splitlines()
            if re.match(r"^(?:hip(?:v4)?|host|openmp)-[^\s]+$",line.strip())][:MAX_LIST]

def unique_targets(targets:list[str])->list[str]:
    return list(dict.fromkeys(targets))

def audit(path:Path,tool_path:str|None, output:Path|None)->dict:
    if not path.is_file():raise ValueError("fatbin does not exist")
    size=path.stat().st_size
    if size<=0 or size>MAX_INPUT:raise ValueError("fatbin outside size bounds")
    with path.open("rb") as f:header=f.read(1024*1024)
    result={"schema":1,"mode":"offline-hip-offload-inspect",
            "input":str(path),"size_bytes":size,"sha256":sha256_file(path),
            "first_64_bytes_hex":header[:64].hex(),
            "header":classify(header,size),
            "bundler_candidates":bundlers(),"tool":None,
            "available_targets":[],"target_occurrences":{},"gfx803_candidates":[],
            "unbundled_output":None,
            "incident_executed_kernel":None,
            "source_binary_build_link_proven":False}
    if tool_path:
        if not Path(tool_path).is_file():raise ValueError("bundler executable missing")
        t=tool([tool_path,"--type=o",f"--input={path}","--list"])
        result["tool"]=t
        if t.get("exit")==0:
            target_lines_seen=target_lines(t.get("stdout",""))
            targets=unique_targets(target_lines_seen)
            result["available_targets"]=targets
            result["target_occurrences"]={target:target_lines_seen.count(target) for target in targets}
            result["gfx803_candidates"]=[x for x in targets if x.endswith("--gfx803") or "--gfx803:" in x]
        if output:
            if output.exists():raise ValueError("will not overwrite output code object")
            candidates=result["gfx803_candidates"]
            if t.get("exit")!=0 or len(candidates)!=1:
                raise ValueError("unbundle requires one exact gfx803 advertised target")
            output.parent.mkdir(parents=True,exist_ok=True)
            q=tool([tool_path,"--type=o",f"--input={path}",
                    f"--targets={candidates[0]}",f"--output={output}","--unbundle"])
            result["unbundle_tool"]=q
            if q.get("exit")!=0 or not output.is_file() or output.stat().st_size==0:
                if output.exists():output.unlink()
                raise ValueError("unbundle failed, no GPU code object accepted")
            result["unbundled_output"]={"path":str(output),"sha256":sha256_file(output),
                                          "size_bytes":output.stat().st_size,
                                          "runtime_selected":False}
    elif output:
        raise ValueError("--unbundle-gfx803 requires --bundler")
    return result

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fatbin",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--bundler",type=Path,help="exact installed clang-offload-bundler executable")
    p.add_argument("--unbundle-gfx803",type=Path,
                   help="optional new destination, only if exactly one gfx803 target is listed")
    a=p.parse_args()
    if a.out.exists():p.error("output already exists")
    try:
        result=audit(a.fatbin,str(a.bundler) if a.bundler else None,a.unbundle_gfx803)
    except (OSError,ValueError) as e:p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("wrote",a.out,"format",result["header"]["kind"],
          "gfx803 candidates",len(result["gfx803_candidates"]),"GPU calls 0")
if __name__=="__main__":raise SystemExit(main())
