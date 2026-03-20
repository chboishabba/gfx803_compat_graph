import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("out/drift/benchmark-results.jsonl")
dest = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path("out/compat-graph-results.json")
graph = []

if not out.exists():
    print(f"Error: {out} not found. Run drift-matrix first.")
    exit(1)

for line in out.read_text().splitlines():
    if not line.strip():
        continue
    entry = json.loads(line)
    metrics = entry.get("metrics", {})

    graph.append({
        "node": f"solver_profile:{entry['profile']}",
        "stack_id": entry.get("stack_id"),
        "status": entry.get("status"),
        "drift": metrics.get("max_drift", 0.0),
        "stable": entry.get("status") == "pass" or metrics.get("max_drift", 0.0) < 0.05,
        "workload": entry.get("workload"),
        "reference_class": entry.get("reference_class"),
    })

dest.write_text(
    json.dumps(graph, indent=2)
)
print(f"Updated {dest}")
