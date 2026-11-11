#!/usr/bin/env python3
"""Integrity inventory of pinned upstream ROCm/gfx803 tests. No GPU execution."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SCHAKA="8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78"
PYTORCH="d70fd61bab718a3d49b053efa8058efc0566b2b0"
ASSETS={
  "pytorch_opinfo":("pytorch","test/test_ops.py","generated device/dtype CPU comparison"),
  "schaka_imgvalidate":("schaka","tools/imgvalidate.sh","upstream OCI whole-image suite; Podman-specific"),
  "schaka_verify":("schaka","verify.py","MIGraphX/rocBLAS/MIOpen/rocSOLVER/coherence; /opt/rocm paths"),
  "schaka_torch":("schaka","tools/correctness-suite/torch_op_suite.py","original PyTorch operator suite"),
  "schaka_miopen_build":("schaka","tools/correctness-suite/build.sh","MIOpen direct test builder"),
  "schaka_miopen":("schaka","tools/correctness-suite/run_all.sh","MIOpen solver-boundary correctness suite"),
  "schaka_fp16":("schaka","tools/correctness-suite/fp16_gemm_sweep.py","27-case GEMM/convolution"),
  "schaka_triton":("schaka","tools/correctness-suite/triton_dot_probe.py","Triton dot canaries"),
  "schaka_coherence":("schaka","tools/tc-staleness/ms3.py","GPU coherence + negative control"),
}

def pinned(root,rev):
    root=root.resolve()
    if not root.is_dir():raise ValueError("missing upstream source")
    check=subprocess.run(["git","-C",str(root),"rev-parse","HEAD"],capture_output=True,text=True)
    if check.returncode or check.stdout.strip()!=rev:
        raise ValueError("source not at exact pinned SHA")
    return root

def inventory(schaka,pytorch):
    roots={"schaka":pinned(schaka,SCHAKA),"pytorch":pinned(pytorch,PYTORCH)}
    result={}
    for name,(origin,rel,reason) in ASSETS.items():
        path=roots[origin]/rel
        if not path.is_file():raise ValueError("missing upstream asset "+str(path))
        result[name]={"origin":origin,"path":rel,"purpose":reason,
                      "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                      "status":"source-present-unexecuted"}
    return {"schema":1,"source_pins":{"schaka":SCHAKA,"pytorch":PYTORCH},
            "assets":result,"gpu_validated":False,"release_admitted":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schaka-source",required=True,type=Path)
    p.add_argument("--pytorch-source",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    if a.out.exists():p.error("refuse overwrite")
    try:report=inventory(a.schaka_source,a.pytorch_source)
    except (ValueError,OSError) as ex:p.error(str(ex))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("SOURCE INVENTORY ONLY:",a.out)
if __name__=="__main__":main()
