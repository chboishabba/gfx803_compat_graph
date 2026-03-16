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
        try:
            data = json.loads(base_path.read_text())
        except json.JSONDecodeError:
            print(f"Error decoding {base_path}. Initializing empty.")
            data = {"nodes": [], "edges": []}

    if "nodes" not in data: data["nodes"] = []
    if "edges" not in data: data["edges"] = []

    # Map existing nodes for easy lookup by any id-like key
    node_map = {}
    for n in data["nodes"]:
        nid = n.get("node_id") or n.get("id")
        if nid:
            node_map[nid] = n

    for new_node in patch.get("nodes", []):
        node_id = new_node.get("node_id") or new_node.get("id")
        if not node_id:
            print(f"Skipping node without id: {new_node}")
            continue
            
        if node_id in node_map:
            node_map[node_id].update(new_node)
        else:
            data["nodes"].append(new_node)
            node_map[node_id] = new_node

    # Map existing edges (src+dst+relation)
    edge_map = {}
    for e in data["edges"]:
        if "src" not in e or "dst" not in e:
            continue
        key = (e["src"], e["dst"], e.get("relation", ""))
        edge_map[key] = e

    for new_edge in patch.get("edges", []):
        if "src" not in new_edge or "dst" not in new_edge:
            print(f"Skipping edge without src/dst: {new_edge}")
            continue
            
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
    try:
        patch_data = json.loads(Path(patch_file).read_text())
        merge_facts(base, patch_data)
    except Exception as e:
        print(f"Failed to merge {patch_file}: {e}")
        sys.exit(1)
