#!/usr/bin/env python3
"""Inspect dumped HIP fatbin for structurally valid embedded AMDGPU ELF candidates.

Conservative ELF64 little-endian parser: requires whole section-header table,
bounded section extents, AMDGPU e_machine=224. No GPU runtime / network use.
A discovered ELF is an *included candidate*, not the dispatched kernel.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

ELF_MAGIC=b"\x7fELF"
AMDGPU_MACHINE=224
MAX_INPUT=1024*1024*1024
MAX_CANDIDATES=2048

def parse_candidate(blob:memoryview, offset:int)->dict|None:
    remaining=len(blob)-offset
    if remaining <64 or bytes(blob[offset:offset+4])!=ELF_MAGIC:return None
    if blob[offset+4]!=2 or blob[offset+5]!=1:return None
    if struct.unpack_from("<H",blob,offset+18)[0]!=AMDGPU_MACHINE:return None
    e_ehsize=struct.unpack_from("<H",blob,offset+52)[0]
    shoff=struct.unpack_from("<Q",blob,offset+40)[0]
    shentsize=struct.unpack_from("<H",blob,offset+58)[0]
    shnum=struct.unpack_from("<H",blob,offset+60)[0]
    phoff=struct.unpack_from("<Q",blob,offset+32)[0]
    phentsize=struct.unpack_from("<H",blob,offset+54)[0]
    phnum=struct.unpack_from("<H",blob,offset+56)[0]
    if e_ehsize!=64 or shnum==0 or shentsize!=64 or shnum>8192:return None
    if shoff<64 or shoff+shnum*64>remaining:return None
    if phnum and (phentsize!=56 or phoff+phnum*56>remaining):return None
    extent=max(64,shoff+shnum*64,phoff+phnum*phentsize)
    # Section records are relative to the embedded ELF, not the fatbin.
    for n in range(shnum):
        base=offset+shoff+n*64
        shtype=struct.unpack_from("<I",blob,base+4)[0]
        shoffset=struct.unpack_from("<Q",blob,base+24)[0]
        shsize=struct.unpack_from("<Q",blob,base+32)[0]
        if shtype!=8 and shsize:
            if shoffset+shsize>remaining:return None
            extent=max(extent,shoffset+shsize)
    for n in range(phnum):
        base=offset+phoff+n*56
        fileoff=struct.unpack_from("<Q",blob,base+8)[0]
        filesz=struct.unpack_from("<Q",blob,base+32)[0]
        if filesz:
            if fileoff+filesz>remaining:return None
            extent=max(extent,fileoff+filesz)
    if extent<64 or extent>remaining:return None
    return {"offset":offset,"size_bytes_min":extent,
            "e_type":struct.unpack_from("<H",blob,offset+16)[0],
            "machine":AMDGPU_MACHINE,"sections":shnum,"program_headers":phnum,
            "warning":"ELF extent is a structural minimum; bundled metadata may follow ELF"}

def inspect(content:bytes)->dict:
    mv=memoryview(content)
    candidates=[]
    cursor=0
    while len(candidates)<MAX_CANDIDATES:
        found=content.find(ELF_MAGIC,cursor)
        if found<0:break
        candidate=parse_candidate(mv,found)
        if candidate:candidates.append(candidate)
        cursor=found+4
    return {"schema":1,"mode":"offline-fatbin-scan",
            "fatbin_size_bytes":len(content),
            "fatbin_sha256":hashlib.sha256(content).hexdigest(),
            "embedded_amdgpu_elf_candidates":candidates,
            "scan_cap_reached":len(candidates)>=MAX_CANDIDATES,
            "actual_dispatched_hsaco":None,
            "limitations":[
                "embedded ELF inclusion is not incident execution evidence",
                "candidate extent may omit trailing bundle wrapper metadata",
                "compressed or non-ELF code objects are not found",
                "ELF metadata is not a reliable kernel grid/occupancy record",
                "no HIP initialization or GPU workload"]}
def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fatbin",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--extract-dir",type=Path,help="optional: extract bounded AMDGPU ELF candidates into new directory")
    a=p.parse_args()
    if a.out.exists():p.error("refuse overwriting prior evidence")
    if a.fatbin.stat().st_size>MAX_INPUT:p.error("fatbin too large for bounded offline scan")
    payload=a.fatbin.read_bytes()
    data=inspect(payload)
    if a.extract_dir:
        if a.extract_dir.exists():p.error("refuse overwriting existing extraction directory")
        if data["scan_cap_reached"]:p.error("candidate cap reached; extraction refused")
        a.extract_dir.mkdir(parents=True)
        for i,candidate in enumerate(data["embedded_amdgpu_elf_candidates"]):
            start=candidate["offset"]
            end=start+candidate["size_bytes_min"]
            name=a.extract_dir/("amdgpu_candidate_%04d.elf"%i)
            part=payload[start:end]
            name.write_bytes(part)
            candidate["extracted_elf"]=str(name)
            candidate["extracted_sha256"]=hashlib.sha256(part).hexdigest()
            candidate["identification"]="included ELF candidate; execution and gfx803 target not established"
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    print("fatbin structural scan done; candidates:",len(data["embedded_amdgpu_elf_candidates"]))
if __name__=="__main__":raise SystemExit(main())
