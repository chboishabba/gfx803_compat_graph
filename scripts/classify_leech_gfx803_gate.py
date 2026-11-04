#!/usr/bin/env python3
"""Audit an observed LeechTransformer numerical GPU admission receipt.

A structurally valid FAILED gate is a reproducible negative-control
observation, never an accepted compatibility claim. This script does
not run GPU kernels or grant GPU execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

KNOWN_CONTROL_SHA256="1e3b5640995eaf7ca93517a19cad7f85639926d1e9b817c8b6c0b296e516aa79"
HASH=re.compile(r"^[0-9a-f]{64}$")
DENSE_KEYS=("dense_cpu_gpu_logits","teacher_layer_input",
            "teacher_layer_ffn","dense_gpu_repeat_1","dense_gpu_repeat_2")


class InvalidObservation(ValueError):
    pass


def sha256_file(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_gate(gate:dict)->dict:
    if not isinstance(gate,dict) or gate.get("admitted") is not False:
        raise InvalidObservation("not an explicitly rejected GPU gate")
    if gate.get("workload")!="LeechTransformer focused C2 training":
        raise InvalidObservation("wrong workload")
    if gate.get("gpu",{}).get("gcn_arch_name")!="gfx803":
        raise InvalidObservation("not a gfx803 device receipt")
    if gate.get("stack_id")!="gfx803_pytorch_stack_control":
        raise InvalidObservation("not the frozen 6.4 control lane")
    sha=gate.get("source_sha256")
    if not isinstance(sha,dict) or not all(
            HASH.fullmatch(str(sha.get(key,""))) for key in
            ("teacher","student","train")):
        raise InvalidObservation("missing source model/token identity")
    checks_result=gate.get("checks_result",{})
    if (checks_result.get("stage")!="teacher numerical parity" or
        checks_result.get("admitted") is not False):
        raise InvalidObservation("teacher parity failure not established")
    checks=checks_result.get("checks",{})
    for key in DENSE_KEYS:
        row=checks.get(key)
        if not isinstance(row,dict) or row.get("passed") is not False:
            raise InvalidObservation("no complete failing dense check: "+key)
        actual=row.get("max_abs_diff")
        limit=row.get("max_allowed_error")
        if (not isinstance(actual,(int,float)) or
                not isinstance(limit,(int,float)) or
                not actual>limit>0):
            raise InvalidObservation("invalid failure magnitude: "+key)
    if (gate.get("checked_train_rows")!=2 or
        gate.get("full_token_window_length")!=64):
        raise InvalidObservation("not the known 2x64 training-token gate")
    if checks["dense_cpu_gpu_logits"].get("shape")!=[2,64,2048]:
        raise InvalidObservation("unexpected dense logits shape")
    if checks["teacher_layer_input"].get("shape")!=[2,64,384]:
        raise InvalidObservation("unexpected layer-1 normalized shape")
    if any("focused" in key or "gradient" in key or "optimizer" in key
           for key in checks):
        raise InvalidObservation("cannot classify unexpectedly executed C2 phases")
    return {
      "status":"observed_rejection",
      "hardware_visible":True,
      "torch_import_and_gpu_visible_not_sufficient":True,
      "dense_cpu_gpu_numerically_admissible":False,
      "dense_same_device_repeatable":False,
      "c2_forward_executed_in_gate":False,
      "c2_gradients_executed_in_gate":False,
      "training_authorized_by_gate":False,
      "scientific_scope":"one actual teacher checkpoint and 2x64 token rows on ROCm 6.4 control",
      "not_a_schaka_10_1_result":True,
      "teacher_checkpoint_sha256":sha["teacher"],
      "student_candidate_sha256":sha["student"],
      "training_tokens_sha256":sha["train"],
      "dense_logits_max_abs_diff":checks["dense_cpu_gpu_logits"]["max_abs_diff"],
      "dense_repeat_max_abs_diff":max(
          checks["dense_gpu_repeat_1"]["max_abs_diff"],
          checks["dense_gpu_repeat_2"]["max_abs_diff"]),
      "miopen_solver_flag_provenance":"not recorded in this original receipt",
      "actual_rocblas_tensile_kernel_identity":"not recorded; must profile exact Leech shape",
      "candidate_patch_class":"Schaka gfx803 assembly WGM!=1 miscompute; requires a measured selected-kernel match",
      "claim_boundary":"No GPU training, solved driver, patched Nix binary, or release acceptance inferred from this classification."
    }


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--receipt",type=Path,required=True)
    parser.add_argument("--known-control-hash",action="store_true",
                        help="also require byte-identical stored Nov 4 original receipt")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    source_hash=sha256_file(args.receipt)
    if args.known_control_hash and source_hash!=KNOWN_CONTROL_SHA256:
        raise InvalidObservation("original receipt bytes differ from locked SHA256")
    observed=json.loads(args.receipt.read_text())
    report=classify_gate(observed)
    report["receipt_sha256"]=source_hash
    print(json.dumps(report,indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+"\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
