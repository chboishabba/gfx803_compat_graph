#!/usr/bin/env python3
import argparse
import ctypes
import inspect
import json
import os
import sys
import time
import traceback
from pathlib import Path


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def detect_torch():
    try:
        import torch  # type: ignore
    except Exception:
        return None
    return torch


TORCH = detect_torch()
ROCTX = None
ROCTX_LIB_NAME = None


def detect_roctx():
    candidates = [
        "librocprofiler-sdk-roctx.so.1",
        "librocprofiler-sdk-roctx.so",
        "libroctx64.so",
        "libroctx64.so.4",
    ]
    for name in candidates:
        try:
            lib = ctypes.CDLL(name)
            lib.roctxMarkA.argtypes = [ctypes.c_char_p]
            lib.roctxMarkA.restype = None
            lib.roctxRangePushA.argtypes = [ctypes.c_char_p]
            lib.roctxRangePushA.restype = ctypes.c_int
            lib.roctxRangePop.argtypes = []
            lib.roctxRangePop.restype = ctypes.c_int
            if hasattr(lib, "roctxProfilerResume") and hasattr(lib, "roctxProfilerPause"):
                lib.roctxProfilerResume.argtypes = [ctypes.c_uint32]
                lib.roctxProfilerResume.restype = None
                lib.roctxProfilerPause.argtypes = [ctypes.c_uint32]
                lib.roctxProfilerPause.restype = None
            return lib, name
        except Exception:
            continue
    return None, None


ROCTX, ROCTX_LIB_NAME = detect_roctx()
COMPUTE_STAGES = {"transcribe", "align", "diarize"}


def cuda_sync() -> None:
    if TORCH is None:
        return
    if not TORCH.cuda.is_available():
        return
    try:
        TORCH.cuda.synchronize()
    except Exception:
        pass


def gpu_snapshot() -> dict:
    snap = {
        "torch_present": TORCH is not None,
        "cuda_available": False,
    }
    if TORCH is None:
        return snap
    try:
        snap["torch_version"] = TORCH.__version__
        snap["cuda_available"] = bool(TORCH.cuda.is_available())
        snap["device_count"] = int(TORCH.cuda.device_count())
        if TORCH.cuda.is_available():
            idx = TORCH.cuda.current_device()
            free_b, total_b = TORCH.cuda.mem_get_info()
            snap.update(
                {
                    "device_index": idx,
                    "device_name": TORCH.cuda.get_device_name(idx),
                    "mem_free_bytes": int(free_b),
                    "mem_total_bytes": int(total_b),
                    "mem_allocated_bytes": int(TORCH.cuda.memory_allocated(idx)),
                    "mem_reserved_bytes": int(TORCH.cuda.memory_reserved(idx)),
                }
            )
    except Exception as exc:
        snap["snapshot_error"] = repr(exc)
    return snap


