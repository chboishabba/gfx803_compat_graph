#!/usr/bin/env python3
"""Offline AMDGPU HSACO ELF64 PT_NOTE / MessagePack metadata decoder.

Implements a small bounded MessagePack subset sufficient for common AMDGPU
code-object v3-v5 .note AMDGPU metadata. Unsupported formats remain unknown;
never invent kernel fields. Verifies supplied exact HSACO SHA/size from the
committed offload-container receipt. No ROCm runtime, HIP or GPU access.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

MAX_FILE=128*1024*1024
MAX_NODES=100000
MAX_DEPTH=32
MAX_BLOB=8*1024*1024
# Keep this deliberately narrower than generic selection/indexing kernels.
# ``gather`` is used across unrelated ATen operations and is not evidence of
# a TopK implementation.  The accepted spellings mirror the host-side TopK
# attribution audit.
TOPK_KERNEL_NAME=re.compile(
    r"mbtopk|sbtopk|warptopk|gatherTopK|TensorTopK|(?:^|[_:])topk(?:[_:<>]|$)",
    re.I,
)

class DecodeError(ValueError):pass

class MsgPack:
    def __init__(self,data:bytes):
        self.data=data
        self.pos=0
        self.nodes=0
    def take(self,n:int)->bytes:
        if n<0 or self.pos+n>len(self.data):raise DecodeError("truncated msgpack")
        raw=self.data[self.pos:self.pos+n]
        self.pos+=n
        return raw
    def number(self,n:int,signed=False)->int:
        return int.from_bytes(self.take(n),"big",signed=signed)
    def decode(self,depth:int=0):
        self.nodes+=1
        if depth>MAX_DEPTH or self.nodes>MAX_NODES:raise DecodeError("metadata recursion/node limit")
        x=self.number(1)
        if x<0x80:return x
        if x>=0xe0:return x-256
        if 0xa0<=x<=0xbf:return self.take(x&0x1f).decode("utf8","replace")
        if 0x90<=x<=0x9f:return [self.decode(depth+1) for _ in range(x&0x0f)]
        if 0x80<=x<=0x8f:return self._map(x&0x0f,depth)
        if x==0xc0:return None
        if x==0xc2:return False
        if x==0xc3:return True
        if x in (0xca,0xcb):return struct.unpack(">f" if x==0xca else ">d",self.take(4 if x==0xca else 8))[0]
        if x in (0xcc,0xcd,0xce,0xcf):return self.number({0xcc:1,0xcd:2,0xce:4,0xcf:8}[x])
        if x in (0xd0,0xd1,0xd2,0xd3):return self.number({0xd0:1,0xd1:2,0xd2:4,0xd3:8}[x],True)
        if x in (0xd9,0xda,0xdb):
            n=self.number({0xd9:1,0xda:2,0xdb:4}[x])
            if n>MAX_BLOB:raise DecodeError("string too big")
            return self.take(n).decode("utf8","replace")
        if x in (0xc4,0xc5,0xc6):
            n=self.number({0xc4:1,0xc5:2,0xc6:4}[x])
            if n>MAX_BLOB:raise DecodeError("binary too big")
            return {"_bytes_hex_prefix":self.take(n)[:32].hex(),"_bytes_length":n}
        if x in (0xdc,0xdd):
            count=self.number(2 if x==0xdc else 4)
            if count>MAX_NODES:raise DecodeError("array too large")
            return [self.decode(depth+1) for _ in range(count)]
        if x in (0xde,0xdf):
            count=self.number(2 if x==0xde else 4)
            return self._map(count,depth)
        raise DecodeError("unsupported msgpack marker 0x%02x"%x)
    def _map(self,count:int,depth:int)->dict:
        if count>MAX_NODES:raise DecodeError("map too large")
        result={}
        for _ in range(count):
            key=self.decode(depth+1)
            val=self.decode(depth+1)
            if not isinstance(key,(int,str,bool)):key=repr(key)[:100]
            result[str(key)]=val
        return result

def notes(data:bytes)->list[dict]:
    if len(data)<64 or data[:4]!=b"\x7fELF" or data[4]!=2 or data[5]!=1:
        raise ValueError("requires little-endian ELF64")
    if struct.unpack_from("<H",data,18)[0]!=224:
        raise ValueError("requires AMDGPU e_machine=224")
    phoff=struct.unpack_from("<Q",data,32)[0]
    entsize=struct.unpack_from("<H",data,54)[0]
    count=struct.unpack_from("<H",data,56)[0]
    if count>2048 or (count and (entsize!=56 or phoff+count*56>len(data))):
        raise ValueError("invalid ELF program header table")
    result=[]
    for i in range(count):
        off=phoff+i*entsize
        ptype=struct.unpack_from("<I",data,off)[0]
        if ptype!=4:continue
        offset=struct.unpack_from("<Q",data,off+8)[0]
        length=struct.unpack_from("<Q",data,off+32)[0]
        if offset+length>len(data) or length>MAX_BLOB:continue
        cursor=offset
        end=offset+length
        while cursor+12<=end:
            namesz,descsz,kind=struct.unpack_from("<III",data,cursor)
            cursor+=12
            name_start=cursor
            name_end=name_start+namesz
            desc_start=name_start+((namesz+3)//4)*4
            desc_end=desc_start+descsz
            next_note=desc_start+((descsz+3)//4)*4
            if next_note>end or name_end>end or desc_end>end:break
            name=data[name_start:name_end].rstrip(b"\0").decode("utf8","replace")
            desc=data[desc_start:desc_end]
            cursor=next_note
            candidate={"name":name,"type":kind,"descriptor_bytes":len(desc),
                       "descriptor_sha256":hashlib.sha256(desc).hexdigest(),
                       "msgpack_decoded":False}
            if name.upper().startswith("AMDGPU") and kind in (32,):
                try:
                    unpacker=MsgPack(desc)
                    value=unpacker.decode()
                    if unpacker.pos!=len(desc):
                        raise DecodeError("trailing metadata bytes")
                    candidate["msgpack_decoded"]=True
                    candidate["metadata"]=value
                except DecodeError as e:
                    candidate["decode_error"]=str(e)
            result.append(candidate)
            if len(result)>5000:raise ValueError("too many ELF note entries")
    return result

def kernels_from_notes(entries:list[dict])->list[dict]:
    out=[]
    for entry in entries:
        meta=entry.get("metadata")
        if not isinstance(meta,dict):continue
        kernels=meta.get("amdhsa.kernels") or meta.get(".amdhsa.kernels")
        # Modern metadata often includes '.name' and '.symbol' in dicts.
        if not isinstance(kernels,list):continue
        for k in kernels:
            if not isinstance(k,dict):continue
            name=k.get(".name",k.get("name"))
            if not isinstance(name,str):continue
            props={}
            for key in (".symbol",".sgpr_count",".vgpr_count",
                        ".group_segment_fixed_size",".private_segment_fixed_size",
                        ".kernarg_segment_size",".wavefront_size",
                        ".max_flat_workgroup_size"):
                if key in k:props[key]=k[key]
            out.append({"name":name,"properties":props,
                        "topk_name_match":bool(TOPK_KERNEL_NAME.search(name))})
            if len(out)>10000:raise ValueError("too many metadata kernels")
    return out

def analyze(path:Path,receipt:dict)->dict:
    obj=receipt.get("unbundled_output",{})
    if not path.is_file() or path.stat().st_size>MAX_FILE:
        raise ValueError("missing/oversized HSACO")
    data=path.read_bytes()
    sha=hashlib.sha256(data).hexdigest()
    if sha!=obj.get("sha256") or len(data)!=obj.get("size_bytes"):
        raise ValueError("HSACO SHA/size mismatch against original receipt")
    entries=notes(data)
    kernels=kernels_from_notes(entries)
    return {"schema":1,"mode":"offline-amdgpu-msgpack-note",
            "hsaco_sha256":sha,"hsaco_size_bytes":len(data),
            "notes":entries,"kernels":kernels,
            "metadata_kernel_count":len(kernels),
            "topk_named_kernel_count":sum(x["topk_name_match"] for x in kernels),
            "incident_runtime_selected":False,"actual_incident_kernel":None,
            "limits":["metadata inclusion does not prove runtime dispatch",
                      "ELF might be a linked aggregate of multiple code objects",
                      "only PT_NOTE AMDGPU type 32 MessagePack subset parsed",
                      "unsupported/corrupt notes remain unknown",
                      "no HIP/GPU work"]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hsaco",type=Path,required=True)
    p.add_argument("--container-receipt",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():p.error("no overwrite")
    try:r=analyze(a.hsaco,json.loads(a.container_receipt.read_text()))
    except (ValueError,OSError,json.JSONDecodeError) as e:p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
    print("AMDGPU notes decoded:",len(r["notes"]),"kernels:",len(r["kernels"]),"GPU work 0")
if __name__=="__main__":main()
