#!/usr/bin/env python3
"""Produce a gated KFD return-trace plan for a DIFFERENT, recoverable GPU host.

Generates an inert bpftrace source file and JSON qualification. Never runs
bpftrace, accesses /dev/kfd, initializes HIP, changes tracefs or launches a
GPU workload. Exact probe names must be checked on the SECOND host.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

PROBES=(
    ("evict_process_queues_cpsch","kfd_dqm_evict"),
    ("unmap_queues_cpsch","kfd_unmap"),
    ("amdkfd_fence_wait_timeout","fence_wait"),
    ("kfd_process_evict_queues","kfd_process_evict"),
    ("kgd2kfd_quiesce_mm","kfd_quiesce"),
)
def generate()->str:
    parts=[
        "/* Offline generated trace plan. DO NOT run on sole display GPU.",
        "   Verify symbols and a recoverable non-display target first.",
        "   bpftrace printf/retval semantics depend on installed version. */",
        'BEGIN { printf("KFD K2.05 scoped trace started: no GPU workload from this script\\n"); }']
    for symbol,label in PROBES:
        parts.append(f'kprobe:{symbol} {{ @start_{label}[tid] = nsecs; '
                     f'printf("ENTER {label} pid=%d tid=%d at=%llu\\n", pid, tid, nsecs); }}')
        parts.append(f'kretprobe:{symbol} {{ printf("RETURN {label} pid=%d tid=%d ret=%ld elapsed_ns=%llu\\n",'
                     f' pid, tid, retval, @start_{label}[tid] ? nsecs-@start_{label}[tid] : 0); '
                     f'delete(@start_{label}[tid]); }}')
    parts.append('END { printf("KFD scoped trace ended\\n"); }')
    return "\n".join(parts)+"\n"

def verdict(safety:dict)->dict:
    # Explicitly fail closed; no implied readiness from tool availability.
    required=("separate_host","non_display_gpu","independent_remote_control",
              "durable_out_of_band_logs","kernel_debug_source_match",
              "rollback_recovery_plan")
    missing=[x for x in required if safety.get(x) is not True]
    return {"schema":1,"mode":"INERT-TRACE-PLAN-ONLY",
            "probe_functions":[s for s,_ in PROBES],
            "safety_criteria":{key:bool(safety.get(key) is True) for key in required},
            "missing_or_false_criteria":missing,
            "eligible_for_operator_review":not missing,
            "trace_armed":False,"gpu_executed":False,
            "provenance":["read-only symbol confirmation needed on dedicated test host",
                          "kernel probe may alter timing and requires explicit operator decision",
                          "historical Nov 14 incident return cannot be recovered by future probe",
                          "T1 code-object dispatch evidence needs separate runtime instrumentation"]}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--trace-source",type=Path,required=True)
    p.add_argument("--qualification",type=Path,
                   help="optional JSON safety checklist, defaults to NOT READY")
    a=p.parse_args()
    if a.out.exists() or a.trace_source.exists():p.error("no overwrites")
    try:
        safety=json.loads(a.qualification.read_text()) if a.qualification else {}
        result=verdict(safety)
    except (OSError,ValueError) as e:p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.trace_source.parent.mkdir(parents=True,exist_ok=True)
    a.trace_source.write_text(generate())
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("inert source generated, trace armed: NO, safe host eligible:",
          result["eligible_for_operator_review"])
if __name__=="__main__":main()
