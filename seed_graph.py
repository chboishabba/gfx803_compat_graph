from __future__ import annotations

import json
from pathlib import Path
import networkx as nx

from graph_schema import make_graph, add_node, add_edge, NodeSpec, EdgeSpec, to_jsonable


from ingest_external_repos import ingest_repo_cluster
from graph_miner import run_miner

def build_seed_graph(facts_path: str | Path = "seed_facts.json") -> nx.MultiDiGraph:
    path = Path(facts_path)
    data = json.loads(path.read_text())
    g = make_graph()

    for item in data["nodes"]:
        add_node(g, NodeSpec(**item))

    for item in data["edges"]:
        add_edge(g, EdgeSpec(**item))

    # Apply additional hardcoded knowledge/relations
    ingest_repo_cluster(g)
    
    # Run the miner to extract insights from external references
    run_miner(g)

    return g


def export_graph(g: nx.MultiDiGraph, out_dir: str | Path = "out") -> None:
    out = Path(out_dir)
    out.mkdir(exist_ok=True, parents=True)

    json_path = out / "gfx803_graph.json"
    json_path.write_text(json.dumps(to_jsonable(g), indent=2))

    # GraphML requires simple scalar attrs; stringify where needed.
    g2 = nx.MultiDiGraph()
    for n, attrs in g.nodes(data=True):
        clean = {k: str(v) if not isinstance(v, (str, int, float, bool)) else v for k, v in attrs.items()}
        g2.add_node(n, **clean)
    for u, v, k, attrs in g.edges(keys=True, data=True):
        clean = {kk: str(vv) if not isinstance(vv, (str, int, float, bool)) else vv for kk, vv in attrs.items()}
        g2.add_edge(u, v, key=k, **clean)
    nx.write_graphml(g2, out / "gfx803_graph.graphml")
