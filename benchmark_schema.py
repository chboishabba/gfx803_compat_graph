import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

SCHEMA_VERSION = "0.1.0"
STATUS_ORDER = {
    "pass": 4,
    "partial": 3,
    "fail": 2,
    "hang": 1,
    "crash": 0,
}


def _run_text(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, timeout=5).strip()
    except Exception:
        return None


def detect_system_info():
    gpu_name = None
    if shutil.which("rocminfo"):
        out = _run_text(["bash", "-lc", r"rocminfo 2>/dev/null | grep -m1 -E 'Name:|Marketing Name:' | sed 's/^[[:space:]]*//'"])
        if out:
            gpu_name = out

    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "kernel": platform.release(),
        "python_version": platform.python_version(),
        "gpu_name": gpu_name,
        "arch": platform.machine(),
    }


def collect_runtime_info():
    keys = [
        "HSA_OVERRIDE_GFX_VERSION",
        "ROC_ENABLE_PRE_VEGA",
        "PYTORCH_ROCM_ARCH",
        "ROCM_ARCH",
        "TORCH_BLAS_PREFER_HIPBLASLT",
        "MIOPEN_DEBUG_CONV_DIRECT",
        "MIOPEN_DEBUG_CONV_GEMM",
        "MIOPEN_DEBUG_CONV_WINOGRAD",
        "MIOPEN_DEBUG_CONV_FFT",
        "MIOPEN_DEBUG_CONV_DET",
        "MIOPEN_DEBUG_DISABLE_FIND_DB",
        "MIOPEN_FIND_ENFORCE",
        "CUBLAS_WORKSPACE_CONFIG",
        "ROCBLAS_TENSILE_LIBPATH",
        "MIOPEN_SYSTEM_DB_PATH",
    ]
    return {key: os.environ.get(key) for key in keys if os.environ.get(key) is not None}


def parse_final_json(text):
    for line in reversed(text.splitlines()):
        if line.startswith("FINAL_JSON="):
            try:
                return json.loads(line.split("=", 1)[1])
            except json.JSONDecodeError:
                return None
    return None


def parse_drift_metrics(text):
    drifts = [float(x) for x in re.findall(r"DRIFT\s+([0-9.eE+-]+)", text)]
    first_drift_iter = None
    for match in re.finditer(r"ITER\s+(\d+):\s+DRIFT\s+([0-9.eE+-]+)", text):
        first_drift_iter = int(match.group(1))
        break
    return {
        "drift_count": len(drifts),
        "max_drift": max(drifts) if drifts else 0.0,
        "min_drift": min(drifts) if drifts else 0.0,
        "mean_drift": (sum(drifts) / len(drifts)) if drifts else 0.0,
        "first_drift_iter": first_drift_iter,
    }


def classify_status(returncode, metrics):
    if returncode is None:
        return "hang"
    if returncode < 0 or returncode == 139:
        return "crash"
    if returncode != 0:
        return "fail"
    if metrics["drift_count"] == 0 or metrics["max_drift"] <= 1e-6:
        return "pass"
    return "partial"


def record_id(stack_id, workload, profile, started_at):
    raw = f"{stack_id}:{workload}:{profile}:{started_at}"
    suffix = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"{stack_id}__{workload}__{profile}__{suffix}"


def build_benchmark_record(
    *,
    stack_id,
    reference_class,
    runtime_family,
    workload,
    profile,
    runtime_source,
    started_at,
    finished_at,
    returncode,
    log_file,
    final_json,
    metrics,
    notes=None,
    extra_system=None,
):
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id(stack_id, workload, profile, started_at),
        "stack_id": stack_id,
        "reference_class": reference_class,
        "runtime_family": runtime_family,
        "runtime_source": runtime_source,
        "workload": workload,
        "profile": profile,
        "status": classify_status(returncode, metrics),
        "status_score": STATUS_ORDER[classify_status(returncode, metrics)],
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_s": round(finished_at - started_at, 3),
        "returncode": returncode,
        "system": detect_system_info(),
        "runtime": collect_runtime_info(),
        "metrics": metrics,
        "artifacts": {
            "log_file": str(log_file),
        },
        "notes": notes or [],
    }
    if extra_system:
        record["system"].update(extra_system)
    if final_json:
        record["probe"] = final_json
        if isinstance(final_json, dict):
            device_name = final_json.get("device_name")
            if device_name and not record["system"].get("gpu_name"):
                record["system"]["gpu_name"] = device_name
    return record


def append_jsonl(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
