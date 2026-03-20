#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: update_graph.py <drift-matrix.jsonl> <out.json>")

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])

    nodes = {}
    edges = []

    def add_node(node_id: str, **attrs):
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, **attrs}

    def add_edge(src_id: str, dst_id: str, relation: str, **attrs):
        edges.append({"src": src_id, "dst": dst_id, "relation": relation, **attrs})

    records = []
    for line in src.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))

    add_node("arch:gfx803", kind="architecture", label="gfx803", status="known_known")

    for rec in records:
        profile_id = f"profile:{rec['profile']}"
        result_id = f"result:{rec['profile']}:{'stable' if rec['stable'] else 'drift'}"
        gpu_id = f"gpu:{rec['gpu_name'] or 'unknown'}"

        add_node(profile_id, kind="solver_profile", label=rec["profile"], status="known_known")
        add_node(gpu_id, kind="hardware", label=rec["gpu_name"] or "unknown", status="known_known")
        add_node(
            result_id,
            kind="observation",
            label=("stable" if rec["stable"] else f"drift max={rec['max_drift']:.6g}"),
            status=("known_known" if rec["stable"] else "known_known"),
            max_drift=rec["max_drift"],
            min_drift=rec["min_drift"],
            mean_drift=rec["mean_drift"],
            drift_count=rec["drift_count"],
            kernel=rec["kernel"],
            log_file=rec["log_file"],
        )

        add_edge(gpu_id, "arch:gfx803", "has_architecture")
        add_edge(profile_id, result_id, "produced")
        add_edge(gpu_id, result_id, "observed_on")

        for idx, line in enumerate(rec.get("solver_lines", [])):
            solver_id = f"solverline:{rec['profile']}:{idx}"
            add_node(solver_id, kind="solver_trace", label=line, status="known_known")
            add_edge(profile_id, solver_id, "captured_solver_line")

    payload = {
        "graph": {"name": "gfx803_drift_results", "version": "0.1.0"},
        "nodes": list(nodes.values()),
        "edges": edges,
        "record_count": len(records),
    }

    dst.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {dst}")

if __name__ == "__main__":
    main()