def write_event(outdir: Path, kind: str, **data) -> None:
    record = {
        "ts": now_iso(),
        "epoch_s": time.time(),
        "kind": kind,
        **data,
    }
    with (outdir / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    print(json.dumps(record, sort_keys=True), flush=True)


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_optional_json_arg(name: str, raw: str):
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{name} must decode to a JSON object")
    return parsed


def callable_signature_info(fn) -> tuple[str, set[str], bool]:
    try:
        sig = inspect.signature(fn)
    except Exception:
        return "<unknown>", set(), True

    accepted = set()
    has_var_kwargs = False
    for param in sig.parameters.values():
        if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
            accepted.add(param.name)
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            has_var_kwargs = True
    return str(sig), accepted, has_var_kwargs


def select_supported_kwargs(fn, kwargs: dict) -> tuple[dict, dict, str]:
    signature_text, accepted, has_var_kwargs = callable_signature_info(fn)
    if has_var_kwargs:
        return dict(kwargs), {}, signature_text

    supported = {}
    ignored = {}
    for key, value in kwargs.items():
        if key in accepted:
            supported[key] = value
        else:
            ignored[key] = value
    return supported, ignored, signature_text


def roctx_mark(name: str) -> bool:
    if ROCTX is None:
        return False
    try:
        ROCTX.roctxMarkA(name.encode("utf-8"))
        return True
    except Exception:
        return False


def roctx_push(name: str) -> bool:
    if ROCTX is None:
        return False
    try:
        ROCTX.roctxRangePushA(name.encode("utf-8"))
        return True
    except Exception:
        return False


def roctx_pop(enabled: bool) -> None:
    if not enabled or ROCTX is None:
        return
    try:
        ROCTX.roctxRangePop()
    except Exception:
        pass


def roctx_profiler_resume() -> bool:
    if ROCTX is None or not hasattr(ROCTX, "roctxProfilerResume"):
        return False
    try:
        ROCTX.roctxProfilerResume(0)
        return True
    except Exception:
        return False


def roctx_profiler_pause(enabled: bool) -> None:
    if not enabled or ROCTX is None or not hasattr(ROCTX, "roctxProfilerPause"):
        return
    try:
        ROCTX.roctxProfilerPause(0)
    except Exception:
        pass


def resolve_profile_stage_policy(selected_stage: str, policy: str) -> str:
    if policy:
        return policy
    if selected_stage:
        return "exact"
    return "none"


def begin_profiler_region(outdir: Path, stage_name: str, policy: str, profiler_state: dict) -> tuple[bool, bool]:
    if policy == "none":
        return False, False

    if policy == "exact":
        selected_stage = profiler_state["selected_stage"]
        if selected_stage != stage_name or profiler_state["active"]:
            return False, False
        if not roctx_profiler_resume():
            return False, False
        profiler_state["active"] = True
        profiler_state["started_stage"] = stage_name
        write_event(outdir, "profiler_region_start", stage=stage_name, policy=policy)
        return True, True

    if policy == "first_compute":
        if profiler_state["latched"] or stage_name not in COMPUTE_STAGES:
            return False, False
        if not roctx_profiler_resume():
            return False, False
        profiler_state["active"] = True
        profiler_state["latched"] = True
        profiler_state["started_stage"] = stage_name
        write_event(outdir, "profiler_region_start", stage=stage_name, policy=policy)
        return True, False

    return False, False


def end_profiler_region(outdir: Path, stage_name: str, policy: str, profiler_state: dict, pause_now: bool) -> None:
    if not profiler_state["active"]:
        return
    if pause_now:
        write_event(outdir, "profiler_region_end", stage=stage_name, policy=policy)
        roctx_profiler_pause(True)
        profiler_state["active"] = False


def finalize_profiler_region(outdir: Path, final_stage: str, policy: str, profiler_state: dict) -> None:
    if not profiler_state["active"]:
        return
    write_event(
        outdir,
        "profiler_region_end",
        stage=final_stage,
        policy=policy,
        started_stage=profiler_state.get("started_stage"),
    )
    roctx_profiler_pause(True)
    profiler_state["active"] = False


def stage(name: str, outdir: Path, fn, profile_selected_stage: str, profile_stage_policy: str, profiler_state: dict):
    start = time.time()
    write_event(outdir, "stage_start", stage=name, gpu=gpu_snapshot())
    roctx_mark(f"stage_start:{name}")
    roctx_enabled = roctx_push(f"whisperx:{name}")
    profiling_enabled, pause_after_stage = begin_profiler_region(
        outdir, name, profile_stage_policy, profiler_state
    )
    try:
        result = fn()
        cuda_sync()
        elapsed = time.time() - start
        write_event(outdir, "stage_end", stage=name, elapsed_s=elapsed, gpu=gpu_snapshot())
        roctx_mark(f"stage_end:{name}")
        return result
    except Exception as exc:
        elapsed = time.time() - start
        write_event(
            outdir,
            "stage_error",
            stage=name,
            elapsed_s=elapsed,
            error=repr(exc),
            traceback=traceback.format_exc(),
            gpu=gpu_snapshot(),
        )
        roctx_mark(f"stage_error:{name}")
        raise
    finally:
        end_profiler_region(outdir, name, profile_stage_policy, profiler_state, pause_after_stage)
        roctx_pop(roctx_enabled)


def main() -> int:
    parser = argparse.ArgumentParser(description="Instrumented WhisperX harness for ROCm RCA.")
    parser.add_argument("--audio", required=True, help="Input audio file")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument("--model", default=os.environ.get("WHISPERX_MODEL", "small"))
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("WHISPERX_BATCH_SIZE", "4")))
    parser.add_argument("--compute-type", default=os.environ.get("WHISPERX_COMPUTE_TYPE", "float16"))
    parser.add_argument(
        "--stage",
        choices=["load", "transcribe", "align", "diarize", "full"],
        default="full",
        help="Maximum stage to execute",
    )
    parser.add_argument("--language", default=os.environ.get("WHISPERX_LANGUAGE", ""))
    parser.add_argument("--device", default=os.environ.get("WHISPERX_DEVICE", "cuda"))
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    parser.add_argument("--diarize", action="store_true", help="Enable diarization in full mode")
    parser.add_argument("--sleep-between-stages", type=float, default=float(os.environ.get("WHISPERX_SLEEP_BETWEEN_STAGES", "0")))
    parser.add_argument(
        "--transcribe-chunk-size",
        type=int,
        default=int(os.environ.get("WHISPERX_TRANSCRIBE_CHUNK_SIZE", "0")),
        help="Optional transcribe chunk/window size. Passed only if supported by installed whisperx.",
    )
    parser.add_argument(
        "--transcribe-num-workers",
        type=int,
        default=int(os.environ.get("WHISPERX_TRANSCRIBE_NUM_WORKERS", "-1")),
        help="Optional transcribe worker count. Passed only if supported by installed whisperx.",
    )
    parser.add_argument(
        "--load-model-threads",
        type=int,
        default=int(os.environ.get("WHISPERX_LOAD_MODEL_THREADS", "0")),
        help="Optional whisperx.load_model threads value. Passed only if supported.",
    )
    parser.add_argument(
        "--vad-method",
        default=os.environ.get("WHISPERX_VAD_METHOD", ""),
        help="Optional whisperx.load_model vad_method.",
    )
    parser.add_argument(
        "--asr-options-json",
        default=os.environ.get("WHISPERX_ASR_OPTIONS_JSON", ""),
        help="Optional JSON object passed as asr_options to whisperx.load_model.",
    )
    parser.add_argument(
        "--vad-options-json",
        default=os.environ.get("WHISPERX_VAD_OPTIONS_JSON", ""),
        help="Optional JSON object passed as vad_options to whisperx.load_model.",
    )
    parser.add_argument(
        "--load-model-options-json",
        default=os.environ.get("WHISPERX_LOAD_MODEL_OPTIONS_JSON", ""),
        help="Optional JSON object merged into whisperx.load_model kwargs.",
    )
    parser.add_argument(
        "--transcribe-options-json",
        default=os.environ.get("WHISPERX_TRANSCRIBE_OPTIONS_JSON", ""),
        help="Optional JSON object merged into model.transcribe kwargs.",
    )
    parser.add_argument(
        "--profile-selected-stage",
        default=os.environ.get("WHISPERX_PROFILE_SELECTED_STAGE", ""),
        choices=["", "load_model", "load_audio", "transcribe", "align", "diarize"],
        help="If set, call roctxProfilerResume/Pause only for this stage",
    )
    parser.add_argument(
        "--profile-stage-policy",
        default=os.environ.get("WHISPERX_PROFILE_STAGE_POLICY", ""),
        choices=["", "exact", "first_compute"],
        help="Profiling gate policy: exact stage or first compute stage onward",
    )
    args = parser.parse_args()
    resolved_profile_stage_policy = resolve_profile_stage_policy(
        args.profile_selected_stage, args.profile_stage_policy
    )
    profiler_state = {
        "active": False,
        "latched": False,
        "selected_stage": args.profile_selected_stage,
        "started_stage": None,
    }

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    parsed_asr_options = parse_optional_json_arg("--asr-options-json", args.asr_options_json)
    parsed_vad_options = parse_optional_json_arg("--vad-options-json", args.vad_options_json)
    parsed_load_model_options = parse_optional_json_arg("--load-model-options-json", args.load_model_options_json)
    parsed_transcribe_options = parse_optional_json_arg("--transcribe-options-json", args.transcribe_options_json)

    env_snapshot = {
        key: os.environ.get(key)
        for key in [
            "HSA_OVERRIDE_GFX_VERSION",
            "ROC_ENABLE_PRE_VEGA",
            "ROCM_ARCH",
            "PYTORCH_ROCM_ARCH",
            "HIP_LAUNCH_BLOCKING",
            "AMD_LOG_LEVEL",
            "ROCBLAS_LAYER",
            "MIOPEN_DEBUG_CONV_WINOGRAD",
            "MIOPEN_DEBUG_CONV_DIRECT",
            "MIOPEN_DEBUG_CONV_GEMM",
            "MIOPEN_FIND_ENFORCE",
            "JOBLIB_MULTIPROCESSING",
            "TOKENIZERS_PARALLELISM",
        ]
    }
    run_config = {
        "argv": sys.argv,
        "cwd": os.getcwd(),
        "audio": os.path.abspath(args.audio),
        "model": args.model,
        "batch_size": args.batch_size,
        "compute_type": args.compute_type,
        "stage": args.stage,
        "language": args.language,
        "device": args.device,
        "diarize": args.diarize,
        "sleep_between_stages": args.sleep_between_stages,
        "env": env_snapshot,
        "gpu": gpu_snapshot(),
        "roctx_available": ROCTX is not None,
        "roctx_library": ROCTX_LIB_NAME,
        "profile_selected_stage": args.profile_selected_stage,
        "profile_stage_policy": resolved_profile_stage_policy,
        "pressure_controls_requested": {
            "transcribe_chunk_size": args.transcribe_chunk_size if args.transcribe_chunk_size > 0 else None,
            "transcribe_num_workers": args.transcribe_num_workers if args.transcribe_num_workers >= 0 else None,
            "load_model_threads": args.load_model_threads if args.load_model_threads > 0 else None,
            "vad_method": args.vad_method or None,
            "asr_options": parsed_asr_options,
            "vad_options": parsed_vad_options,
            "load_model_options": parsed_load_model_options,
            "transcribe_options": parsed_transcribe_options,
        },
    }
    write_json(outdir / "run-config.json", run_config)
    write_event(
        outdir,
        "run_start",
        args=vars(args),
        gpu=gpu_snapshot(),
        roctx_available=ROCTX is not None,
        roctx_library=ROCTX_LIB_NAME,
        profile_stage_policy=resolved_profile_stage_policy,
    )
    roctx_mark("run_start")

    try:
        import whisperx  # type: ignore
    except Exception as exc:
        write_event(outdir, "import_error", module="whisperx", error=repr(exc), traceback=traceback.format_exc())
        raise

    asr_module = None
    try:
        asr_module = whisperx._lazy_import("asr")
    except Exception:
        try:
            import whisperx.asr as asr_module  # type: ignore
        except Exception:
            asr_module = None

    load_model_callable = getattr(asr_module, "load_model", whisperx.load_model) if asr_module is not None else whisperx.load_model

    load_model_extra_kwargs = {}
    if args.load_model_threads > 0:
        load_model_extra_kwargs["threads"] = args.load_model_threads
    if args.vad_method:
        load_model_extra_kwargs["vad_method"] = args.vad_method
    if parsed_asr_options is not None:
        load_model_extra_kwargs["asr_options"] = parsed_asr_options
    if parsed_vad_options is not None:
        load_model_extra_kwargs["vad_options"] = parsed_vad_options
    if parsed_load_model_options is not None:
        load_model_extra_kwargs.update(parsed_load_model_options)

    load_model_applied_kwargs, load_model_ignored_kwargs, load_model_signature = select_supported_kwargs(
        load_model_callable, load_model_extra_kwargs
    )

    transcribe_extra_kwargs = {}
    if args.transcribe_chunk_size > 0:
        transcribe_extra_kwargs["chunk_size"] = args.transcribe_chunk_size
    if args.transcribe_num_workers >= 0:
        transcribe_extra_kwargs["num_workers"] = args.transcribe_num_workers
    if parsed_transcribe_options is not None:
        transcribe_extra_kwargs.update(parsed_transcribe_options)

    model = None
    audio = None
    transcription = None
    aligned = None
    transcribe_signature = "<unknown>"
    transcribe_applied_kwargs = {}
    transcribe_ignored_kwargs = {}

    def maybe_pause():
        if args.sleep_between_stages > 0:
            time.sleep(args.sleep_between_stages)

    def do_load():
        return whisperx.load_model(
            args.model,
            args.device,
            compute_type=args.compute_type,
            language=args.language or None,
            **load_model_applied_kwargs,
        )

    def do_audio_load():
        return whisperx.load_audio(args.audio)

    def do_transcribe():
        return model.transcribe(
            audio,
            batch_size=args.batch_size,
            language=args.language or None,
            **transcribe_applied_kwargs,
        )

    def do_align():
        language = transcription.get("language") or args.language
        align_model, metadata = whisperx.load_align_model(language_code=language, device=args.device)
        try:
            return whisperx.align(
                transcription["segments"],
                align_model,
                metadata,
                audio,
                args.device,
                return_char_alignments=False,
            )
        finally:
            del align_model

    def do_diarize():
        diarize_model = whisperx.DiarizationPipeline(use_auth_token=args.hf_token or None, device=args.device)
        diarize_segments = diarize_model(args.audio)
        return whisperx.assign_word_speakers(diarize_segments, aligned or transcription)

    final_stage = ""
    try:
        model = stage("load_model", outdir, do_load, args.profile_selected_stage, resolved_profile_stage_policy, profiler_state)
        transcribe_applied_kwargs, transcribe_ignored_kwargs, transcribe_signature = select_supported_kwargs(
            model.transcribe, transcribe_extra_kwargs
        )
        run_config["pressure_controls_resolved"] = {
            "load_model_signature": load_model_signature,
            "load_model_applied_kwargs": load_model_applied_kwargs,
            "load_model_ignored_kwargs": load_model_ignored_kwargs,
            "transcribe_signature": transcribe_signature,
            "transcribe_applied_kwargs": transcribe_applied_kwargs,
            "transcribe_ignored_kwargs": transcribe_ignored_kwargs,
        }
        write_json(outdir / "run-config.json", run_config)
        write_event(
            outdir,
            "pressure_controls_resolved",
            load_model_signature=load_model_signature,
            load_model_applied_kwargs=load_model_applied_kwargs,
            load_model_ignored_kwargs=load_model_ignored_kwargs,
            transcribe_signature=transcribe_signature,
            transcribe_applied_kwargs=transcribe_applied_kwargs,
            transcribe_ignored_kwargs=transcribe_ignored_kwargs,
        )
        if args.stage == "load":
            final_stage = "load_model"
            roctx_mark("run_end:load_model")
            write_event(outdir, "run_end", status="ok", final_stage="load_model")
            return 0

        maybe_pause()
        audio = stage("load_audio", outdir, do_audio_load, args.profile_selected_stage, resolved_profile_stage_policy, profiler_state)
        maybe_pause()
        transcription = stage("transcribe", outdir, do_transcribe, args.profile_selected_stage, resolved_profile_stage_policy, profiler_state)
        write_json(outdir / "transcription.json", transcription)
        if args.stage == "transcribe":
            final_stage = "transcribe"
            roctx_mark("run_end:transcribe")
            write_event(outdir, "run_end", status="ok", final_stage="transcribe")
            return 0

        maybe_pause()
        aligned = stage("align", outdir, do_align, args.profile_selected_stage, resolved_profile_stage_policy, profiler_state)
        write_json(outdir / "aligned.json", aligned)
        if args.stage == "align":
            final_stage = "align"
            roctx_mark("run_end:align")
            write_event(outdir, "run_end", status="ok", final_stage="align")
            return 0

        if args.stage == "diarize" or args.diarize:
            maybe_pause()
            diarized = stage("diarize", outdir, do_diarize, args.profile_selected_stage, resolved_profile_stage_policy, profiler_state)
            write_json(outdir / "diarized.json", diarized)
            final_stage = "diarize"
            roctx_mark("run_end:diarize")
            write_event(outdir, "run_end", status="ok", final_stage="diarize")
            return 0

        final_stage = "align"
        roctx_mark("run_end:align")
        write_event(outdir, "run_end", status="ok", final_stage="align")
        return 0
    finally:
        finalize_profiler_region(outdir, final_stage or "aborted", resolved_profile_stage_policy, profiler_state)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        raise
