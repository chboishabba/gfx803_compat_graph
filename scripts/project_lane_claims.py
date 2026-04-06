#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lane_contracts import EXAMPLE_DIR, validate_payload


ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
ARTIFACTS_DIR = ROOT / "artifacts"


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)
        fh.write("\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _exists(relpath: str) -> bool:
    return (ROOT / relpath).exists()


def _read_text(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def _contains(relpath: str, needle: str) -> bool:
    path = ROOT / relpath
    if not path.exists():
        return False
    return needle in path.read_text(encoding="utf-8")


def _lane_specs() -> list[dict[str, Any]]:
    status_text = _read_text("status.md")
    plan_text = _read_text("plan.md")
    lane_owner_text = _read_text("docs/LANE_OWNER_TABLE.md")

    return [
        {
            "lane_id": "control-6.4",
            "workload_id": "baseline-runtime-availability-with-whisperx-exclusion",
            "witness_label": "canonical",
            "promotion_status": "promoted",
            "admissibility_status": "admissible",
            "statement": "The extracted ROCm 6.4 host path is the current practical baseline in this repo for torch import, ComfyUI, and general extracted userspace bring-up on this machine.",
            "claim_scope": "baseline runtime availability on this machine for torch import, ComfyUI, and general extracted userspace bring-up",
            "blocker": "WhisperX can use the GPU on this runtime but can still hit KFD/reset instability at an unknown point, so WhisperX host-stable completion is not part of the promoted baseline.",
            "next_action": "Attach one projected smoke observation for the control lane and keep WhisperX in a separate RCA claim family until host-stable completion is demonstrated.",
            "exclusions": [
                "Does not promote WhisperX as a host-stable GPU workflow",
                "Does not promote Ollama host stability",
                "Does not promote Leech correctness",
                "Does not imply all GPU workloads are trustworthy"
            ],
            "command": ["projector", "control-6.4"],
            "artifact_refs": ["lib-compat/", "docker-venv/"],
            "metrics": {
                "baseline_lib_compat_present": _exists("lib-compat"),
                "baseline_docker_venv_present": _exists("docker-venv"),
                "status_control_lane_preserved": "Control lane: preserved and untouched" in status_text,
                "docs_user_guide_present": _exists("docs/USER_GUIDE.md"),
                "whisperx_not_host_stable": _contains("README.md", "KFD / reset crash at an as-yet unknown point") or _contains("docs/USER_GUIDE.md", "KFD / reset crash at an unknown point")
            },
            "proof_refs": [
                "status.md",
                "architecture.md",
                "docs/LANE_OWNER_TABLE.md",
                "docs/ADMISSIBILITY_CONE_TREE.md"
            ],
            "verdicts": {
                "import_ok": True,
                "gpu_visible": True
            }
        },
        {
            "lane_id": "upgrade-oldabi",
            "workload_id": "torch-oldabi-smoke-gate",
            "witness_label": "experimental",
            "promotion_status": "candidate",
            "admissibility_status": "partially_admissible",
            "statement": "The old-ABI upgrade lane is the main promotion candidate toward a newer reproducible stack, but it is not yet promoted because GPU visibility and framework rebuild gates remain open.",
            "claim_scope": "old-ABI upgrade lane as the main promotion candidate for a newer reproducible stack",
            "blocker": "GPU visibility and framework rebuild gates remain open for the old-ABI lane.",
            "next_action": "Capture one torch smoke observation proving old-ABI runtime purity and recording whether torch both imports and sees the GPU.",
            "exclusions": [
                "Does not claim a promoted usable newer stack yet",
                "Does not claim end-to-end framework rebuild success"
            ],
            "command": ["scripts/smoke-pytorch-oldabi-import.sh"],
            "artifact_refs": [
                "artifacts/rocm64-upgrade-oldabi/",
                "artifacts/rocm64-oldabi-sdk/"
            ],
            "metrics": {
                "oldabi_lane_present": _exists("artifacts/rocm64-upgrade-oldabi"),
                "oldabi_sdk_present": _exists("artifacts/rocm64-oldabi-sdk"),
                "status_upgrade_lane_materialized": "Upgrade lane: materialized" in status_text,
                "status_sdk_extracted": "SDK root: extracted" in status_text,
                "plan_mentions_torch_smoke": "Rerun the torch smoke" in plan_text
            },
            "proof_refs": [
                "status.md",
                "plan.md",
                "architecture.md",
                "docs/LANE_OWNER_TABLE.md"
            ],
            "verdicts": {
                "import_ok": True,
                "gpu_visible": False
            }
        },
        {
            "lane_id": "diag-5.7",
            "workload_id": "leech-correctness-diagnostic",
            "witness_label": "validation",
            "promotion_status": "candidate",
            "admissibility_status": "diagnostic_only",
            "statement": "The extracted ROCm 5.7 lane is admissible for comparison and upstream debugging, but not for trustworthy inference output on this machine.",
            "claim_scope": "extracted ROCm 5.7 lane for Leech correctness investigation on this machine",
            "blocker": "Leech output remains nondeterministic and not trustworthy under the current 5.7 runtime.",
            "next_action": "Promote one diagnostic claim that ties the 5.7 lane to layout-path witnesses rather than user-facing inference guidance.",
            "exclusions": [
                "Does not claim trustworthy GPU inference",
                "Does not claim a user-facing recommended runtime"
            ],
            "command": ["scripts/host-rocm57-python.sh", "scripts/debug-leech-attn-layout-repeat.py"],
            "artifact_refs": ["artifacts/rocm57/"],
            "metrics": {
                "rocm57_present": _exists("artifacts/rocm57"),
                "user_guide_mentions_untrustworthy_57": _contains("docs/USER_GUIDE.md", "the extracted `5.7` path is useful for comparison and diagnostics, but it is also not yet trustworthy for inference output"),
                "user_guide_mentions_layout_instability": _contains("docs/USER_GUIDE.md", "transpose(...).reshape(B, T, -1)")
            },
            "trace_refs": [
                "docs/USER_GUIDE.md",
                "docs/LANE_OWNER_TABLE.md"
            ],
            "verdicts": {
                "import_ok": True,
                "gpu_visible": True,
                "numerically_stable": False,
                "same_process_repeatable": False
            }
        },
        {
            "lane_id": "diag-latest-hybrid",
            "workload_id": "latest-hsa-abi-diagnostic",
            "witness_label": "negative_control",
            "promotion_status": "candidate",
            "admissibility_status": "diagnostic_only",
            "statement": "The pure latest-class and HSA-hybrid lanes are useful for ABI and device-gating diagnosis, but are not promoted usable runtime lanes on this machine.",
            "claim_scope": "pure latest-class and HSA-hybrid ABI seam investigation on this machine",
            "blocker": "The HIP/HSA ABI seam still blocks a promoted usable stack even when rocminfo can be restored on hybrid variants.",
            "next_action": "Capture one explicit diagnostic claim that separates rocminfo restoration from torch GPU usability across the latest and hybrid variants.",
            "exclusions": [
                "Does not claim a promoted newer runtime",
                "Does not claim torch GPU usability on Polaris under the latest-class seam"
            ],
            "command": ["scripts/create-rocm-latest-hsa-hybrid-lanes.sh", "scripts/probe-rocm-hybrid-runtime-lanes.sh"],
            "artifact_refs": [
                "artifacts/rocm-latest/",
                "artifacts/rocm-runtime-hybrids/"
            ],
            "metrics": {
                "rocm_latest_present": _exists("artifacts/rocm-latest"),
                "hybrid_lane_present": _exists("artifacts/rocm-runtime-hybrids"),
                "readme_mentions_hybrid_probe": _contains("README.md", "HSA-hybrid latest-class lanes are now reproducible probe artifacts"),
                "user_guide_mentions_cuda_false": _contains("docs/USER_GUIDE.md", "torch.cuda.is_available() == False")
            },
            "trace_refs": [
                "README.md",
                "docs/USER_GUIDE.md",
                "docs/LANE_OWNER_TABLE.md"
            ],
            "verdicts": {
                "import_ok": True,
                "gpu_visible": False
            }
        },
        {
            "lane_id": "ollama-ref",
            "workload_id": "extracted-ollama-host-bundle",
            "witness_label": "experimental",
            "promotion_status": "candidate",
            "admissibility_status": "investigation_only",
            "statement": "The extracted Ollama reference bundle is a provenance-bearing host-port investigation surface, but it is not a promoted safe host daily-driver path on this machine.",
            "claim_scope": "extracted host-port of the Robert 6.4.3_0.11.5 Ollama lineage on this machine",
            "blocker": "Host reset and system instability remain unresolved for the extracted host bundle.",
            "next_action": "Capture one timestamp-aligned reproduction packet after the current host-port fixes to determine whether the reset sequence still reproduces.",
            "exclusions": [
                "Does not supersede the Robert container lineage",
                "Does not promote a safe host GPU Ollama recommendation"
            ],
            "command": ["scripts/run-ollama-reference-host.sh", "scripts/correlate-amdgpu-reset-window.sh"],
            "artifact_refs": ["artifacts/ollama_reference/"],
            "metrics": {
                "ollama_reference_present": _exists("artifacts/ollama_reference"),
                "incident_doc_present": _exists("docs/INCIDENT_2026-03-20_OLLAMA_MISTRAL_KFD_RESET.md"),
                "wayland_incident_present": _exists("docs/INCIDENT_2026-03-25_WAYLAND_GFX_TIMEOUT_RESET.md"),
                "lane_owner_mentions_unresolved_instability": "Host reset/system instability remains unresolved" in lane_owner_text
            },
            "trace_refs": [
                "docs/INCIDENT_2026-03-20_OLLAMA_MISTRAL_KFD_RESET.md",
                "docs/INCIDENT_2026-03-25_WAYLAND_GFX_TIMEOUT_RESET.md"
            ],
            "verdicts": {
                "import_ok": True,
                "gpu_visible": True,
                "crash_free": False
            }
        }
    ]


def _build_observation(spec: dict[str, Any]) -> dict[str, Any]:
    stamp = _now()
    return {
        "observation_id": f"obs-{spec['lane_id']}-{stamp[:10]}",
        "lane_id": spec["lane_id"],
        "workload_id": spec["workload_id"],
        "captured_at": stamp,
        "command": spec["command"],
        "environment": {
            "host_id": "cachy-lambo",
            "gpu_arch": "gfx803",
            "runtime_lane": spec["lane_id"],
            "artifact_refs": spec["artifact_refs"],
        },
        "metrics": spec["metrics"],
        **({"trace_refs": spec["trace_refs"]} if spec.get("trace_refs") else {}),
        **({"proof_refs": spec["proof_refs"]} if spec.get("proof_refs") else {}),
        "related_artifact_refs": spec["artifact_refs"],
        "verdicts": spec["verdicts"],
    }


def _build_claim(spec: dict[str, Any], observation_id: str) -> dict[str, Any]:
    stamp = _now()[:10]
    return {
        "claim_id": f"claim-{spec['lane_id']}-{stamp}",
        "lane_id": spec["lane_id"],
        "claim_scope": spec["claim_scope"],
        "witness_label": spec["witness_label"],
        "promotion_status": spec["promotion_status"],
        "statement": spec["statement"],
        "admissibility_status": spec["admissibility_status"],
        "observation_refs": [observation_id],
        "blocker": spec["blocker"],
        "next_action": spec["next_action"],
        "exclusions": spec["exclusions"],
    }


def project_repo_state(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    index: dict[str, Any] = {"observations": [], "claims": []}

    for spec in _lane_specs():
        observation = _build_observation(spec)
        validate_payload(observation, "execution_observation")
        observation_name = f"{spec['lane_id']}.execution_observation.json"
        _dump(out_dir / observation_name, observation)

        claim = _build_claim(spec, observation["observation_id"])
        validate_payload(claim, "compatibility_claim")
        claim_name = f"{spec['lane_id']}.compatibility_claim.json"
        _dump(out_dir / claim_name, claim)

        index["observations"].append(
            {
                "observation_id": observation["observation_id"],
                "lane_id": observation["lane_id"],
                "workload_id": observation["workload_id"],
            }
        )
        index["claims"].append(
            {
                "claim_id": claim["claim_id"],
                "lane_id": claim["lane_id"],
                "promotion_status": claim["promotion_status"],
                "witness_label": claim["witness_label"],
                "admissibility_status": claim["admissibility_status"],
            }
        )

    _dump(out_dir / "lane_claim_index.json", index)


def project_examples(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    observation_ids: set[str] = set()
    for obs_path in sorted(EXAMPLE_DIR.glob("*.execution_observation.json")):
        payload = _load(obs_path)
        validate_payload(payload, "execution_observation")
        observation_ids.add(payload["observation_id"])
        _dump(out_dir / obs_path.name, payload)

    index: dict[str, Any] = {"observations": [], "claims": []}

    for claim_path in sorted(EXAMPLE_DIR.glob("*.compatibility_claim.json")):
        payload = _load(claim_path)
        validate_payload(payload, "compatibility_claim")
        for ref in payload["observation_refs"]:
            if ref not in observation_ids:
                raise ValueError(f"{claim_path.name} references unknown observation_id: {ref}")
        _dump(out_dir / claim_path.name, payload)
        index["claims"].append(
            {
                "claim_id": payload["claim_id"],
                "lane_id": payload["lane_id"],
                "promotion_status": payload["promotion_status"],
                "witness_label": payload["witness_label"],
                "admissibility_status": payload.get("admissibility_status"),
            }
        )

    for obs_path in sorted(EXAMPLE_DIR.glob("*.execution_observation.json")):
        payload = _load(obs_path)
        index["observations"].append(
            {
                "observation_id": payload["observation_id"],
                "lane_id": payload["lane_id"],
                "workload_id": payload["workload_id"],
            }
        )

    _dump(out_dir / "lane_claim_index.json", index)


def main() -> int:
    examples_out = ROOT / "out" / "lane_claims_examples"
    project_examples(examples_out)
    repo_state_out = ROOT / "out" / "lane_claims"
    project_repo_state(repo_state_out)
    print(f"projected example lane claims to {examples_out}")
    print(f"projected repo-state lane claims to {repo_state_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
