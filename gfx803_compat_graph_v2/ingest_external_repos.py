from __future__ import annotations

from graph_schema import add_node, add_edge, NodeSpec, EdgeSpec


def ingest_repo_cluster(g):
    """
    Add currently-known external repos / stacks that matter to gfx803 debugging.
    This is deterministic and local; no API access required.
    """
    repos = [
        ("repo:robertrosenbusch_gfx803_rocm", "robertrosenbusch/gfx803_rocm"),
        ("repo:chboishabba_rr_gfx803_rocm", "chboishabba/rr_gfx803_rocm"),
        ("repo:chboishabba_gfx803_compat_graph", "chboishabba/gfx803_compat_graph"),
        ("repo:lamikr_rocm_sdk_builder", "lamikr/rocm_sdk_builder"),
        ("repo:advanced_lvl_up_fix_amd_gpu", "advanced-lvl-up/Rx470-Vega10-Rx580-gfx803-gfx900-fix-AMD-GPU"),
    ]
    for node_id, label in repos:
        if node_id not in g:
            add_node(g, NodeSpec(node_id=node_id, label=label, kind="repository", status="known_known", confidence=0.95, source="local_ingest"))

    relations = [
        ("repo:chboishabba_rr_gfx803_rocm", "repo:robertrosenbusch_gfx803_rocm", "derived_from"),
        ("repo:robertrosenbusch_gfx803_rocm", "workload:comfyui", "supports"),
        ("repo:robertrosenbusch_gfx803_rocm", "workload:whisperx", "supports"),
        ("repo:robertrosenbusch_gfx803_rocm", "workload:ollama", "supports"),
        ("repo:chboishabba_gfx803_compat_graph", "exp:canonical_protocol", "contains"),
        ("repo:chboishabba_gfx803_compat_graph", "exp:hip_probe_suite", "targets"),
    ]
    for src, dst, rel in relations:
        if src in g and dst in g:
            add_edge(g, EdgeSpec(src=src, dst=dst, relation=rel, status="known_known", confidence=0.9, source="local_ingest"))
