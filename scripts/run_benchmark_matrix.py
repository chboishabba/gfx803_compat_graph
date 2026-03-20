#!/usr/bin/env python3
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark_schema import (
    append_jsonl,
    build_benchmark_record,
    parse_drift_metrics,
    parse_final_json,
)


PROFILE_ENVS = {
    "default": {},
    "direct_only": {
        "MIOPEN_DEBUG_CONV_GEMM": "0",
        "MIOPEN_DEBUG_CONV_DIRECT": "1",
    },
    "gemm_only": {
        "MIOPEN_DEBUG_CONV_DIRECT": "0",
        "MIOPEN_DEBUG_CONV_GEMM": "1",
    },
    "stable_profile": {
        "MIOPEN_DEBUG_CONV_WINOGRAD": "0",
        "MIOPEN_DEBUG_CONV_FFT": "0",
        "MIOPEN_DEBUG_CONV_DET": "1",
        "MIOPEN_DEBUG_DISABLE_FIND_DB": "1",
        "MIOPEN_FIND_ENFORCE": "3",
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
    },
}

COMMON_ENV = {
    "HSA_OVERRIDE_GFX_VERSION": "8.0.3",
    "ROC_ENABLE_PRE_VEGA": "1",
    "PYTORCH_ROCM_ARCH": "gfx803",
    "ROCM_ARCH": "gfx803",
    "TORCH_BLAS_PREFER_HIPBLASLT": "0",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run a benchmark matrix and emit standardized records.")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--python-cmd-json", required=True)
    parser.add_argument("--test-script", default="tests/bug_report_mre.py")
    parser.add_argument("--out-dir", default="out/benchmark")
    parser.add_argument("--stack-id", required=True)
    parser.add_argument("--reference-class", default="candidate")
    parser.add_argument("--runtime-family", required=True)
    parser.add_argument("--runtime-source", required=True)
    parser.add_argument("--workload", default="bug_report_mre")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--profiles", nargs="*", default=["default", "direct_only", "gemm_only", "stable_profile"])
    return parser.parse_args()


def run_one(profile, args, python_cmd, jsonl_path, log_dir):
    env = os.environ.copy()
    env.update(COMMON_ENV)
    env.update(PROFILE_ENVS[profile])

    log_path = log_dir / f"{profile}.log"
    started = time.time()

    with log_path.open("w", encoding="utf-8") as log_handle:
        proc = subprocess.Popen(
            python_cmd + [str(Path(args.repo_root) / args.test_script)],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=args.repo_root,
            env=env,
            text=True,
        )
        returncode = None
        notes = []
        try:
            returncode = proc.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            returncode = None
            notes.append(f"timeout:{args.timeout}s")
        finished = time.time()

    text = log_path.read_text(encoding="utf-8", errors="replace")
    final_json = parse_final_json(text)
    metrics = parse_drift_metrics(text)
    if returncode is not None and returncode < 0:
        notes.append(f"signal:{signal.Signals(-returncode).name}")
    elif returncode == 139:
        notes.append("signal:SIGSEGV")

    record = build_benchmark_record(
        stack_id=args.stack_id,
        reference_class=args.reference_class,
        runtime_family=args.runtime_family,
        workload=args.workload,
        profile=profile,
        runtime_source=args.runtime_source,
        started_at=started,
        finished_at=finished,
        returncode=returncode,
        log_file=log_path,
        final_json=final_json,
        metrics=metrics,
        notes=notes,
    )
    append_jsonl(jsonl_path, record)
    return record


def main():
    args = parse_args()
    python_cmd = json.loads(args.python_cmd_json)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "benchmark-results.jsonl"
    if jsonl_path.exists():
        jsonl_path.unlink()

    all_records = []
    for profile in args.profiles:
        if profile not in PROFILE_ENVS:
            raise SystemExit(f"unknown profile: {profile}")
        print(f"=== Running profile: {profile} ===", flush=True)
        record = run_one(profile, args, python_cmd, jsonl_path, log_dir)
        all_records.append(record)
        print(json.dumps(record, indent=2), flush=True)

    summary_path = out_dir / "benchmark-summary.json"
    summary_path.write_text(json.dumps(all_records, indent=2), encoding="utf-8")
    print(f"Wrote {jsonl_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
