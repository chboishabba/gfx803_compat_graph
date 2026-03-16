from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, Optional
import networkx as nx


@dataclass
class NodeSpec:
    node_id: str
    label: str
    kind: str
    status: str = "context"
    confidence: float = 1.0
    source: str = "manual_seed"
    attrs: Optional[Dict[str, Any]] = None


@dataclass
class EdgeSpec:
    src: str
    dst: str
    relation: str
    status: str = "context"
    confidence: float = 1.0
    source: str = "manual_seed"
    attrs: Optional[Dict[str, Any]] = None


def make_graph() -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    g.graph["name"] = "gfx803_compatibility_graph"
    g.graph["version"] = "0.1.0"
    return g


def add_node(g: nx.MultiDiGraph, spec: NodeSpec) -> None:
    data = {
        "label": spec.label,
        "kind": spec.kind,
        "status": spec.status,
        "confidence": spec.confidence,
        "source": spec.source,
    }
    if spec.attrs:
        data.update(spec.attrs)
    g.add_node(spec.node_id, **data)


def add_edge(g: nx.MultiDiGraph, spec: EdgeSpec) -> None:
    data = {
        "relation": spec.relation,
        "status": spec.status,
        "confidence": spec.confidence,
        "source": spec.source,
    }
    if spec.attrs:
        data.update(spec.attrs)
    g.add_edge(spec.src, spec.dst, key=spec.relation, **data)


def node_record(g: nx.MultiDiGraph, node_id: str) -> Dict[str, Any]:
    return {"id": node_id, **dict(g.nodes[node_id])}


def edge_records(g: nx.MultiDiGraph) -> Iterable[Dict[str, Any]]:
    for src, dst, key, data in g.edges(keys=True, data=True):
        yield {"src": src, "dst": dst, "key": key, **dict(data)}


def to_jsonable(g: nx.MultiDiGraph) -> Dict[str, Any]:
    return {
        "graph": dict(g.graph),
        "nodes": [node_record(g, n) for n in g.nodes()],
        "edges": list(edge_records(g)),
    }
