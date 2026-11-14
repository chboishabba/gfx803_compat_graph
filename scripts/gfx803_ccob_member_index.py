#!/usr/bin/env python3
"""T1.13: header-bound index of concatenated Clang CCOB v2/v3 HIP fatbin members.

CRITICAL: walk each member using its recorded Total File Size, never scan
through compressed payload for the first occurrence of 'CCOB'. Padding can
occur between members. This indexes the container and can extract ONE selected
member to a new file; no HIP, GPU, or kernel execution. Optional per-member
clang-offload-bundler extraction is performed separately.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

MAGIC=b"CCOB"
MAX_INPUT=1024*1024*1024
MAX_MEMBERS=4096
MAX_GAP=4096*4

def sha_bytes(x:bytes)->str:
    return hashlib.sha256(x).hexdigest()

def cco_header(buf:bytes, start:int)->dict|None:
    if start+16>len(buf) or buf[start:start+4]!=MAGIC:return None
    version,method=struct.unpack_from("<HH",buf,start+4)
    if version==3:
        if start+32>len(buf):return None
        length,unpacked=struct.unpack_from("<QQ",buf,start+8)
        header=32
    elif version==2:
        if start+24>len(buf):return None
        length,unpacked=struct.unpack_from("<II",buf,start+8)
        header=24
    else:return None
    if length<header or start+length>len(buf):return None
    if unpacked==0 or unpacked>MAX_INPUT*16:return None
    return {"offset":start,"compressed_member_bytes":length,
            "uncompressed_bytes":unpacked,"version":version,
            "compression_method_code":method,"header_bytes":header}

def index(data:bytes)->dict:
    entries=[]
    pos=0
    first=None
    previous_end=0
    while pos<len(data):
        if len(entries)>=MAX_MEMBERS:raise ValueError("member count exceeds strict bound")
        # Seek only in the small inter-member padding. Do not search compressed
        # member payloads; header's length is authoritative.
        end=min(len(data),pos+MAX_GAP+4)
        found=-1
        hdr=None
        cursor=pos
        while cursor<end:
            at=data.find(MAGIC,cursor,end)
            if at<0:break
            candidate=cco_header(data,at)
            if candidate:
                found=at;hdr=candidate;break
            cursor=at+4
        if found<0:
            tail=data[pos:]
            if tail and any(b!=0 for b in tail):
                raise ValueError("nonzero unindexed trailing data or gap")
            break
        gap=data[pos:found]
        if gap and any(x!=0 for x in gap):
            raise ValueError("nonzero bytes between CCOB members")
        if first is None:first=found
        member=data[found:found+hdr["compressed_member_bytes"]]
        hdr["index"]=len(entries)
        hdr["sha256"]=sha_bytes(member)
        hdr["gap_bytes_before"]=len(gap)
        entries.append(hdr)
        previous_end=found+hdr["compressed_member_bytes"]
        pos=previous_end
    return {"schema":1,"mode":"offline-ccob-members",
            "fatbin_sha256":sha_bytes(data),"fatbin_bytes":len(data),
            "members":entries,"member_count":len(entries),
            "first_offset":first,"trailing_padding_bytes":len(data)-previous_end,
            "extraction_runtime_selected":False,
            "limits":["CCOB membership does not identify incident kernel",
                      "header structural validity is not successful decompression",
                      "members may contain one or multiple target sub-bundles",
                      "no HIP, GPU work or tracing performed"]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fatbin",type=Path,required=True)
    p.add_argument("--container-receipt",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--extract-index",type=int)
    p.add_argument("--extract-out",type=Path)
    args=p.parse_args()
    if args.out.exists():p.error("refuse overwrite")
    if (args.extract_index is None)!=(args.extract_out is None):
        p.error("must specify BOTH --extract-index and --extract-out")
    if args.extract_out and args.extract_out.exists():p.error("refuse overwrite extract")
    if args.fatbin.stat().st_size>MAX_INPUT:p.error("fatbin too large")
    raw=args.fatbin.read_bytes()
    old=json.loads(args.container_receipt.read_text())
    if sha_bytes(raw)!=old.get("sha256"):
        p.error("original fatbin SHA does not match committed receipt")
    try: result=index(raw)
    except ValueError as e:p.error(str(e))
    if args.extract_index is not None:
        n=args.extract_index
        if n<0 or n>=len(result["members"]):p.error("selected member absent")
        e=result["members"][n]
        part=raw[e["offset"]:e["offset"]+e["compressed_member_bytes"]]
        args.extract_out.parent.mkdir(parents=True,exist_ok=True)
        args.extract_out.write_bytes(part)
        result["selected_member"]={"index":n,"path":str(args.extract_out),
                                   "sha256":sha_bytes(part),
                                   "runtime_selected":False}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("indexed",result["member_count"],"CCOB members; GPU calls 0")
if __name__=="__main__":main()
