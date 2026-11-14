#!/usr/bin/env python3
"""T1.09-10 + K2.07 conservative binary/source/KFD evidence reconciliation.

Consumes committed original T1.04/T1.08 references plus NEW host outputs.
No GPU operations. Recompute attribution only from exact matching hashes.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

def load(p:Path)->dict:
    r=json.loads(p.read_text())
    if not isinstance(r,dict):raise ValueError("expected JSON object: "+str(p))
    return r

def join(source_ref:dict,container:dict,hsaco:dict,source:dict,
         old_join:dict,elf_inventory:dict,kfd:dict|None=None,trace:dict|None=None,
         note_metadata:dict|None=None)->dict:
    original=source_ref["t1_04_static_candidate"]
    if source.get("sha256")!=original["retained_pre_review_source"]["sha256"] or not source.get("source_verified"):
        raise ValueError("retained source SHA not verified")
    original_elf=original["binary"]
    if (elf_inventory.get("sha256")!=original_elf["sha256"] or
        elf_inventory.get("build_id")!=original_elf["build_id"]):
        raise ValueError("original libtorch_hip ELF identity mismatch")
    recorded_fatbins=elf_inventory.get("extracted_fatbin",[])
    if len(recorded_fatbins)!=1 or recorded_fatbins[0].get("sha256")!=container.get("sha256"):
        raise ValueError("fatbin SHA linkage mismatch")
    extracted=container.get("unbundled_output")
    if not extracted or extracted.get("sha256")!=hsaco.get("sha256") or extracted.get("size_bytes")!=hsaco.get("size_bytes"):
        raise ValueError("HSACO identity not matching original container")
    if hsaco.get("identity_verified") is not True or hsaco.get("mode")!="offline-hsaco-metadata":
        raise ValueError("HSACO identity and analysis mode must be verified")
    if old_join.get("gates",{}).get("K2.06",{}).get("status")!="reference-source-mapped":
        raise ValueError("original KFD non-MES reference receipt missing")
    if old_join.get("gpu_rerun") is not False:
        raise ValueError("unexpected GPU work in prior offline join")
    valid_gfx803="hip-amdgcn-amd-amdhsa--gfx803" in container.get("gfx803_candidates",[])
    if not valid_gfx803:
        raise ValueError("original container does not advertise gfx803")
    kfd_verified=bool(kfd and kfd.get("mode")=="offline-kfd-source-audit" and
                      kfd.get("reference_log_site_found") and kfd.get("fence_function_name_found"))
    run_gates={
        "T1.04":{"status":"source-candidate","name":"mbtopk"},
        "T1.05":{"status":"accepted-original-lib-and-fatbin",
                  "host_symbol_count":elf_inventory.get("symbols_total_matches")},
        "T1.08":{"status":"accepted-container-and-gfx803-target",
                  "bundle_occurrences":container.get("target_occurrences",{}).get("hip-amdgcn-amd-amdhsa--gfx803")},
        "T1.09":{"status":"verified-extracted-hsaco","sha256":hsaco["sha256"],
                  "metadata_kernel_blocks":hsaco.get("metadata_kernel_count_parsed"),
                  "named_topk_blocks":len(hsaco.get("topk_kernel_blocks",[]))},
        "T1.10":{"status":"verified-retained-source","sha256":source["sha256"],
                  "source_binary_build_link":False},
        "T1.06":{"status":"open","reason":"no original build manifest and historical loader path linkage"},
        "T1.07":{"status":"open","reason":"code-object inclusion does not establish actual selected incident kernel or grid"},
        "K2.06":{"status":"reference-source-mapped",
                  "selected_reference_path":"evict_process_queues_cpsch -> unmap_queues_cpsch -> amdkfd_fence_wait_timeout"},
        "K2.07":{"status":"source-crosscheck" if kfd_verified else "open",
                  "exact_cachyos_source_match":False},
        "K2.05":{"status":"open","incident_fence_return":None},
        "J1":{"status":"open","reason":"no paired actual incident TopK dispatch and KFD return"},
        "F1":{"status":"blocked","reason":"no proven minimal causal correction"},
        "release":{"status":"blocked","reason":"display GPU wedged and reset recovery unqualified"}
    }
    if note_metadata:
        if (note_metadata.get("mode")!="offline-amdgpu-msgpack-note" or
            note_metadata.get("hsaco_sha256")!=hsaco.get("sha256") or
            note_metadata.get("hsaco_size_bytes")!=hsaco.get("size_bytes")):
            raise ValueError("AMDGPU note identity mismatch")
        run_gates["T1.11"]={
            "status":"code-object-note-inventory",
            "total_metadata_kernels":note_metadata.get("metadata_kernel_count"),
            "readable_topk_kernel_names":note_metadata.get("topk_named_kernel_count"),
            "incident_executed":False}
    if trace:
        if trace.get("mode")!="INERT-TRACE-PLAN-ONLY" or trace.get("trace_armed") is not False:
            raise ValueError("trace plan cannot be admitted as active or historical trace")
        run_gates["K2.08"]={"status":"inert-plan-available",
                           "operator_eligibility":bool(trace.get("eligible_for_operator_review"))}
    return {"schema":1,"mode":"offline-final-evidence-join","gates":run_gates,
            "verified_hsaco_sha256":hsaco["sha256"],
            "verified_retained_source_sha256":source["sha256"],
            "gpu_runs":0,
            "historical_incident_topk_kernel":None,
            "historical_incident_kfd_return":None,
            "physical_acceptance":"open",
            "boundaries":["names and metadata in bundled HSACO are not an execution trace",
                         "historic source-to-binary provenance is not implied by matching source markers",
                         "exact CachyOS source identity unresolved",
                         "KFD original quiescence path and TopK original hang remain distinct causal targets"]}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("source-attribution","container-receipt","hsaco-metadata",
                 "retained-source","old-join","out"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--elf-inventory",type=Path,required=True)
    p.add_argument("--kfd-source",type=Path)
    p.add_argument("--safehost-plan",type=Path)
    p.add_argument("--note-metadata",type=Path)
    a=p.parse_args()
    if a.out.exists():p.error("refuse overwrite")
    try:
        r=join(load(a.source_attribution),load(a.container_receipt),
               load(a.hsaco_metadata),load(a.retained_source),load(a.old_join),
               load(a.elf_inventory),load(a.kfd_source) if a.kfd_source else None,
               load(a.safehost_plan) if a.safehost_plan else None,
               load(a.note_metadata) if a.note_metadata else None)
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as e:p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
    print("offline join saved; T1.06/T1.07/K2.05 remain OPEN; GPU runs 0")
if __name__=="__main__":main()
