#!/usr/bin/env python3
"""Offline PyTorch TopK source / wheel / GPU-object provenance assay.

Never imports torch, initializes HIP, executes kernels or resets a GPU.
String/code-object inventory is not proof that a kernel ran in a crash.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

SHAPES=((1,151936,50,4),(32,151936,50,4))
MAX_SCAN=400000000  # refuse reading giant ELF blobs into memory

# TensorTopK HIP kernels are linked into libtorch_hip.so.  Hashing every
# unrelated host-side library makes a TopK-only audit needlessly read hundreds
# of MiB across network storage while adding no dispatch provenance.
TOPK_HIP_LIBRARY = "libtorch_hip.so"

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def zip_member_hash(z: zipfile.ZipFile, member: str) -> str:
    h=hashlib.sha256()
    with z.open(member) as stream:
        for block in iter(lambda: stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def manifest(path:Path)->dict:
    if not path.exists():raise FileNotFoundError(path)
    if path.is_file():
        if not zipfile.is_zipfile(path):raise ValueError("expected a Python wheel ZIP")
        with zipfile.ZipFile(path) as z:
            names=z.namelist()
            libs=[x for x in names if x.startswith("torch/lib/") and x.endswith(".so")]
            entries=[]
            for x in libs:
                info=z.getinfo(x)
                relevant=Path(x).name == TOPK_HIP_LIBRARY
                entries.append({"name":x,"bytes":info.file_size,
                                "topk_hip_library":relevant,
                                "sha256":zip_member_hash(z,x) if relevant and info.file_size<=MAX_SCAN else None})
            if not any(x["topk_hip_library"] for x in entries):
                raise ValueError("wheel has no torch/lib/libtorch_hip.so")
            return {"kind":"wheel","sha256":sha(path),"libs":entries,
                    "hash_scope":"wheel archive plus libtorch_hip.so; unrelated shared objects are listed but not read",
                    "topk_file_in_wheel":any(x.endswith("TensorTopK.cpp") for x in names),
                    "torch_version_files":[x for x in names if x.endswith("torch/version.py")]}
    entries=[]
    for p in sorted(path.glob("torch/lib/*.so")):
        relevant=p.name == TOPK_HIP_LIBRARY
        entries.append({"name":str(p.relative_to(path)),"bytes":p.stat().st_size,
                        "topk_hip_library":relevant,
                        "sha256":sha(p) if relevant else None})
    if not any(x["topk_hip_library"] for x in entries):
        raise ValueError("no torch/lib/libtorch_hip.so found in overlay")
    return {"kind":"overlay","libs":entries,
            "hash_scope":"libtorch_hip.so only; unrelated shared objects are listed but not read"}

def source_audit(path:Path)->dict:
    text=path.read_text()
    return {"path":str(path),"sha256":sha(path),
            "arch_helper":'isGPUArch({"gfx803"})' in text,
            "marker":"GFX803_TOPK_SORT_FALLBACK_PATCH" in text,
            "manual_gcn_arch":bool(re.search(r"gcnArchName|strncmp",text)),
            "should_use_sort":bool(re.search(r"\bshould_use_sort\s*\(",text)),
            "warp_merge": "WarpMergeSortTopK" in text or "warpMergeSortTopK" in text,
            "gather": "gatherTopK" in text,
            "notes":"source feature inventory, not a proof of compiled branch/selected HSACO"}

def case_resource(rows:int,vocab:int,k:int,itembytes:int)->dict:
    # Lower bound only. Real ATen sort can need additional indices,
    # workspace, temporary buffers and per-kernel register/LDS usage.
    elems=rows*vocab
    return {"rows":rows,"cols":vocab,"k":k,"dtype_bytes":itembytes,
            "input_bytes_min":elems*itembytes,
            "values_output_bytes_min":rows*k*itembytes,
            "indices_output_bytes_min":rows*k*8,
            "full_sort_values_lower_bound_bytes":elems*itembytes,
            "full_sort_indices_lower_bound_bytes":elems*8,
            "limitation":"not measured allocations, wavefront geometry or scheduler occupancy"}

def strings_inventory(binary:Path)->dict:
    if binary.stat().st_size>MAX_SCAN:
        return {"path":str(binary),"status":"too-large; no scan"}
    data=binary.read_bytes()
    matches={}
    for needle in (b"gfx803",b"amdgcn",b"topk",b"TopK",b"sort",b"hsaco",b"warpMergeSortTopK",b"gatherTopK"):
        matches[needle.decode()]=data.count(needle)
    return {"path":str(binary),"sha256":hashlib.sha256(data).hexdigest(),
            "bytes":len(data),"string_counts":matches,
            "limitation":"unstructured strings; cannot identify selected GPU kernel"}

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--torch",type=Path,required=True,help="cached pre-review wheel .whl OR offline overlay root")
    p.add_argument("--source",type=Path,help="matching TensorTopK.cpp; optional")
    p.add_argument("--code-object",type=Path,action="append",default=[],
                   help="existing offline HSACO/ELF/torch shared object to inventory (may repeat)")
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():p.error("refuse overwriting a previous receipt")
    receipt={"schema":1,"mode":"static-only","torch":manifest(a.torch),
             "topk_source":source_audit(a.source) if a.source else {"status":"missing"},
             "cases":[case_resource(*x) for x in SHAPES],
             "code_objects":[strings_inventory(x) for x in a.code_object],
             "incident":{"passed":"float32 [1,151936] k=50",
                         "gpu_hung":"float32 [32,151936] k=50",
                         "first_dispatched_kernel":None,
                         "first_gpu_failing_instruction":None},
             "notes":["No HIP execution, no runtime kernel selection claim",
                      "Further: extract HSACO from exact binary and resolve dispatch",
                      "Compare installed dynamic-library mappings recorded by earlier runtime receipts",
                      "Full sort lower bounds omit implementation workspace and allocator overhead"]}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    print("wrote",a.out,"(static only; no GPU workload)")
    return 0
if __name__=="__main__":raise SystemExit(main())
