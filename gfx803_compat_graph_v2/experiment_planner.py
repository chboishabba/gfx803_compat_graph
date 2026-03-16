from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import networkx as nx

from seed_graph import build_seed_graph


DEFAULT_EXPERIMENTS = {
    "probe:T1_runtime_sanity": {
        "label": "T1 runtime sanity",
        "targets": ["runtime:hip", "driver:amdgpu_kfd"],
        "resolves": [],
        "cost": 1,
    },
    "probe:T3_lds_correctness": {
        "label": "T3 LDS correctness",
        "targets": ["component:lds"],
        "resolves": [],
        "cost": 2,
    },
    "probe:T6_wave_sched": {
        "label": "T6 wavefront scheduling / occupancy",
        "targets": ["component:wavefront_sched"],
        "resolves": ["unk:best_gemm_tiles"],
        "cost": 2,
    },
    "probe:T7_raw_gemm_correctness": {
        "label": "T7 raw GEMM correctness",
        "targets": ["component:gemm_tiles", "lib:rocblas"],
        "resolves": ["unk:best_gemm_tiles"],
        "cost": 3,
    },
    "probe:T8_gemm_tile_sweep": {
        "label": "T8 GEMM tile sweep",
        "targets": ["component:gemm_tiles"],
        "resolves": ["unk:best_gemm_tiles"],
        "cost": 4,
    },
    "probe:T9_raw_conv": {
        "label": "T9 raw HIP conv",
        "targets": ["component:conv_path"],
        "resolves": ["unk:first_bad_layer", "unk:precision_matrix"],
        "cost": 4,
    },
    "probe:T10_rocblas_shapes": {
        "label": "T10 rocBLAS shape probe",
        "targets": ["lib:rocblas", "workload:llm"],
        "resolves": ["unk:best_gemm_tiles"],
        "cost": 3,
    },
    "probe:T11_miopen_conv": {
        "label": "T11 MIOpen conv + perfdb stability",
        "targets": ["lib:miopen", "component:perfdb", "workload:diffusion"],
        "resolves": ["unk:first_bad_layer", "unk:miopen_perfdb_stability", "unk:precision_matrix"],
        "cost": 5,
    },
    "probe:T12_framework_layers": {
        "label": "T12 framework layer probes",
        "targets": ["fw:pytorch", "workload:diffusion", "workload:llm"],
        "resolves": ["unk:first_bad_layer", "unk:precision_matrix"],
        "cost": 5,
    },
    "sweep:kernel_boundary": {
        "label": "Kernel sweep for KFD stability boundary",
        "targets": ["component:host_kernel", "driver:amdgpu_kfd"],
        "resolves": ["unk:kernel_boundary_exact"],
        "cost": 4,
    },
    "sweep:baseline_matrix": {
        "label": "Baseline stack matrix (ROCm 5.7 vs 6.4, patched vs stock)",
        "targets": ["rocm:5.7", "rocm:6.4", "stack:rr_rocm64_base"],
        "resolves": ["unk:which_stack_is_best_baseline"],
        "cost": 4,
    },
    "sweep:flags_matrix": {
        "label": "Flag/settings matrix (--lowvram, MIOPEN_LOG_LEVEL, CFG hacks)",
        "targets": ["flag:lowvram", "flag:miopen_log_level_3", "flag:cfg_1_0"],
        "resolves": ["unk:which_build_flags_are_required_per_workload"],
        "cost": 2,
    },
}


def unknown_pressure(g: nx.MultiDiGraph, node_id: str) -> int:
    score = 0
    for src, _, _, edata in g.in_edges(node_id, keys=True, data=True):
        rel = edata.get("relation")
        if rel in {"requires_test", "targets", "maps_to", "candidate_baseline"}:
            score += 1
    return score


def rank_experiments(g: nx.MultiDiGraph) -> List[Dict[str, Any]]:
    ranked: List[Tuple[float, Dict[str, Any]]] = []

    for exp_id, spec in DEFAULT_EXPERIMENTS.items():
        resolve_score = 0
        reasons = []
        for unk in spec["resolves"]:
            if unk in g:
                p = unknown_pressure(g, unk)
                resolve_score += p * 3
                reasons.append({"unknown": unk, "pressure": p})
            else:
                resolve_score += 1

        target_bonus = 0
        for tgt in spec["targets"]:
            if tgt in g:
                target_bonus += 1

        score = resolve_score + target_bonus - spec["cost"] * 0.5

        ranked.append((score, {
            "id": exp_id,
            "label": spec["label"],
            "score": round(score, 2),
            "cost": spec["cost"],
            "targets": spec["targets"],
            "resolves": spec["resolves"],
            "reasons": reasons,
        }))

    ranked.sort(key=lambda x: (-x[0], x[1]["cost"], x[1]["id"]))
    return [r[1] for r in ranked]


def main() -> None:
    g = build_seed_graph()
    ranked = rank_experiments(g)

    out = Path("out")
    out.mkdir(exist_ok=True, parents=True)
    (out / "ranked_experiment_plan.json").write_text(json.dumps(ranked, indent=2))

    print("RANKED NEXT EXPERIMENTS")
    print("-" * 70)
    for item in ranked[:10]:
        print(f"{item['id']}: score={item['score']} cost={item['cost']} :: {item['label']}")
        if item["resolves"]:
            print("  resolves:", ", ".join(item["resolves"]))
        if item["targets"]:
            print("  targets :", ", ".join(item["targets"]))


if __name__ == "__main__":
    main()
