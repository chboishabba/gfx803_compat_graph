#!/usr/bin/env python3
"""Explicit direct hipSPARSE handle smoke, no sparse kernel launch.
Requires exact absolute library path; loader dependencies remain observable.
GPU initialization is possible: execute only on idle healthy host.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path

def maps():
    return sorted({s.split(maxsplit=5)[-1] for s in Path("/proc/self/maps").read_text().splitlines()
                   if any(k in s for k in ("libhipsparse","librocsparse","libamdhip64","libhsa-runtime"))})

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--library",type=Path,required=True)
    p.add_argument("--execute",action="store_true")
    a=p.parse_args()
    if not a.library.is_absolute() or not a.library.is_file():
        p.error("exact absolute existing hipSPARSE library required")
    lib=a.library.resolve()
    with lib.open("rb") as f:
        sha=hashlib.file_digest(f,"sha256").hexdigest()
    result=dict(library=str(lib),sha256=sha,mode="identity-only",maps_before=maps())
    if a.execute:
        result["mode"]="direct-handle"
        try:
            api=C.CDLL(str(lib))
            create=api.hipsparseCreate
            create.argtypes=[C.POINTER(C.c_void_p)]
            create.restype=C.c_int
            destroy=api.hipsparseDestroy
            destroy.argtypes=[C.c_void_p]
            destroy.restype=C.c_int
            h=C.c_void_p()
            rc=create(C.byref(h))
            result.update(create_status=rc,handle_nonnull=bool(h))
            if rc==0 and h:
                result["destroy_status"]=destroy(h)
            result["status"]="pass" if rc==0 and h and result.get("destroy_status")==0 else "fail"
        except (OSError,AttributeError) as e:
            result.update(status="loader-or-symbol-failure",error=str(e))
        result["maps_after"]=maps()
    print(json.dumps(result,indent=2))
    return 0 if result.get("status","pass")=="pass" else 1
if __name__=="__main__":
    raise SystemExit(main())
