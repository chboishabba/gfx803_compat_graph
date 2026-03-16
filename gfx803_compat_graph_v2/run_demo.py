from __future__ import annotations

import json
from pathlib import Path

from seed_graph import build_seed_graph, export_graph
from graph_queries import (
    print_summary,
    nodes_by_status,
    proposed_experiments,
    frontier_unknowns,
)


def main() -> None:
    g = build_seed_graph()
    export_graph(g, "out")
    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True, parents=True)

    kk = nodes_by_status(g, "known_known")
    ku = nodes_by_status(g, "known_unknown")
    exps = proposed_experiments(g)
    frontier = frontier_unknowns(g)

    (out_dir / "known_knowns.json").write_text(json.dumps(kk, indent=2))
    (out_dir / "known_unknowns.json").write_text(json.dumps(ku, indent=2))
    (out_dir / "proposed_experiments.json").write_text(json.dumps(exps, indent=2))
    (out_dir / "frontier_unknowns.json").write_text(json.dumps(frontier, indent=2))

    print_summary(g)
    print()
    print("KNOWN KNOWNS")
    print("-" * 70)
    for item in kk:
        print(f"{item['id']:<32} {item['label']}")
    print()
    print("KNOWN UNKNOWNS")
    print("-" * 70)
    for item in ku:
        print(f"{item['id']:<32} {item['label']}")
    print()
    print("PROPOSED EXPERIMENTS")
    print("-" * 70)
    for item in exps:
        print(f"{item['id']}: {item['label']}")
        if item["tests"]:
            print("  tests   :", ", ".join(item["tests"]))
        if item["targets"]:
            print("  targets :", ", ".join(item["targets"]))
        if item["measures"]:
            print("  measures:", ", ".join(item["measures"]))
    print()
    print("FRONTIER UNKNOWNS")
    print("-" * 70)
    for item in frontier:
        print(f"{item['id']}: score={item['score']} :: {item['label']}")
        for reason in item["reasons"]:
            print(f"  <- {reason['src']} [{reason['relation']}]")

    print()
    print(f"Wrote artifacts to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
