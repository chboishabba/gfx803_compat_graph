#!/usr/bin/env python3
"""Read-only post-reboot collector for one-shot TopK capture.

Does not access /dev/kfd, reset, restart or execute a GPU workload.
Preserves original records in a NEW folder and records command errors.
Systemd journal may be volatile; absence of previous-boot history is not
evidence no GPU errors occurred. Does not copy giant binary cores by default.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def collect(run:Path,out:Path):
    manifest=run/"manifest.json"
    if not manifest.is_file():
        raise ValueError("missing original one-shot capture manifest")
    info=json.loads(manifest.read_text())
    if info.get("mode")!="ONE-SHOT-KNOWN-GPU-HANG":
        raise ValueError("not a one-shot TopK run")
    if out.exists():
        raise ValueError("refuse overwrite postmortem output")
    if not out.parent.is_dir():
        raise ValueError("postmortem parent must exist")
    if out.resolve()==run.resolve() or run.resolve() in out.resolve().parents:
        raise ValueError("postmortem output must be separate from capture directory")
    out.mkdir(mode=0o700)
    boot=info["boot_id"]
    if not isinstance(boot,str) or len(boot)!=36 or boot.count("-")!=4:
        raise ValueError("capture has invalid original boot ID")
    # Boot ID, not -1: a later extra reboot must not shift attribution.
    commands={
        "original-kernel-journal.log":["journalctl","--boot",boot,"-k",
                                       "-o","short-iso-precise","--no-pager"],
        "original-system-journal.log":["journalctl","--boot",boot,
                                       "-o","short-iso-precise","--no-pager",
                                       "-g","amdgpu|kfd|GPU Hang|oomd|core dumped|segfault"],
        "original-coredumps-list.log":["coredumpctl","--boot",boot,"list","--no-pager"],
    }
    results={}
    for name,cmd in commands.items():
        dest=out/name
        with dest.open("wb") as fd:
            try:
                r=subprocess.run(cmd,stdout=fd,stderr=subprocess.PIPE,
                                 timeout=45,check=False)
                result={"returncode":r.returncode,"stderr":r.stderr.decode(errors="replace")[-1200:]}
            except (FileNotFoundError,subprocess.TimeoutExpired) as e:
                result={"error":str(e)}
            fd.flush()
            os.fsync(fd.fileno())
        result.update({"file":name,"bytes":dest.stat().st_size,"sha256":digest(dest)})
        results[name]=result
    found={}
    for name in ("kernel-journal.log","loaded-maps.log","kfd-return-probe.log",
                 "child-stdout.log","child-stderr.log","journal-stderr.log",
                 "kfd-return-probe-stderr.log","result.json"):
        p=run/name
        if p.is_file():
            found[name]={"sha256":digest(p),"bytes":p.stat().st_size}
    report={"schema":1,"mode":"POST-REBOOT-READ-ONLY-COLLECT",
            "original_run_id":info["run_id"],"original_boot_id":boot,
            "collected_at_ns":time.time_ns(),
            "original_manifest_sha256":digest(manifest),
            "original_artifacts":found,"journal_queries":results,
            "original_gpu_dispatch_proven":False,
            "first_kfd_return_proven_by_kernel_journal":False,
            "note":"bpftrace return may be present only if instrumented probe attached; absence cannot refute a return",
            "gpu_commands":0}
    p=out/"receipt.json"
    with p.open("x") as f:
        json.dump(report,f,indent=2,sort_keys=True)
        f.write("\n")
        f.flush();os.fsync(f.fileno())
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",type=Path,required=True,help="existing one-shot folder")
    p.add_argument("--out",type=Path,required=True,help="NEW persistent output directory")
    a=p.parse_args()
    try:
        r=collect(a.run,a.out)
    except (ValueError,OSError,KeyError) as e:
        p.error(str(e))
    print(json.dumps({"mode":r["mode"],"boot":r["original_boot_id"],
                      "gpu_commands":0,"out":str(a.out)}))
if __name__=="__main__":
    main()
