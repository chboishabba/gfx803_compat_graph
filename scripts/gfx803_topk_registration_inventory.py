#!/usr/bin/env python3
"""CPU-only host registration candidate inventory, not runtime dispatch."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
from gfx803_mbtopk_elf_attribution import sha256, parse_build_id

PATTERN=re.compile(r"__hipRegister(?:Function|FatBinary|Var)|__hipUnregisterFatBinary|__hip_module_ctor|__device_stub__.*(?:topk|gather)|mbtopk|sbtopk|warptopk",re.I)

def scan(elf, flag):
    # Disk-backed stdout/stderr avoids pipe deadlock and unbounded RAM.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        subprocess.run(["readelf","-W",flag,str(elf)],stdout=out,stderr=err,
                       check=True,timeout=120)
        out.seek(0)
        rows=[]
        count=0
        for raw in out:
            line=raw.decode("utf-8",errors="replace").rstrip()
            if PATTERN.search(line):
                count+=1
                if len(rows)<20000:
                    rows.append(line)
        if count!=len(rows):
            raise ValueError("registration match cap exceeded; cannot claim complete inventory")
        return {"count":count,"lines":rows}

def audit(elf,receipt):
    expected=receipt["t1_04_static_candidate"]["binary"]
    actual=sha256(elf)
    if actual!=expected["sha256"]:
        raise ValueError("original ELF SHA mismatch")
    note=subprocess.check_output(["readelf","-n",str(elf)],timeout=120,text=True)
    build=parse_build_id(note)
    if build!=expected["build_id"]:
        raise ValueError("original ELF Build ID mismatch")
    return dict(schema=1,elf=str(elf),sha256=actual,build_id=build,
                symbols=scan(elf,"-s"),relocations=scan(elf,"-r"),
                source_binary_build_link_proven=False,
                incident_loader_identity_proven=False,
                incident_dispatch_proven=False,
                mode="offline-registration-candidates")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--elf",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():
        p.error("refusing overwrite")
    data=audit(a.elf,json.loads(a.receipt.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open("x") as f:
        json.dump(data,f,indent=2)
        f.write("\n")

if __name__=="__main__":
    main()
