#!/usr/bin/env python3
"""Join independent original MIOpen, 42-isolated, shared-prefix and runtime controls.

This is a strict provenance/observation reducer; no result promotion and
no causal attribution to an unobserved kernel, queue or doorbell callback.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

PIN="8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78"
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    obj=json.loads(path.read_text())
    if obj.get("source_sha")!=PIN or obj.get("release_admitted") is not False:
        raise ValueError("unsupported original source or untrusted release flag: "+str(path))
    return obj

def join(single,prefix,controls=None,original=None,kfd=None):
    single_doc=read(single)
    ids=[str(i) for i in range(42)]
    c=single_doc.get("cases",{})
    if set(c)!=set(ids) or not all(v.get("status")=="pass" and v.get("tested")==1
                                    and v.get("wrong")==0 for v in c.values()):
        raise ValueError("isolated 42-case evidence incomplete or nonpassing")
    pref=read(prefix)
    p=pref.get("cases",{})
    expected=("1","2","4","8","14","16","21","28","35","42")
    if not all(k in p and p[k].get("status")=="passed" for k in expected):
        raise ValueError("shared-process prefix ladder incomplete or nonpassing")
    if pref.get("original_pool_sha256")!=single_doc.get("original_sha256"):
        raise ValueError("isolated and prefix original source content differs")
    if pref.get("rocm_prefix")!=single_doc.get("rocm_prefix"):
        raise ValueError("original test runtime selection differs")
    report={"schema":1,"original_schaka_source_sha":PIN,
            "source_pool_sha256":single_doc["original_sha256"],
            "selected_runtime_prefix":single_doc["rocm_prefix"],
            "isolated_count":42,"isolated_pass":42,
            "shared_process_prefix_lengths":list(map(int,expected)),
            "shared_process_pass":len(expected),
            "isolated_receipt_sha256":digest(single),
            "prefix_receipt_sha256":digest(prefix),
            "original_binary_reproduced_fault":None,
            "doorbell_callback_in_running_kernel":"unverified",
            "historical_fault":"observed in earlier original whole MIOpen sweep; not reproduced by isolated/prefix experiments",
            "release_admitted":False,"all_miopen_functions_qualified":False,
            "cumulative_state_causality_established":False}
    if original is not None:
        d=read(original)
        if d.get("source_sha")!=PIN:
            raise ValueError("original MIOpen source mismatch")
        cases=d.get("cases",{})
        if "pool_sweep" not in cases:raise ValueError("original pool entry absent")
        report["historical_original_pool_status"]=cases["pool_sweep"].get("status")
        report["historical_original_receipt_sha256"]=digest(original)
    if controls is not None:
        d=read(controls)
        if d.get("original_source_sha256")!=single_doc["original_sha256"]:
            raise ValueError("original-binary controls source not identical")
        if d.get("rocm_prefix")!=single_doc["rocm_prefix"]:
            raise ValueError("original-binary controls ROCm prefix differs")
        r=d.get("results",{})
        if set(r)!=set(d.get("controls",{})):
            raise ValueError("runtime control result universe incomplete")
        report["original_binary_controls"]={name:item.get("status") for name,item in r.items()}
        report["original_binary_controls_receipt_sha256"]=digest(controls)
        # A controls fault is a newly reproduced original binary fault, not
        # necessarily kernel fault attribution.
        report["original_binary_reproduced_fault"]=any(
            item.get("status") in ("fault","kernel-fault-observed")
            for item in r.values())
    if kfd is not None:
        record=json.loads(kfd.read_text())
        if record.get("schema")!=1 or record.get("gpu_executed") is not False:
            raise ValueError("invalid read-only KFD audit")
        report["kfd_journal_available"]=record.get("journal_available")
        report["kfd_matched_event_counts"]={
            k:len(v) for k,v in record.get("matched_kernel_lines",{}).items()}
        report["kfd_receipt_sha256"]=digest(kfd)
        report["doorbell_callback_in_running_kernel"]="unverified"
    return report

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--isolated",type=Path,required=True)
    p.add_argument("--prefix",type=Path,required=True)
    p.add_argument("--original",type=Path)
    p.add_argument("--controls",type=Path)
    p.add_argument("--kfd",type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args(argv)
    if a.out.exists():p.error("refuse to overwrite evidence report")
    try:report=join(a.isolated,a.prefix,a.controls,a.original,a.kfd)
    except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError) as e:p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"isolated_pass":42,"shared_prefixes_pass":10,
                      "original_binary_reproduced_fault":report["original_binary_reproduced_fault"],
                      "kernel_doorbell_provenance":"unverified",
                      "release_admitted":False}))
if __name__=="__main__":main()
