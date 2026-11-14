#!/usr/bin/env python3
"""Offline kprobe/ftrace readiness inventory and optional bounded CPU-only trace.

Default: inspect tracefs, installed kernel symbols and probe suitability.
--arm: root, explicit tracefs changes, no GPU workload or fault injection.
Uses kprobe_events *temporary* entries and removes only its own probes.
A hard Ctrl-C or killed process may leave probes: see --cleanup.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import time

PROBES = (
    ("evict", "evict_process_queues_cpsch"),
    ("unmap", "unmap_queues_cpsch"),
    ("mes", "remove_queue_mes_on_reset_option"),
    ("reset_mes", "reset_queues_mes"),
)
NAMESPACE = "gfx803k2"
VALID = re.compile(r"^[a-zA-Z_][a-zA-Z_0-9]*$")
def symbols(kallsyms: str) -> set[str]:
    return {match.group(1) for match in re.finditer(r"(?m)^[0-9a-fA-F]+ [tTwW] ([A-Za-z_]\w*)(?:\s.*)?$", kallsyms)}

def choose_available(available: set[str]) -> list[tuple[str, str]]:
    # Exact names preferred. Only exact compiler-suffixed names are admitted.
    result=[]
    for label,name in PROBES:
        candidates=sorted(x for x in available if x == name or x.startswith(name+"."))
        if len(candidates)==1 and VALID.fullmatch(candidates[0]):
            result.append((label,candidates[0]))
    return result

def trace_root() -> Path | None:
    for path in (Path("/sys/kernel/tracing"), Path("/sys/kernel/debug/tracing")):
        if (path / "kprobe_events").exists() and (path / "trace").exists():
            return path
    return None

def inventory(kallsyms: str, root: Path | None) -> dict:
    known=symbols(kallsyms)
    selected=choose_available(known)
    return {"schema":1,"namespace":NAMESPACE,
            "trace_root":str(root) if root else None,
            "probes":[{"label":label,"symbol":sym} for label,sym in selected],
            "unresolved":[label for label,_ in PROBES if label not in {x[0] for x in selected}],
            "scope":"postboot static availability; no incident-time call assertion",
            "advisory":"Return-value probes expose signed long $retval on x86_64; arguments require separately verified ABI and source."}

def write(path:Path,text:str)->None:
    path.write_text(text)

def cleanup(root:Path, labels:list[str])->None:
    # Scoped deletion: do not clear the global trace buffer or touch other probes.
    for label in reversed(labels):
        for prefix in ("r","p"):
            try:
                write(root/"events"/"kprobes"/(NAMESPACE+"_"+label+"_"+prefix)/"enable","0")
            except OSError:
                pass
            try:
                write(root/"kprobe_events","-:kprobes/"+NAMESPACE+"_"+label+"_"+prefix+"\n")
            except OSError:
                pass

def capture(root:Path, chosen:list[tuple[str,str]], seconds:int, out:Path)->dict:
    created=[]
    try:
        for label,sym in chosen:
            for prefix,definition in (
                ("p",f"p:kprobes/{NAMESPACE}_{label}_p {sym}\n"),
                ("r",f"r:kprobes/{NAMESPACE}_{label}_r {sym} ret=$retval\n")
            ):
                # Writing kprobe_events appends dynamically on tracefs.
                with (root/"kprobe_events").open("a") as f: f.write(definition)
                created.append((label,prefix))
        for label,prefix in created:
            write(root/"events"/"kprobes"/(NAMESPACE+"_"+label+"_"+prefix)/"enable","1")
        start=time.monotonic()
        # No workload initiated. Trace normal host activity only, for a short window.
        time.sleep(seconds)
        records=(root/"trace").read_text(errors="replace")
        scoped="\n".join(line for line in records.splitlines() if NAMESPACE+"_" in line)
        return {"status":"completed","duration_s":round(time.monotonic()-start,2),
                "events":scoped.splitlines(),"event_count":len(scoped.splitlines()),
                "warning":"No fault reproduction. Event omission is not proof branch is unreachable."}
    finally:
        cleanup(root,[label for label,_ in chosen])

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--seconds",type=int,default=10)
    p.add_argument("--arm",action="store_true",help="root-only, bounded tracefs probe attach; no GPU workload")
    p.add_argument("--cleanup",action="store_true",help="remove only gfx803k2-named probes")
    p.add_argument("--ack-tracefs-writes",action="store_true",
                   help="required for arming; no general 'safe GPU' claim")
    a=p.parse_args()
    if a.out.exists():p.error("refusing to overwrite")
    if not 1<=a.seconds<=30:p.error("1 <= seconds <= 30 required")
    root=trace_root()
    try: ks=Path("/proc/kallsyms").read_text()
    except OSError: ks=""
    report=inventory(ks,root)
    if a.cleanup:
        if not root:p.error("tracefs unavailable")
        cleanup(root,[label for label,_ in PROBES])
        report["cleanup"]="requested; only prefixed probes"
    if a.arm:
        if not a.ack_tracefs_writes:p.error("--ack-tracefs-writes required to arm")
        if not root:p.error("tracefs not mounted/available")
        if report["unresolved"]:p.error("probe symbols missing or ambiguous; inspect inventory first")
        if not ks:p.error("kallsyms unavailable")
        if (root/"events"/"kprobes"/(NAMESPACE+"_evict_p")).exists():
            p.error("stale probe already exists; use --cleanup after inspection")
        report["capture"]=capture(root,choose_available(symbols(ks)),a.seconds,a.out)
    else:
        report["capture"]={"status":"not-armed"}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("inventory written; armed="+str(a.arm)+"; initiated GPU workloads: 0")
    return 0

if __name__=="__main__":raise SystemExit(main())
