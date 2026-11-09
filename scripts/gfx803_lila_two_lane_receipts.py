#!/usr/bin/env python3
"""Cross-repository fail-closed adjudicator for actual LILA 6.4/10.1 receipts.

Inputs are physical operator and model receipts, not synthetic source checks.
This adjudicates *candidate numerical parity*, not long-run training safety
or native Nix release acceptance. No GPU executes in this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def adjudicate(lane: str, gate: dict, *, summary: dict | None = None,
               on: dict | None = None, off: dict | None = None,
               wgm_join: dict | None = None, wgm_join_sha: str | None = None) -> dict:
    if lane not in ("6.4-cpu-linear", "6.4-wgm1-qkv", "10.1-schaka"):
        raise ValueError("unsupported LILA repair lane")
    checks = gate.get("checks_result", {}).get("checks")
    passed = (isinstance(checks, dict) and bool(checks) and
              all(isinstance(value, dict) and value.get("passed") is True
                  for value in checks.values()) and
              gate.get("checks_result", {}).get("stage") == "complete")
    source = gate.get("source_sha256")
    if not isinstance(source, dict):
        source = {}
    source_complete = (isinstance(source, dict) and
                       all(isinstance(source.get(key), str) and
                           len(source[key]) == 64
                           for key in ("teacher", "student", "train")))
    arch = gate.get("gpu", {}).get("gcn_arch_name")
    real_gpu = isinstance(arch, str) and arch.startswith("gfx803")
    errors = []
    if not source_complete: errors.append("source SHA evidence incomplete")
    if not real_gpu: errors.append("no attested physical gfx803")
    if not passed: errors.append("full dense/C2 forward-backward-step numerical parity failed")
    if lane in ("6.4-cpu-linear", "6.4-wgm1-qkv"):
        repair = gate.get("linear_repair") or {}
        valid_hybrid = (
            repair.get("kind") == "cpu-fp32-linear-diagnostic" and
            repair.get("installed") is True and
            isinstance(repair.get("gpu_linear_calls_repaired"), int) and
            repair["gpu_linear_calls_repaired"] > 0 and
            repair.get("training_admission") == "denied" and
            repair.get("full_gpu_execution") is False and
            gate.get("gate_only_hybrid") is True and
            gate.get("admitted") is False and
            str(gate.get("torch_hip", "")).startswith("6.4")
        )
        if not valid_hybrid: errors.append("no valid 6.4 hybrid/denied receipt")
        if lane == "6.4-wgm1-qkv":
            qkv=repair.get("wgm1_qkv") or {}
            valid_wgm1=(isinstance(qkv.get("forced_qkv_gpu_forward_calls"),int) and
                        qkv["forced_qkv_gpu_forward_calls"]>0 and
                        qkv.get("torch_default_rocblas_sgemm_fixed") is False and
                        qkv.get("gpu_backward") is False and
                        qkv.get("admission")=="denied" and
                        isinstance(qkv.get("source_join_sha256"),str) and
                        len(qkv["source_join_sha256"])==64)
            if not valid_wgm1:
                errors.append("no genuine WGM1 QKV dispatch receipt")
            trace=(wgm_join or {}).get("trace") or {}
            join_valid=(
                isinstance(wgm_join,dict) and
                isinstance(wgm_join_sha,str) and
                wgm_join_sha==qkv.get("source_join_sha256") and
                wgm_join.get("schema_version")==2 and
                wgm_join.get("teacher_sha256")==source.get("teacher") and
                wgm_join.get("rocblas_sha256")==qkv.get("rocblas_sha256") and
                wgm_join.get("input_sha256")==qkv.get("original_input_sha256") and
                wgm_join.get("gpu_arch")==arch and
                wgm_join.get("torch_hip")==gate.get("torch_hip") and
                wgm_join.get("attribution_complete") is True and
                wgm_join.get("profile_observer_effect_absent_for_first_output") is True and
                wgm_join.get("no_training_admission") is True and
                isinstance(wgm_join.get("unprofiled_repeats_completed"),int) and
                wgm_join["unprofiled_repeats_completed"]>=100 and
                wgm_join.get("unprofiled_numerics")=="correct-at-tested-shape" and
                trace.get("status")=="identified" and trace.get("wgm")==1 and
                trace.get("unique_kernel_names")==[qkv.get("reported_kernel")]
            )
            if not join_valid:
                errors.append("retained 100-repeat same-source WGM1 join unavailable or inconsistent")
        return {
            "lane": lane, "numerical_hybrid_diagnostic_passed":
                bool(passed and source_complete and real_gpu and valid_hybrid and not errors),
            "gpu_native_correctness": "not-established",
            "training_admitted": False, "release_accepted": False,
            "errors": errors,
        }
    # One AdamW update is an initial parity gate, NOT a C2 training
    # stability certificate. Require a matched 20-step CPU/HIP trajectory
    # (loss, gradient, post-step logits and same-GPU repeat at every step).
    result=gate.get("checks_result") or {}
    evidence=result.get("checks") or {}
    trajectory=result.get("stability_trajectory") or []
    stability_complete=(
        isinstance(result.get("stability_steps_requested"),int) and
        result["stability_steps_requested"]>=20 and
        isinstance(result.get("stability_steps_completed"),int) and
        result["stability_steps_completed"]>=20 and
        isinstance(trajectory,list) and len(trajectory)>=19 and
        all(isinstance(t,dict) and t.get("step")==i for i,t in
            enumerate(trajectory[:19],start=2)) and
        all((isinstance(evidence.get(f"{kind}_{i}"),dict) and
              evidence[f"{kind}_{i}"].get("passed") is True)
            for i in range(2,21)
            for kind in ("stability_loss_step","stability_gradients_step",
                         "stability_post_step_logits","stability_gpu_repeat"))
    )
    if not stability_complete:
        errors.append("20-step matched C2 optimizer drift trajectory absent or failed")
    before = gate.get("shim_runtime_before") or {}
    after = gate.get("shim_runtime_after") or {}
    same_shim = (before.get("shim_mapped") is True and
                 after.get("shim_mapped") is True and
                 before.get("shim_enabled") is True and
                 after.get("shim_enabled") is True and
                 before.get("shim_sha256") == after.get("shim_sha256") and
                 before.get("shim_path") == after.get("shim_path") and
                 before.get("selected_rocm_root") ==
                    after.get("selected_rocm_root") and
                 str(before.get("selected_rocm_root", "")).startswith("/nix/store/"))
    if not same_shim: errors.append("same-process shim/root provenance incomplete")
    # The pinned Schaka ROCm 10.1 image reports torch.version.hip
    # '7.16.26385'; it is a Torch build identifier, not the ROCm tree's
    # /core-10.1 directory name. Match the actually measured ABI and
    # selected immutable runtime, not a made-up 10.1 prefix.
    if gate.get("torch_hip") != "7.16.26385":
        errors.append("wrong selected Schaka Torch HIP build identifier")
    if before.get("rocblas_preload") != after.get("rocblas_preload") or not str(
            before.get("rocblas_preload", "")).startswith(
                str(before.get("selected_rocm_root", "")) + "/lib/"):
        errors.append("missing or mismatched exact same-root rocBLAS preload")
    if not (isinstance(summary, dict) and
            summary.get("status") == "supports-scoped-interposer-effect" and
            summary.get("shim_effect_at_original_QKV_shape") is True and
            summary.get("both_traces_complete_and_observer_effect_free") is True and
            summary.get("actual_interposer_kernel_discrimination") is True and
            summary.get("same_library_shim_fixture_and_numeric_identity") is True):
        errors.append("independent profiler-verified original QKV ON/OFF not established")
    if not (isinstance(on, dict) and isinstance(off, dict)):
        errors.append("missing both independently joined QKV arm traces")
    else:
        for name, arm in (("on", on), ("off", off)):
            if (arm.get("teacher_sha256") != (source or {}).get("teacher") or
                arm.get("shim_sha256") != before.get("shim_sha256") or
                arm.get("shim_realpath") != before.get("shim_path") or
                arm.get("required_image_root") != before.get("selected_rocm_root") or
                arm.get("torch_hip") != gate.get("torch_hip")):
                errors.append(name + " QKV trace belongs to another source/runtime")
    # Even complete model parity + scoped interposer attribution is not proof
    # of sustained training, backprop kernel identity across all shapes or KFD safety.
    return {
        "lane": lane,
        "numerical_candidate_supported": not errors and passed and
            gate.get("admitted") is True,
        "training_admitted": False, "release_accepted": False,
        "stability_and_all_kernel_attribution": "open",
        "errors": errors,
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lane", choices=["6.4-cpu-linear", "6.4-wgm1-qkv", "10.1-schaka"], required=True)
    p.add_argument("--gate-receipt", type=Path, required=True)
    p.add_argument("--wgm-join", type=Path,
                   help="Required for 6.4-wgm1-qkv: original 100-repeat trace_join.json")
    p.add_argument("--shim-ab-dir", type=Path,
                   help="Required for 10.1: directory with summary and per-arm trace joins")
    p.add_argument("--out", type=Path, required=True)
    a=p.parse_args()
    if a.out.exists():
        p.error("refuse to overwrite pre-existing evidence")
    if a.lane == "6.4-wgm1-qkv" and a.wgm_join is None:
        p.error("WGM1 needs the original retained 100-repeat trace_join.json")
    if a.lane == "10.1-schaka" and a.shim_ab_dir is None:
        p.error("10.1 requires separately profiled original QKV shim ON/OFF")
    try:
        gate=json.loads(a.gate_receipt.read_text())
        summary=on=off=wgm_join=wgm_join_sha=None
        if a.wgm_join:
            raw=a.wgm_join.read_bytes()
            wgm_join_sha=hashlib.sha256(raw).hexdigest()
            wgm_join=json.loads(raw)
        if a.shim_ab_dir:
            summary=json.loads((a.shim_ab_dir/"shim_ab_summary.json").read_text())
            on=json.loads((a.shim_ab_dir/"on/trace_join.json").read_text())
            off=json.loads((a.shim_ab_dir/"off/trace_join.json").read_text())
        result=adjudicate(a.lane,gate,summary=summary,on=on,off=off,
                          wgm_join=wgm_join,wgm_join_sha=wgm_join_sha)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result={"lane":a.lane,"training_admitted":False,
                "release_accepted":False,"errors":[str(exc)]}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,sort_keys=True))
    key=("numerical_hybrid_diagnostic_passed" if a.lane.startswith("6.4-")
         else "numerical_candidate_supported")
    return 0 if result.get(key) is True else 3


if __name__ == "__main__":
    raise SystemExit(main())
