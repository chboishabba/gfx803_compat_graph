from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def merge_facts(base_path: str | Path, patch: Dict[str, Any]) -> None:
    base_path = Path(base_path)
    if not base_path.exists():
        data = {"nodes": [], "edges": []}
    else:
        data = json.loads(base_path.read_text())

    # Map existing nodes for easy lookup
    node_map = {n["node_id"]: n for n in data["nodes"]}
    for new_node in patch.get("nodes", []):
        node_id = new_node["node_id"]
        if node_id in node_map:
            # Update existing node with new info
            node_map[node_id].update(new_node)
        else:
            data["nodes"].append(new_node)
            node_map[node_id] = new_node

    # Map existing edges (src+dst+relation)
    edge_map = {}
    for e in data["edges"]:
        key = (e["src"], e["dst"], e.get("relation", ""))
        edge_map[key] = e

    for new_edge in patch.get("edges", []):
        key = (new_edge["src"], new_edge["dst"], new_edge.get("relation", ""))
        if key in edge_map:
            edge_map[key].update(new_edge)
        else:
            data["edges"].append(new_edge)
            edge_map[key] = new_edge

    base_path.write_text(json.dumps(data, indent=2))
    print(f"Merged {len(patch.get('nodes', []))} nodes and {len(patch.get('edges', []))} edges into {base_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python merge.py <base_facts.json> <patch.json>")
        sys.exit(1)

    base = sys.argv[1]
    patch_file = sys.argv[2]
    patch_data = json.loads(Path(patch_file).read_text())
    merge_facts(base, patch_data)
