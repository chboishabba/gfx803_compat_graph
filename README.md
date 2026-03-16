# gfx803 compatibility graph (seeded from current known facts)

This is a small Python project that turns the current gfx803 / RX580 / ROCm debugging knowledge into a structured graph.

It includes:

- `graph_schema.py` — graph helpers and node/edge conventions
- `seed_graph.py` — builds the seeded knowledge graph from currently known facts
- `graph_queries.py` — query helpers
- `run_demo.py` — builds the graph, prints summaries, and exports artifacts
- `seed_facts.json` — machine-readable seed facts
- `requirements.txt` — only depends on `networkx`

## 📣 Call for Testers: Vulkan Comparison Branch

We are looking for community testers to contribute to the **Vulkan Comparison** research branch. Since native ROCm is unstable on many modern Linux kernels (6.14+) for gfx803, we are using Vulkan as the "Numerical Ground Truth."

**We need people who can:**
1. Run a working Vulkan-based compute workload (e.g., Stable Diffusion via `sd.cpp` or `ncnn`) on an RX 580.
2. Capture output tensors using the `vulkan_ground_truth_capture.py` tool.
3. Help map these against failing ROCm/Docker outputs to isolate the "first bad layer" (noise source).

## Host Environment Status

Currently actively testing on:
- **OS**: Arch Linux
- **Kernel**: 6.19+ (CachyOS)
- **Runtimes**: Vulkan (Working), ROCm 7.2 (Native broken/KFD issues), Nix (Installed - experimenting with low-overhead builds).

> [!NOTE]
> **Disk Space Strategy**: We are being strategic with disk usage. We prefer Nix shells or minimal containers over massive 20GB+ PyTorch Docker images where possible to avoid SSD wear.

## ❄️ Nix Strategy

For testers with limited disk space, we are exploring **Nix flakes** to provide reproducible development shells. This allows us to:
1. Share system-level dependencies (like `hip`, `llvm`, `clinfo`) across projects.
2. Avoid the storage overhead of multi-layered Docker images.
3. Rapidly iterate on custom ROCm library builds (rocBLAS, MIOpen) without a full container rebuild.

If you have Nix installed, check out the upcoming `flake.nix` in the comparison branch.

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


## Added in v2

- richer seed graph including:
  - Rosenbusch ROCm 6.4 gfx803 stack
  - your `rr_gfx803_rocm` fork/work repo
  - your `gfx803_compat_graph` repo
  - `advanced-lvl-up` issue thread integration
  - `lamikr/rocm_sdk_builder` discussion node
  - workload-specific flags/settings
  - baseline stack candidates

- `ingest_external_repos.py`
  - deterministic local ingester for known repo cluster

- `experiment_planner.py`
  - ranks the next experiments to run based on graph pressure
  - outputs `out/ranked_experiment_plan.json`

### Extra run commands

```bash
python experiment_planner.py
```

