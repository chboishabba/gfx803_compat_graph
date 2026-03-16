# gfx803 compatibility graph (seeded from current known facts)

This is a small Python project that turns the current gfx803 / RX580 / ROCm debugging knowledge into a structured graph.

It includes:

- `graph_schema.py` — graph helpers and node/edge conventions
- `seed_graph.py` — builds the seeded knowledge graph from currently known facts
- `graph_queries.py` — query helpers
- `run_demo.py` — builds the graph, prints summaries, and exports artifacts
- `seed_facts.json` — machine-readable seed facts
- `requirements.txt` — only depends on `networkx`

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_demo.py
```

This writes:

- `out/gfx803_graph.json`
- `out/gfx803_graph.graphml`
- `out/known_knowns.json`
- `out/known_unknowns.json`
- `out/proposed_experiments.json`

## Graph model

The graph is a typed knowledge graph, not just a dependency tree.

Main node types:
- `hardware`
- `architecture`
- `kernel`
- `driver`
- `runtime`
- `library`
- `framework`
- `workload`
- `symptom`
- `hypothesis`
- `observation`
- `experiment`
- `metric`
- `unknown`

Main edge types:
- `has_architecture`
- `uses`
- `affects`
- `observed_in`
- `suggests`
- `suspects`
- `requires_test`
- `depends_on`
- `maps_to`
- `supports`
- `dropped_support_for`

Each node/edge carries:
- `status`: `known_known`, `known_unknown`, `hypothesis`, `context`
- `confidence`: float in `[0,1]`
- `source`: short provenance tag

## Current seeded facts

The seed graph encodes the current state of discussion:

Known-known-ish:
- RX580 uses gfx803 / Polaris
- gfx803 support was dropped officially in newer ROCm
- Whisper works on some ROCm 6.4 paths
- basic GEMM / HIP math appears functional
- diffusion/image generation can produce noise
- LLM/token throughput can be slow
- some kernel / KFD reset issues affect Polaris under compute load
- ROCm containers share the host kernel
- Vulkan can match or beat ROCm in some tested cases
- CFG=1.0 improved diffusion throughput materially in at least one report

Known-unknown-ish:
- first corrupted tensor/layer in diffusion path
- whether noise begins in conv path, MIOpen, mixed precision, or framework integration
- whether token slowness is fallback GEMM / poor occupancy / launch geometry
- exact kernel-version compatibility boundary for KFD reset stability
- safe precision matrix for gfx803 by workload
- optimal GEMM tile families for raw HIP probes

## Notes

- This is a seed atlas, not the final truth.
- It is designed to be extended with canonical test outputs later.
- The code does not require PyTorch; it only manages the compatibility graph.
