#!/usr/bin/env python3
"""Normalize upstream test receipts by immutable device/profile identity.

Does not run tests or admit any release. No missing operator is counted as passed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

VALID={"pass","fail","fault","timeout","unsupported","unassayed"}
FIELDS=("architecture","board","kernel","driver","rocm_store","torch_wheel_sha256","source_revision")

def validate_profile(profile):
    if not isinstance(profile,dict) or any(
        not isinstance(profile.get(k),str) or not profile[k].strip() for k in FIELDS
    ):
        raise ValueError("complete original hardware/software profile required")
    digest=profile["torch_wheel_sha256"]
    if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("invalid PyTorch wheel SHA-256")
    return {key:profile[key] for key in FIELDS}

def normalize(name,receipt,digest):
    if not isinstance(receipt,dict) or not isinstance(receipt.get("cases"),dict) or not receipt["cases"]:
        raise ValueError("receipt missing selected cases")
    result=[]
    for case,row in sorted(receipt["cases"].items()):
        if not isinstance(row,dict) or row.get("status") not in VALID:
            raise ValueError("invalid case status")
        result.append({"suite":name,"case":case,"status":row["status"],
                       "original_receipt_sha256":digest})
    return result

def aggregate(profile,receipts):
    pinned=validate_profile(profile)
    cases=[]
    for suite,path in receipts:
        original=path.read_bytes()
        cases+=normalize(suite,json.loads(original),hashlib.sha256(original).hexdigest())
    identities=[(c["suite"],c["case"]) for c in cases]
    if len(identities)!=len(set(identities)):
        raise ValueError("duplicate suite/case identities")
    return {"schema":1,"profile":pinned,"cases":cases,
            "counts":{status:sum(c["status"]==status for c in cases) for status in sorted(VALID)},
            "general_gpu_compatibility":False,"release_admitted":False,
            "scope":"only these original receipts on the specified board/runtime"}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile",required=True,type=Path)
    p.add_argument("--receipt",required=True,action="append",
                   help="suite=/path/to/upstream-or-local-matrix.json")
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args(argv)
    if a.out.exists():p.error("fresh output required")
    try:
        sources=[]
        for arg in a.receipt:
            if "=" not in arg:raise ValueError("receipt needs suite=path")
            suite,path=arg.split("=",1)
            if not suite or "/" in suite or not path:raise ValueError("invalid suite name/path")
            sources.append((suite,Path(path)))
        result=aggregate(json.loads(a.profile.read_text()),sources)
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as e:p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result["counts"],sort_keys=True))
    return 0
if __name__=="__main__":sys.exit(main())
