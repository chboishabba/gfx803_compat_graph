#!/usr/bin/env python3
"""Offline join of original OpInfo skip audit and replay matrices; no GPU."""
import argparse
from collections import Counter
import json
from pathlib import Path
from gfx803_opinfo_skip_reason_probe import read_audit, MATRIX_SHA, SOURCE_PIN

RESOLVED={"upstream-skipped","upstream-xfailed","executed-passed"}
OBSERVED=RESOLVED|{"unexpected-xpass","unexpected-call-failure","setup-failed","teardown-failed"}

def join(ids,audit_sha,inputs):
    universe=set(ids)
    rows={n:[] for n in ids}
    for path,doc in inputs:
        if (doc.get("schema")!=1 or doc.get("mode")!="replay" or
            doc.get("original_matrix_sha256")!=MATRIX_SHA or
            doc.get("audit_sha256")!=audit_sha or doc.get("pytorch_source")!=SOURCE_PIN):
            raise ValueError("replay identity mismatch: "+path)
        selected=doc["selected_nodes"]
        if len(set(selected))!=len(selected) or set(selected)!=set(doc["cases"]) or not set(selected)<=universe:
            raise ValueError("invalid replay node universe: "+path)
        for n,row in doc["cases"].items():
            if row.get("status")=="unassayed":
                continue
            outcome=row.get("runtime_outcome")
            if row.get("status")!="replayed" or outcome not in OBSERVED:
                outcome="unresolved-attempt"
            elif outcome in ("upstream-skipped","upstream-xfailed") and not row.get("skip_reason"):
                outcome="unresolved-attempt"
            rows[n].append(dict(receipt=path,outcome=outcome,details=row))
    result={}
    for n,attempts in rows.items():
        outcomes={a["outcome"] for a in attempts}
        status=next(iter(outcomes)) if len(outcomes)==1 else "conflicting-attempts" if outcomes else "unassayed"
        result[n]=dict(status=status,attempts=attempts)
    counts=Counter(row["status"] for row in result.values())
    unresolved=[n for n in ids if result[n]["status"] not in RESOLVED]
    return dict(schema=1,original_matrix_sha256=MATRIX_SHA,audit_sha256=audit_sha,
                counts=dict(counts),resolved_count=len(ids)-len(unresolved),
                unresolved_count=len(unresolved),unresolved_nodes=unresolved,
                rows=result,release_admitted=False)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit",type=Path,required=True)
    p.add_argument("--replay",type=Path,nargs="+",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    ids,sha=read_audit(a.audit)
    result=join(ids,sha,[(str(x),json.loads(x.read_text())) for x in a.replay])
    with a.out.open("x") as f:
        json.dump(result,f,indent=2)
        f.write("\n")
    print(json.dumps({k:result[k] for k in ("counts","resolved_count","unresolved_count")}))

if __name__=="__main__":
    main()
