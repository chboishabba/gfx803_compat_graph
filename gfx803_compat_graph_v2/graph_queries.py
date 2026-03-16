from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple
import networkx as nx


def nodes_by_status(g: nx.MultiDiGraph, status: str) -> List[Dict[str, Any]]:
    out = []
    for node_id, attrs in g.nodes(data=True):
        if attrs.get("status") == status:
            out.append({"id": node_id, **dict(attrs)})
    return sorted(out, key=lambda x: (x.get("kind", ""), x["id"]))


def summarize_by_kind(g: nx.MultiDiGraph) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for _, attrs in g.nodes(data=True):
        counts[attrs.get("kind", "unknown")] += 1
    return dict(sorted(counts.items()))


def relation_counts(g: nx.MultiDiGraph) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for _, _, _, attrs in g.edges(keys=True, data=True):
        counts[attrs.get("relation", "unknown")] += 1
    return dict(sorted(counts.items()))


def proposed_experiments(g: nx.MultiDiGraph) -> List[Dict[str, Any]]:
    result = []
    for node_id, attrs in g.nodes(data=True):
        if attrs.get("kind") != "experiment":
            continue

        tests = []
        targets = []
        measures = []

        for _, dst, _, edata in g.out_edges(node_id, keys=True, data=True):
            rel = edata.get("relation")
            if rel == "tests":
                tests.append(dst)
            elif rel == "targets":
                targets.append(dst)
            elif rel == "measures":
                measures.append(dst)

        result.append({
            "id": node_id,
            "label": attrs.get("label"),
            "status": attrs.get("status"),
            "tests": sorted(tests),
            "targets": sorted(targets),
            "measures": sorted(measures),
        })
    return sorted(result, key=lambda x: x["id"])


def frontier_unknowns(g: nx.MultiDiGraph) -> List[Dict[str, Any]]:
    """
    Unknowns with the largest number of incoming 'requires_test' or 'targets' relations.
    """
    ranking: List[Tuple[int, str, Dict[str, Any]]] = []
    for node_id, attrs in g.nodes(data=True):
        if attrs.get("status") != "known_unknown":
            continue
        score = 0
        reasons = []
        for src, _, _, edata in g.in_edges(node_id, keys=True, data=True):
            if edata.get("relation") in {"requires_test", "targets", "maps_to"}:
                score += 1
                reasons.append({"src": src, "relation": edata.get("relation")})
        ranking.append((score, node_id, {"id": node_id, "label": attrs.get("label"), "score": score, "reasons": reasons}))
    ranking.sort(key=lambda x: (-x[0], x[1]))
    return [item[2] for item in ranking]


def print_summary(g: nx.MultiDiGraph) -> None:
    print("GRAPH SUMMARY")
    print("-" * 70)
    print(f"Nodes: {g.number_of_nodes()}")
    print(f"Edges: {g.number_of_edges()}")
    print()
    print("By kind:")
    for kind, count in summarize_by_kind(g).items():
        print(f"  {kind:<18} {count}")
    print()
    print("Relations:")
    for rel, count in relation_counts(g).items():
        print(f"  {rel:<18} {count}")
