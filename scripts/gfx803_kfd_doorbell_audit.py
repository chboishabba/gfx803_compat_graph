#!/usr/bin/env python3
"""Read-only KFD doorbell/queue and amdgpu fault-era host diagnostics.

Historical gfx7/8 SDMA callback fix: 34659c1a1f4fd4c148ab13e13b11fd64df01ffcd.
Gfx7/8 queue validation: 542c3bb836733a1325874310d54d25b4907ed10e.
This script NEVER infers backport presence from a modern kernel version;
only a matching kernel source/config/build proves patch presence.
No modification to /sys, /dev/kfd, modules, drivers or reset controls.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PATCHES={
 "sdma_callback":"34659c1a1f4fd4c148ab13e13b11fd64df01ffcd",
 "gfx7_8_queue_validation":"542c3bb836733a1325874310d54d25b4907ed10e",
}
PATTERNS={
 "sdma_or_doorbell":re.compile(r"sdma|doorbell|hqd_sdma|queue reset",re.I),
 "gpu_vm_fault":re.compile(r"vm fault|page.not.present|protection.fault|gpu fault|0x1004800c",re.I),
 "queue_timeout":re.compile(r"ring .*timeout|scheduler .*not ready|queue.*hang|gpu reset",re.I),
 "memory_exhaustion":re.compile(r"out of memory|out-of-memory|allocation fail|oom",re.I),
}
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def command(argv,timeout=15):
    try:
        p=subprocess.run(argv,capture_output=True,timeout=timeout)
        return {"returncode":p.returncode,"stdout":p.stdout.decode("utf8","replace"),
                "stderr":p.stderr.decode("utf8","replace")}
    except (OSError,subprocess.TimeoutExpired) as e:
        return {"returncode":None,"error":str(e),"stdout":"","stderr":""}

def kernel_source_check(path):
    # This is only an optional provenance aid for a developer-supplied
    # *exactly matched* build tree, never an automatic kernel-version guess.
    root=path.resolve()
    files=[
        root/"drivers/gpu/drm/amd/amdgpu/amdgpu_amdkfd_gfx_v7.c",
        root/"drivers/gpu/drm/amd/amdgpu/amdgpu_amdkfd_gfx_v8.c",
    ]
    if not all(f.is_file() for f in files):
        return {"status":"source-files-missing","patch_presence_verified":False}
    findings={}
    for file in files:
        text=file.read_text(errors="replace")
        findings[file.name]={"callback_implementation":
            "kgd_hqd_sdma_get_doorbell" in text,
            "callback_assignment":
            bool(re.search(r"\.hqd_sdma_get_doorbell\s*=\s*kgd_hqd_sdma_get_doorbell",text)),
            "sha256":sha(file)}
    complete=all(x["callback_implementation"] and x["callback_assignment"]
                 for x in findings.values())
    return {"status":"source-callbacks-present" if complete else "source-callbacks-missing",
            "source_files":findings,
            "patch_presence_verified":False,
            "caveat":"Matching the running kernel binary to this source tree requires independent build provenance; callbacks alone do not verify queue or fault correctness"}

def audit(since,source=None):
    journal=command(["journalctl","-k","--since",since,
                    "--no-pager","-o","short-iso"])
    lines=journal["stdout"].splitlines() if journal["returncode"]==0 else []
    categories={key:[] for key in PATTERNS}
    for line in lines:
        for key,pattern in PATTERNS.items():
            if pattern.search(line):categories[key].append(line)
    info={"schema":1,
          "kernel_release":os.uname().release,
          "kernel_version":os.uname().version,
          "amdgpu_modinfo":command(["modinfo","-F","vermagic","amdgpu"]),
          "amdgpu_module_loaded":Path("/sys/module/amdgpu").exists(),
          "kfd_device_present":Path("/dev/kfd").exists(),
          "journal_available":journal["returncode"]==0,
          "journal_returncode":journal["returncode"],
          "journal_error":journal["stderr"][-1200:],
          "matched_kernel_lines":categories,
          "patches_to_check":PATCHES,
          "historical_sdma_callback_presence_in_running_kernel":"unverified",
          "historical_queue_validation_presence_in_running_kernel":"unverified",
          "diagnosis":"observations only; SDMA callback crash and GPU VM faults are distinct failure classes",
          "gpu_executed":False,"release_admitted":False}
    if source is not None:info["optional_source_check"]=kernel_source_check(source)
    return info,journal

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--since",default="today",help="journalctl --since expression")
    p.add_argument("--kernel-source",type=Path,default=None)
    a=p.parse_args(argv)
    if a.out.exists():p.error("refuse existing evidence directory")
    record,journal=audit(a.since,a.kernel_source)
    a.out.mkdir(parents=True)
    raw=a.out/"kernel-journal.txt"
    raw.write_text(journal["stdout"]+"\nSTDERR:\n"+journal["stderr"])
    record["raw_journal_sha256"]=sha(raw)
    (a.out/"matrix.json").write_text(json.dumps(record,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"kernel":record["kernel_release"],
                     "journal_available":record["journal_available"],
                     "fault_lines":len(record["matched_kernel_lines"]["gpu_vm_fault"]),
                     "queue_lines":len(record["matched_kernel_lines"]["queue_timeout"]),
                     "sdma_doorbell_lines":len(record["matched_kernel_lines"]["sdma_or_doorbell"]),
                     "running_kernel_patch_verified":False}))
    return 0

if __name__=="__main__":sys.exit(main())
