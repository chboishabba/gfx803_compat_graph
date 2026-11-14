#!/usr/bin/env python3
"""T1.05: offline HIP TopK symbol/fatbin attribution from exact libtorch_hip.so.

NEVER imports torch, HIP or GPU libraries, invokes no GPU workload.
Provides: SHA/Build-ID gate, exact device-stub/symbol inventory, ELF
offload-section metadata, optional bounded fatbin extraction, source hash,
and one-row/32-row resource scaling. Does NOT identify historical dispatch.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

SHAPES = ((1, 151936, 50), (32, 151936, 50))
FATBIN_LIMIT = 1024 * 1024 * 1024
SYMBOL_LIMIT = 300
TOPK_MATCH = re.compile(r"(mbtopk|sbtopk|warptopk|gatherTopK|TensorTopK|topk)", re.I)
# Generic .rodata is not evidence of a HIP code-object bundle.  Keep this
# deliberately specific so the receipt cannot mislabel ordinary constants as
# offload payloads.
SECTION_MATCH = re.compile(r"(hip_fatbin|llvm\.offload|offload)",re.I)

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def invoke(argv: list[str], max_bytes: int = 32_000_000) -> dict:
    if not shutil.which(argv[0]):
        return {"status":"tool-missing","argv":argv,"stdout":"","stderr":""}
    try:
        p=subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         timeout=120,check=False)
        return {"status":"ok" if p.returncode==0 else "failed","exit":p.returncode,
                "stdout":p.stdout[:max_bytes].decode("utf-8",errors="replace"),
                "stderr":p.stderr[:2000].decode("utf-8",errors="replace"),
                "truncated":len(p.stdout)>max_bytes}
    except (OSError,subprocess.TimeoutExpired) as e:
        return {"status":"error","error":str(e),"argv":argv,"stdout":"","stderr":""}

def invoke_matching_lines(argv: list[str], pattern: re.Pattern[str], max_matches: int = 20_000) -> dict:
    """Run a large inventory command without retaining unrelated symbols.

    libtorch_hip has a tens-of-megabytes complete symbol table.  The audit's
    evidence question is limited to TopK candidates, so retaining the entire
    table makes the safety cap reject an otherwise inspectable binary.  This
    streams stdout and records every matching line up to an explicit bound;
    the result remains an exact *matching-symbol* inventory, not a claim of a
    complete symbol-table inventory or runtime dispatch.
    """
    if not shutil.which(argv[0]):
        return {"status":"tool-missing","argv":argv,"stdout":"","stderr":""}
    try:
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert p.stdout is not None
        matches: list[str] = []
        truncated = False
        for raw in p.stdout:
            line = raw.decode("utf-8", errors="replace")
            if pattern.search(line):
                if len(matches) < max_matches:
                    matches.append(line)
                else:
                    truncated = True
        stderr = p.stderr.read(2000).decode("utf-8", errors="replace") if p.stderr else ""
        exit_code = p.wait(timeout=120)
        return {"status":"ok" if exit_code == 0 else "failed", "exit":exit_code,
                "stdout":"".join(matches), "stderr":stderr,
                "truncated":truncated, "matching_lines":len(matches)}
    except (OSError, subprocess.TimeoutExpired) as e:
        if 'p' in locals():
            p.kill()
            p.wait()
        return {"status":"error","error":str(e),"argv":argv,"stdout":"","stderr":""}

def parse_build_id(note: str) -> str | None:
    m=re.search(r"Build ID:\s*([0-9a-fA-F]+)",note)
    return m.group(1).lower() if m else None

def parse_symbols(text: str) -> list[dict]:
    # GNU readelf -W --dyn-syms and -Ws symbol tables; retain source text,
    # avoid guessing whether a stub actually executed.
    matched=[]
    for line in text.splitlines():
        if not TOPK_MATCH.search(line):continue
        m=re.match(r"\s*(\d+):\s+([0-9a-fA-F]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+)",line)
        if m:
            matched.append({"index":int(m.group(1)),"address":m.group(2),
                            "size_bytes":int(m.group(3)),"type":m.group(4),
                            "binding":m.group(5),"section":m.group(7),
                            "name":m.group(8)[:768]})
        else:
            matched.append({"raw":line[:768]})
    # Do not silently claim this is a complete symbol inventory.
    return matched[:SYMBOL_LIMIT]

def parse_sections(text: str) -> list[dict]:
    out=[]
    # E.g. [17] .hip_fatbin PROGBITS 00000000 00abc000 00001000 00 A 0 0 8
    pat=re.compile(r"^\s*\[\s*(\d+)\]\s+(\S+)\s+(\S+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+",re.M)
    for m in pat.finditer(text):
        if SECTION_MATCH.search(m.group(2)):
            out.append({"index":int(m.group(1)),"name":m.group(2),
                        "type":m.group(3),"file_offset":int(m.group(5),16),
                        "size_bytes":int(m.group(6),16)})
    return out

def shape_bounds(rows:int,cols:int,k:int) -> dict:
    n=rows*cols
    return {"rows":rows,"cols":cols,"k":k,"total_elements":n,
            "input_bytes_f32_min":n*4,
            "full_sort_key_bytes_min":n*4,
            "full_sort_indices_bytes_min":n*8,
            "output_values_bytes_f32_min":rows*k*4,
            "output_indices_i64_bytes_min":rows*k*8,
            "single_row_scaling_factor":rows,
            "notes":"Lower bounds only: not actual mbtopk temp buffer, CTAs, occupancy, LDS or registers"}

def source_scan(source:Path)->dict:
    data=source.read_bytes()
    text=data.decode(errors="replace")
    lines=text.splitlines()
    return {"path":str(source),"sha256":hashlib.sha256(data).hexdigest(),
            "size_bytes":len(data),
            "markers":{name:[i+1 for i,l in enumerate(lines) if name in l][:80]
                       for name in ("should_use_multiblock","mbtopk","sbtopk",
                                    "warptopk","multi_block","block_size","gridDim","threadIdx")},
            "source_binary_build_link_proven":False}

def audit(binary:Path, receipt:dict, source:Path|None, dump:Path|None)->dict:
    expected=receipt["t1_04_static_candidate"]["binary"]
    actual=sha256(binary)
    if actual!=expected["sha256"]:
        raise ValueError("FAIL CLOSED: libtorch_hip.so SHA differs from retained T1 receipt")
    note=invoke(["readelf","-n",str(binary)])
    if note["status"]!="ok":raise ValueError("readelf -n required for binary identity")
    build_id=parse_build_id(note["stdout"])
    if build_id!=expected["build_id"]:
        raise ValueError("FAIL CLOSED: TopK ELF Build ID differs from retained T1 receipt")
    # Stream/filter the huge complete symbol table; see invoke_matching_lines.
    sym=invoke_matching_lines(["readelf","-Ws",str(binary)], TOPK_MATCH)
    sec=invoke(["readelf","-WS",str(binary)])
    if sym["status"]!="ok" or sec["status"]!="ok":
        raise ValueError("readelf symbols and sections required")
    symbols=parse_symbols(sym["stdout"])
    sections=parse_sections(sec["stdout"])
    if sym.get("truncated"):
        raise ValueError("too many matching TopK symbols: refusing an incomplete inventory")
    if sec.get("truncated"):
        raise ValueError("readelf section output too long: cannot make complete section inventory")
    dumps=[]
    if dump:
        # objcopy extracts ELF sections only; it does not perform GPU execution,
        # disassemble or guarantee a valid HSACO.
        selected=[s for s in sections if "hip_fatbin" in s["name"]]
        if len(selected)!=1:raise ValueError("exactly one .hip_fatbin section required for extraction")
        item=selected[0]
        if item["size_bytes"]<=0 or item["size_bytes"]>FATBIN_LIMIT:
            raise ValueError("fatbin size outside bounded extraction limits")
        if dump.exists():raise ValueError("will not overwrite fatbin extraction")
        dump.parent.mkdir(parents=True,exist_ok=True)
        cmd=invoke(["objcopy","--dump-section",f"{item['name']}={dump}",str(binary)],
                   max_bytes=2048)
        if cmd["status"]!="ok":
            if dump.exists():dump.unlink()
            raise ValueError("objcopy fatbin extraction failed: "+cmd.get("stderr","")[:200])
        if not dump.exists() or dump.stat().st_size!=item["size_bytes"]:
            raise ValueError("fatbin extraction size mismatch")
        dumps.append({"path":str(dump),"sha256":sha256(dump),"size_bytes":dump.stat().st_size,
                      "type":"ELF section payload; NOT a proven HSACO or dispatched kernel"})
    return {"schema":1,"mode":"offline-binary","libtorch_hip":str(binary),
            "sha256":actual,"build_id":build_id,
            # The retained display is intentionally bounded.  Preserve the
            # streamed total separately so a 300-entry display never reads as
            # a complete symbol count.
            "symbols_total_matches":sym["matching_lines"],
            "symbols_displayed":len(symbols),
            "symbols_truncated_at":SYMBOL_LIMIT if sym["matching_lines"]>len(symbols) else None,
            "matching_symbols":symbols,
            "offload_sections":sections,"extracted_fatbin":dumps,
            "original_source":source_scan(source) if source else None,
            "case_bounds":[shape_bounds(*s) for s in SHAPES],
            "build_link_to_retained_source_proven":False,
            "actual_incident_executed_hsaco":None,
            "actual_incident_first_stalled_kernel":None,
            "limitations":[
                "readelf symbol presence cannot prove runtime selection",
                ".hip_fatbin may hold bundles; extraction is not kernel extraction",
                "source and ELF matching names are not build provenance",
                "grid, LDS, VGPR/SGPR, synchronization and real workspaces require exact code object metadata",
                "no GPU/HIP work executed"]}

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--libtorch-hip",type=Path,required=True)
    p.add_argument("--attribution-receipt",type=Path,required=True)
    p.add_argument("--source",type=Path)
    p.add_argument("--dump-fatbin",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():p.error("refusing to overwrite output")
    if a.dump_fatbin and a.dump_fatbin.resolve()==a.out.resolve():
        p.error("fatbin path must differ from JSON path")
    try:
        data=audit(a.libtorch_hip,json.loads(a.attribution_receipt.read_text()),a.source,a.dump_fatbin)
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as e:
        p.error(str(e))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")
    print("offline TopK ELF inventory saved",a.out,"no GPU executed")
if __name__=="__main__":
    raise SystemExit(main())
