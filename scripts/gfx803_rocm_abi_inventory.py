#!/usr/bin/env python3
"""Inventory exported ROCm shared-library symbols in an exact Nix closure.

Exported ELF symbols are NOT equivalent to public HIP/ROCm API declarations
and NEVER constitute correctness evidence. Header-only rocPRIM/rocThrust,
HIP compiler ISA and Triton JIT require separate source/testing inventories.
Uses an immutable Nix nm/readelf-compatible executable; no GPU execution.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

STORE=re.compile(r"^/nix/store/[0-9a-z]{32}-[A-Za-z0-9+._?=-]+$")
LIBS={
    "hip-runtime":("libamdhip64",),
    "rocr-hsa-kfd":("libhsa-runtime64",),
    "rocblas-hipblas":("librocblas","libhipblas"),
    "miopen":("libMIOpen",),
    "rocsolver-rocsparse":("librocsolver","librocsparse"),
    "rocfft-rocrand-rocprim":("librocfft","librocrand"),
    "llvm-hip-compiler":("libamd_comgr",),
}
NO_ELF_LIBRARY=("pytorch-opinfo","triton","composed-workloads")
HEADER_ONLY=("rocPRIM","rocThrust","hipCUB")

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def identify_lib(filename):
    # 'libfoo.so', 'libfoo.so.0', but not libfoo-extra.so.
    for group,names in LIBS.items():
        for name in names:
            if filename==name+".so" or filename.startswith(name+".so."):
                return group,name
    return None

def discover(root):
    found={name:{} for group in LIBS.values() for name in group}
    for file in root.rglob("*.so*"):
        identity=identify_lib(file.name)
        if identity is None or not file.is_file():continue
        _,name=identity
        # Versioned SONAME aliases in staged OCI imports may be copied rather
        # than symlinked.  Identical bytes are one ABI candidate; distinct
        # bytes remain deliberately ambiguous.
        binary_digest=sha(file.resolve())
        previous=found[name].get(binary_digest)
        candidate=str(file)
        found[name][binary_digest]=min(previous,candidate) if previous else candidate
    # Do not silently pick among incompatible ABI revisions of a library.
    return {name:sorted(values.values()) for name,values in found.items()}

def executable(path):
    path=path.resolve()
    if not path.is_file() or not os.access(path,os.X_OK) or not str(path).startswith("/nix/store/"):
        raise ValueError("immutable Nix llvm-nm/nm executable required")
    return str(path)

def nm_symbols(nm,path,timeout):
    proc=subprocess.run([nm,"-D","--defined-only","--format=posix",str(path)],
                        capture_output=True,timeout=timeout)
    if proc.returncode:
        raise ValueError("nm failed: "+proc.stderr.decode("utf-8","replace")[-400:])
    names=set()
    for line in proc.stdout.decode("utf-8","replace").splitlines():
        words=line.split()
        if not words:continue
        names.add(words[0])
    return sorted(names)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rocm-root",required=True,type=Path)
    p.add_argument("--nm",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--symbols",action="store_true",
                   help="inspect exports of unique shared-library candidates; CPU-only")
    p.add_argument("--timeout",type=int,default=120)
    a=p.parse_args(argv)
    if a.out.exists():p.error("refuse to overwrite existing ABI evidence")
    if a.timeout<1:p.error("positive timeout required")
    root=a.rocm_root.resolve()
    if not STORE.fullmatch(str(root)) or not root.is_dir():
        p.error("selected ROCm closure must be existing Nix store directory")
    try:nm=executable(a.nm)
    except ValueError as e:p.error(str(e))
    files=discover(root)
    a.out.mkdir(parents=True)
    per_library={}
    for group,names in LIBS.items():
        for name in names:
            candidates=files[name]
            row={"layer":group,"candidate_shared_objects":candidates,
                 "status":("missing" if not candidates else
                           "ambiguous-binary-candidates" if len(candidates)>1 else
                           "shared-object-discovered"),
                 "symbol_count":None}
            if a.symbols and len(candidates)==1:
                path=Path(candidates[0])
                try:
                    symbols=nm_symbols(nm,path,a.timeout)
                    out=a.out/(name+".symbols.json")
                    out.write_text(json.dumps(symbols,indent=2)+"\n")
                    row.update({"status":"ELF-exports-inventoried-not-tested",
                                "binary_sha256":sha(path),
                                "symbol_count":len(symbols),
                                "symbol_file":out.name,
                                "symbol_file_sha256":sha(out)})
                except (ValueError,OSError,subprocess.TimeoutExpired) as e:
                    row.update({"status":"ELF-symbol-inspection-failed",
                                "error":str(e)})
            per_library[name]=row
    report={"schema":1,"rocm_root":str(root),"nm":nm,
            "nm_sha256":sha(Path(nm)),"libraries":per_library,
            "header_only_not_represented_by_ELF":list(HEADER_ONLY),
            "not_qualifiable_by_ELF_exports":list(NO_ELF_LIBRARY),
            "dynamic_symbols_are_not_public_API":True,
            "gpu_executed":False,"all_rocm_apis_qualified":False,
            "release_admitted":False}
    (a.out/"matrix.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"libraries_found":sum(bool(r["candidate_shared_objects"])
                      for r in per_library.values()),
                      "libraries_inventory_symbols":sum(r["symbol_count"] is not None
                      for r in per_library.values()),
                      "gpu_executed":False}))
    return 0

if __name__=="__main__":sys.exit(main())
