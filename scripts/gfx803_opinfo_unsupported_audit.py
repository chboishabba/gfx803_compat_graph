#!/usr/bin/env python3
"""Audit original 1774-case OpInfo discovery skips; never equate skip to missing GPU support."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

EXPECTED="47c7ed58d7b549abfc038b534faaaa9ecaf6ee2fc18b3ba55addebeed02b7e36"
FAMILIES=("test_variant_consistency_eager_","test_compare_cpu_")
DTYPES=("complex128","complex64","bfloat16","float64","float32","float16","int64","int32","int16","int8","uint8","bool")

def parse_name(name):
    stem=name.split("::")[-1]
    family=next((s[:-1] for s in FAMILIES if stem.startswith(s)),"other")
    suffix=stem[len(family)+1:] if family!="other" else stem
    dtype=next((d for d in DTYPES if suffix.endswith("_cuda_"+d)),"other")
    op=suffix[:-len("_cuda_"+dtype)] if dtype!="other" else suffix
    return family,dtype,op

def audit(raw,expected_hash=EXPECTED):
    digest=hashlib.sha256(raw).hexdigest()
    if expected_hash and digest!=expected_hash:
        raise ValueError("original discovery matrix SHA-256 mismatch")
    cases=json.loads(raw).get("cases")
    if not isinstance(cases,dict):raise ValueError("missing original case records")
    counts=Counter(x["status"] for x in cases.values())
    if len(cases)!=1774 or counts.get("unsupported")!=183:
        raise ValueError("unexpected case universe / unsupported count")
    rows=[]
    for name,rec in sorted(cases.items()):
        if rec["status"]!="unsupported":continue
        family,dtype,op=parse_name(name)
        reason=rec.get("skip_reason") or rec.get("reason")
        rows.append({"nodeid":name,"family":family,"dtype":dtype,"operator":op,
                     "original_status":"unsupported",
                     "pytest_outcome":"skipped (mapped by discovery worker)",
                     "reason":reason,
                     "classification":"skip-reason-recorded" if reason else "skip-reason-not-recorded",
                     "evidence_lane":rec.get("evidence_lane")})
    return {"schema":1,"source_matrix_sha256":digest,"total_nodes":len(cases),
            "unsupported_count":len(rows),"counts":dict(sorted(counts.items())),
            "families":dict(sorted(Counter(x["family"] for x in rows).items())),
            "dtypes":dict(sorted(Counter(x["dtype"] for x in rows).items())),
            "reason_classes":dict(sorted(Counter(x["classification"] for x in rows).items())),
            "hardware_unsupported_proven":0,
            "interpretation":"pytest skip is not proof of missing HIP kernels or missing device support",
            "release_admitted":False,"rows":rows}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    if a.out.exists():p.error("refuse overwriting original classification receipt")
    try:result=audit(a.matrix.read_bytes())
    except (ValueError,OSError,KeyError,TypeError) as ex:p.error(str(ex))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({x:result[x] for x in ("unsupported_count","families","dtypes","reason_classes")},indent=2))
if __name__=="__main__":main()
