#!/usr/bin/env python3
"""Independent offline Leech QKV/SGEMM same-image proof consumer for gfx803.

Validates the ACTUAL GPU FP32 output bytes against the frozen CPU reference,
not just a 'pass' flag. Reads both stock shim ON/OFF original-model receipts,
their rocprofv3 marker/kernels and the published source/fixture identities.
Optional --attach stages original bytes into the gfx803 release evidence root,
rechecks them, and records a SCOPED leech_qkv capability in an unaccepted
candidate. It never admits C2 training, sustained stability, or ROCm as a
whole. Patch author: Schaka. Hardware repro and independent packaging:
chboishabba/gfx803_compat_graph and LeechTransformer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
from pathlib import Path

ORIGINAL_INPUT = "6e33dd589ce2fdc69f953fe1e195016076b883a7948f72a002de05fb49056cb5"
ORIGINAL_TEACHER = "581fdc3b4b6d169a03e2b06896e10d454fd4f819b40a2836c1d5b76849e4c674"
MIN_REPEATS = 100
ATOL_MAX = 0.001
RTOL_MAX = 0.0001
FILES = (
    "fixture/manifest.json", "fixture/input.f32", "fixture/weight.f32",
    "fixture/reference_f32.f32", "fixture/reference_f64_cast_f32.f32",
    "fixture/reference_full_torch.f32",
    "on/unprofiled.json", "on/profiled.json", "on/trace_join.json",
    "on/first-output.f32", "on/profile-output.f32",
    "off/unprofiled.json", "off/profiled.json", "off/trace_join.json",
    "off/first-output.f32", "off/profile-output.f32",
)


class QKVAdmissionError(ValueError):
    pass


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fd:
        for chunk in iter(lambda: fd.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    o = json.loads(Path(path).read_text())
    if not isinstance(o, dict):
        raise QKVAdmissionError("expected object: " + str(path))
    return o


def fp32_compare(reference: Path, output: Path, *, atol: float, rtol: float) -> dict:
    a, b = Path(reference).read_bytes(), Path(output).read_bytes()
    if len(a) != len(b) or len(a) == 0 or len(a) % 4:
        raise QKVAdmissionError("actual QKV output byte length differs from original reference")
    wrong = 0
    largest = 0.0
    for (want,), (got,) in zip(struct.iter_unpack("<f", a), struct.iter_unpack("<f", b)):
        if not math.isfinite(want) or not math.isfinite(got):
            raise QKVAdmissionError("nonfinite actual QKV output or reference")
        deviation = abs(want-got)
        largest = max(largest, deviation)
        if deviation > atol + rtol * abs(want):
            wrong += 1
    return {"status": "pass" if wrong == 0 else "fail",
            "max_abs": largest, "outside_tolerance": wrong,
            "compared_fp32_values": len(a) // 4,
            "reference_sha256": digest(reference),
            "gpu_output_sha256": digest(output)}


def verify_bundle(bundle: Path, *, expected_rocm_root: Path,
                  exact_teacher: bool = True) -> dict:
    bundle = Path(bundle)
    root = Path(expected_rocm_root).resolve()
    if not root.is_dir() or not str(root).startswith("/nix/store/"):
        raise QKVAdmissionError("expected a real imported Nix-store ROCm root")
    for rel in FILES:
        p = bundle / rel
        if not p.is_file() or not p.resolve().is_relative_to(bundle.resolve()):
            raise QKVAdmissionError("missing/escaping original evidence: " + rel)
    manifest = load_json(bundle / "fixture/manifest.json")
    if manifest.get("kind") != "leech-qkv-original-fp32":
        raise QKVAdmissionError("fixture not produced by original Leech QKV exporter")
    if manifest.get("gemm_logical_m_n_k") != [128, 1152, 384]:
        raise QKVAdmissionError("not the original physical failing Leech QKV shape")
    if exact_teacher and manifest.get("teacher_sha256") != ORIGINAL_TEACHER:
        raise QKVAdmissionError("wrong dense teacher SHA256")
    tensor_records = manifest.get("tensors", {})
    for key in ("input", "weight", "reference_f32", "reference_f64_cast_f32", "reference_full_torch"):
        t = tensor_records.get(key, {})
        if t.get("file") != key + ".f32":
            raise QKVAdmissionError("unexpected fixture tensor identity " + key)
        p = bundle / "fixture" / (key + ".f32")
        if t.get("sha256") != digest(p) or t.get("bytes") != p.stat().st_size:
            raise QKVAdmissionError("fixture tensor hash/size mismatch: " + key)
    if tensor_records["input"]["sha256"] != ORIGINAL_INPUT:
        raise QKVAdmissionError("not exact original CPU-copy QKV input")
    if manifest.get("bias_present"):
        bias = bundle / "fixture/bias.f32"
        if not bias.is_file() or digest(bias) != tensor_records.get("bias", {}).get("sha256"):
            raise QKVAdmissionError("original QKV bias missing or altered")
    joined = {}
    receipts = {}
    for arm in ("on", "off"):
        r = load_json(bundle / arm / "unprofiled.json")
        p = load_json(bundle / arm / "profiled.json")
        j = load_json(bundle / arm / "trace_join.json")
        if any(r.get("arm") != arm or p.get("arm") != arm for _ in (0,)):
            raise QKVAdmissionError("shim arm label mismatch")
        if r.get("mode") != "shim" or not r.get("shim_actually_mapped"):
            raise QKVAdmissionError("stock Schaka shim not actually mapped into original QKV process")
        if not str(r.get("torch_hip", "")).startswith("10.1"):
            raise QKVAdmissionError("wrong torch HIP version for claimed 10.1")
        if Path(r.get("required_image_root", "")).resolve() != root:
            raise QKVAdmissionError("foreign ROCm root in shim A/B")
        for field in ("rocblas_realpath", "shim_realpath"):
            if not Path(r.get(field, "")).resolve().is_relative_to(root):
                raise QKVAdmissionError("mixed ABI/foreign library in " + field)
        if Path(r["shim_realpath"]).name != "libgfx803_sgemm_shim.so":
            raise QKVAdmissionError("wrong upstream interposer identity")
        for path_field, sha_field in (("rocblas_realpath", "rocblas_sha256"),
                                      ("shim_realpath", "shim_sha256")):
            q = Path(r[path_field])
            if not q.is_file() or digest(q) != r.get(sha_field):
                raise QKVAdmissionError("actual library SHA mismatch: " + path_field)
        if j.get("attribution_complete") is not True or j.get("profiler_observer_effect_absent") is not True:
            raise QKVAdmissionError("no actual observer-free original GPU kernel trace: " + arm)
        if j.get("unprofiled_status") != r.get("status"):
            raise QKVAdmissionError("trace and unprofiled numerical statuses disagree")
        if (j.get("rocblas_sha256") != r.get("rocblas_sha256") or
                j.get("shim_sha256") != r.get("shim_sha256") or
                j.get("fixture_manifest_sha256") != digest(bundle / "fixture/manifest.json")):
            raise QKVAdmissionError("trace not same original QKV bytes/runtime")
        reps = r.get("repeat_metrics", [])
        if len(reps) < MIN_REPEATS or len(r.get("output_sha256_by_repeat", [])) != len(reps):
            raise QKVAdmissionError("fewer than 100 real QKV repeats: " + arm)
        if not all(str(x) and len(x)==64 for x in r["output_sha256_by_repeat"]):
            raise QKVAdmissionError("invalid output hashes")
        for field, file in (("raw_first_output_sha256", "first-output.f32"),):
            if r.get(field) != digest(bundle / arm / file):
                raise QKVAdmissionError("original GPU output bytes do not match receipt: " + arm)
        if r["output_sha256_by_repeat"][0] != digest(bundle / arm / "first-output.f32"):
            raise QKVAdmissionError("GPU output SHA array does not match original tensor: " + arm)
        if p.get("raw_first_output_sha256") != digest(bundle / arm / "profile-output.f32"):
            raise QKVAdmissionError("profiled output tensor SHA mismatch: " + arm)
        if p.get("output_sha256_by_repeat", [None])[0] != r["output_sha256_by_repeat"][0]:
            raise QKVAdmissionError("profiler observer effect changed original GPU output: " + arm)
        atol = float(r.get("threshold", {}).get("atol", float("inf")))
        rtol = float(r.get("threshold", {}).get("rtol", float("inf")))
        if not (0 <= atol <= ATOL_MAX and 0 <= rtol <= RTOL_MAX):
            raise QKVAdmissionError("operator loosened original QKV acceptance tolerance: " + arm)
        comparison = fp32_compare(bundle / "fixture/reference_full_torch.f32",
                                  bundle / arm / "first-output.f32", atol=atol, rtol=rtol)
        if (r["status"] == "correct-at-tested-shape") != (comparison["status"] == "pass"):
            raise QKVAdmissionError("numerical result differs from raw QKV bytes: " + arm)
        if arm == "on":
            if comparison["status"] != "pass" or not all(x.get("pass") for x in reps):
                raise QKVAdmissionError("stock Schaka shim did not pass every original QKV run")
            if len(set(r["output_sha256_by_repeat"])) != 1:
                raise QKVAdmissionError("stock shim QKV repeated inference changed outputs")
        receipts[arm], joined[arm] = (r, comparison), j
    on, off = receipts["on"][0], receipts["off"][0]
    if any(on.get(k) != off.get(k) for k in ("rocblas_sha256","shim_sha256",
                                            "fixture_manifest_sha256","teacher_sha256")):
        raise QKVAdmissionError("shim arms used different libraries or original model")
    if on["fixture_manifest_sha256"] != digest(bundle / "fixture/manifest.json"):
        raise QKVAdmissionError("original fixture has changed since GPU execution")
    return {"status": "scoped-original-qkv-pass-not-training-admission",
            "passed": True, "runtime_root": str(root),
            "teacher_sha256": manifest["teacher_sha256"],
            "input_sha256": ORIGINAL_INPUT,
            "rocblas_sha256": on["rocblas_sha256"],
            "shim_sha256": on["shim_sha256"],
            "shim_effect_discriminated": receipts["off"][1]["status"] == "fail",
            "on_error": receipts["on"][1], "off_error": receipts["off"][1],
            "original_GPU_repeats": len(on["repeat_metrics"]),
            "Schaka_patch_owner": "Schaka/rocm-gfx803",
            "consumer": "chboishabba gfx803_compat_graph / LeechTransformer",
            "no_C2_or_training_admission": True}


def stage_original_evidence(source: Path, fixture: Path, dest: Path):
    source, fixture = Path(source).resolve(), Path(fixture).resolve()
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise QKVAdmissionError("refuse overwrite of an existing release QKV evidence bundle")
    for name in FILES:
        src = fixture / name.split("/", 1)[1] if name.startswith("fixture/") else source / name
        if not src.is_file():
            raise QKVAdmissionError("cannot stage unretained original evidence: " + name)
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
    if (fixture/"bias.f32").is_file():
        shutil.copy2(fixture/"bias.f32", dest/"fixture/bias.f32")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, help="Leech 10.1 shim A/B output root")
    ap.add_argument("--fixture", type=Path, help="original QKV fixture")
    ap.add_argument("--bundle", type=Path, help="existing staged release-evidence/leech_qkv dir")
    ap.add_argument("--runtime-root", type=Path, required=True)
    ap.add_argument("--evidence-root", type=Path, help="stage into this release evidence root")
    ap.add_argument("--candidate", type=Path, help="candidate JSON to attach if real evidence passed")
    ap.add_argument("--lock", type=Path, default=Path("nix/gfx803/upstream.json"))
    args = ap.parse_args()
    try:
        if args.bundle:
            bundle = args.bundle
        elif args.source and args.fixture and args.evidence_root:
            bundle = args.evidence_root / "leech_qkv"
            stage_original_evidence(args.source, args.fixture, bundle)
        else:
            raise QKVAdmissionError("supply --bundle or source+fixture+evidence-root")
        result = verify_bundle(bundle, expected_rocm_root=args.runtime_root)
        report = bundle / "verification.json"
        report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        if args.candidate:
            # Promotion is still blocked until all seven independent core gates pass.
            try:
                from scripts.gfx803_release import load, write, validate_lock
            except ModuleNotFoundError:
                from gfx803_release import load, write, validate_lock
            lock = load(args.lock)
            validate_lock(lock)
            candidate = load(args.candidate)
            if (candidate.get("state") != "candidate"
                    or lock.get("image_digest") is None
                    or candidate.get("image_ref") != lock["image_repository"]+"@"+lock["image_digest"]
                    or candidate.get("store_paths", {}).get("rocm") != str(args.runtime_root)):
                raise QKVAdmissionError("original QKV acceptance requires a real pinned 10.1 candidate")
            candidate.setdefault("provenance", {})["sgemm_shim_loaded_and_correct"] = "verified"
            capabilities = candidate.setdefault("claimed_capabilities", [])
            if "leech_qkv" not in capabilities:
                capabilities.append("leech_qkv")
            relative = report.relative_to(args.evidence_root.resolve())
            candidate.setdefault("evidence", {})["leech_qkv_original"] = {
                "status": "pass", "command": "gfx803_leech_qkv_admission --original-output-verify",
                "log_path": str(relative), "log_sha256": digest(report),
                "source": "rechecked raw original Leech QKV tensor, runtime and profiler trace bytes"}
            write(args.candidate, candidate)
        print(json.dumps({"bundle":str(bundle), "status":result["status"],
                          "training_admitted":False,"release_admitted":False}))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        ap.exit(3, "LEECH QKV BUNDLE NOT ADMITTED: "+str(exc)+"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
