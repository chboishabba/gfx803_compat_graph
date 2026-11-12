#!/usr/bin/env python3
"""Aggregate separate original ROCm-layer receipts without inventing API coverage.

Join configured CTest receipts from the source-pinned qualification runner.
The OpInfo baseline is an explicitly marked, committed source-bound summary.
No amount of CTest passes sets GPU or release admission.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

CATALOG=Path(__file__).resolve().parents[1]/"qualification/rocm_layers_v1.json"
STATUSES={"unassayed","interrupted","ctest-pass","ctest-fail","fault","timeout"}

def hashfile(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def aggregate(catalog,inputs):
    layers=catalog["layers"]
    by_id={x["id"]:x for x in layers}
    if len(by_id)!=10 or len(layers)!=10:
        raise ValueError("expected ten distinct source-owned layers")
    baseline=catalog["observed_baseline"]
    summary={}
    for entry in layers:
        name=entry["id"]
        summary[name]={"origin":entry["origin"],"status":"unqualified-in-this-aggregation",
                       "discovered_tests":0,"executed_tests":0,
                       "passed_ctest_reports":0,"failed_or_faulted":0,
                       "unassayed":None,"source_receipt":None}
    summary["pytorch-opinfo"].update({
        "status":"partial-original-OpInfo-hardware-evidence",
        "discovered_tests":sum(baseline[k] for k in
             ("opinfo_pass","opinfo_original_skips","opinfo_fail",
              "opinfo_fault_candidates","opinfo_interruption")),
        "executed_tests":baseline["opinfo_pass"]+baseline["opinfo_original_skips"]+
                         baseline["opinfo_fail"]+baseline["opinfo_fault_candidates"]+
                         baseline["opinfo_interruption"],
        "passed_opinfo":baseline["opinfo_pass"],
        "historical_upstream_skips":baseline["opinfo_original_skips"],
        "fault_candidates":baseline["opinfo_fault_candidates"],
        "failed_or_faulted":baseline["opinfo_fail"]+baseline["opinfo_fault_candidates"],
        "unassayed":0,
        "source_receipt":baseline["opinfo_raw_matrix_sha256"]})
    seen=set()
    profiles=set()
    for name,path in inputs:
        if name not in by_id or name=="pytorch-opinfo":
            raise ValueError("unknown or duplicate-existing OpInfo suite: "+name)
        if name in seen:
            raise ValueError("duplicate test layer: "+name)
        seen.add(name)
        raw=path.read_bytes()
        data=json.loads(raw)
        if data.get("schema")!=1 or data.get("layer")!=name:
            raise ValueError("wrong source-layer receipt: "+name)
        cases=data.get("cases")
        ids=data.get("all_discovered_tests")
        if not isinstance(cases,dict) or not isinstance(ids,list) or not ids:
            raise ValueError("missing installed CTest inventory")
        if set(ids)!=set(cases) or len(ids)!=len(set(ids)):
            raise ValueError("original test inventory/case mismatch")
        if any(not isinstance(v,dict) or v.get("status") not in STATUSES
               for v in cases.values()):
            raise ValueError("invalid original case status")
        if data.get("release_admitted") is not False or data.get("gpu_validated") is not False:
            raise ValueError("unexpected promotion in original source receipt")
        root=data.get("rocm_root")
        if not isinstance(root,str) or not root.startswith("/nix/store/"):
            raise ValueError("missing selected immutable runtime root")
        profiles.add(root)
        counts=Counter(v["status"] for v in cases.values())
        complete=len(ids)-counts["unassayed"]-counts["interrupted"]
        summary[name].update({
            "status":"installed-CTest-receipt-partial" if complete<len(ids)
                     else "installed-CTest-results-not-API-coverage",
            "discovered_tests":len(ids),"executed_tests":complete,
            "passed_ctest_reports":counts["ctest-pass"],
            "failed_or_faulted":counts["ctest-fail"]+counts["fault"]+counts["timeout"],
            "unassayed":counts["unassayed"],
            "interrupted":counts["interrupted"],
            "source_receipt":hashlib.sha256(raw).hexdigest(),
            "rocm_root":root,
            "runtime_coherence_verified":data.get("runtime_coherence_verified") is True,
            "source_sha":data.get("source_sha")})
    return {"schema":1,"layers":summary,
            "ctest_receipts_count":len(inputs),
            "different_rocm_roots":len(profiles)>1,
            "runtime_roots":sorted(profiles),
            "all_rocm_apis_qualified":False,"gpu_validated":False,
            "release_admitted":False,
            "qualification_rule":"test inventory and CTest outcomes never imply universal ROCm API, device or runtime coherence"}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--receipt",action="append",default=[],
                   help="layer-id=/exact/path/to/original/matrix.json")
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args(argv)
    if a.out.exists():p.error("refuse overwriting aggregate report")
    try:
        pairs=[]
        for arg in a.receipt:
            if "=" not in arg:raise ValueError("receipt must be layer-id=path")
            name,path=arg.split("=",1)
            if not name or not path:raise ValueError("empty layer/path")
            pairs.append((name,Path(path)))
        report=aggregate(json.loads(CATALOG.read_text()),pairs)
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as ex:p.error(str(ex))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"ctest_receipts":report["ctest_receipts_count"],
                      "layers":len(report["layers"]),
                      "release_admitted":False}))
if __name__=="__main__":main()
