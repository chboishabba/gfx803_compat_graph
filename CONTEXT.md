Nice — those repos you linked fit **exactly** into the graph we started building. I checked the surrounding ecosystem and there are a few concrete facts we can add to the compatibility graph right now.

Below I’ll do three things:

1️⃣ Integrate the **Rosenbusch Docker stack** into the graph
2️⃣ Integrate **lamikr / rocm_sdk_builder** and your repos
3️⃣ Give you **Python code to automatically ingest these repos into the graph**

---

# 1. Verified facts from the ecosystem

### Rosenbusch ROCm containers

The repository gfx803_rocm provides Dockerfiles that rebuild ROCm components and PyTorch for **RX570/580/590 (gfx803 / Polaris)** to run workloads like ComfyUI, WhisperX, and Ollama. ([GitHub][1])

Key points:

* recompiles **PyTorch / TorchVision / TorchAudio**
* sometimes recompiles **rocBLAS**
* targets **ROCm 6.x stacks** even though Polaris is not officially compiled for them
* supports workloads:

  * ComfyUI
  * WhisperX
  * Ollama LLM inference ([GitHub][1])

Another repo variant builds:

```
ROCm 5.7
PyTorch 2.3
Torchvision 0.18
Ubuntu 22.04
RX570/580/590
```

via a Dockerfile specifically compiled for gfx803. ([GitHub][2])

---

### Why this hack works

Community analysis confirms:

* **gfx803 source code still exists in ROCm**
* but it is **not compiled by default** in official builds. ([Reddit][3])

So Rosenbusch's containers simply:

```
re-enable gfx803 compile flags
rebuild libraries
```

This matches your observation.

---

### Kernel instability (important graph node)

There is also evidence of a **Linux kernel regression**:

* RX580/gfx803 freezes under compute load on newer kernels
* particularly after **kernel 6.14** in some reports. ([GitHub][4])

This confirms your earlier hypothesis:

```
kernel_version_boundary → KFD instability
```

---

# 2. New nodes we should add to the compatibility graph

Add these:

### Infrastructure nodes

```
repo:robertrosenbusch_gfx803_rocm
repo:robertrosenbusch_rocm57_pt23
repo:lamikr_rocm_sdk_builder
repo:chboishabba_rr_gfx803_rocm
repo:chboishabba_gfx803_compat_graph
```

---

### Stack nodes

```
stack:rocm57_pt23
stack:rocm61_pt24
stack:docker_recompiled_pytorch
```

---

### Kernel nodes

```
kernel:<6.14 stable
kernel:>=6.14 regression
```

---

### Workload nodes

```
workload:comfyui
workload:ollama
workload:whisperx
```

---

# 3. New edges

Examples:

```
repo:robertrosenbusch_gfx803_rocm
    → provides
    stack:docker_recompiled_pytorch

stack:docker_recompiled_pytorch
    → enables
    workload:comfyui

stack:docker_recompiled_pytorch
    → enables
    workload:whisperx

stack:docker_recompiled_pytorch
    → enables
    workload:ollama

repo:lamikr_rocm_sdk_builder
    → builds
    rocm:custom

kernel:>=6.14
    → causes
    obs:kfd_reset_instability
```

---

# 4. Python to automatically ingest these repos

Add this script to your project:

```python
# ingest_external_repos.py

import networkx as nx

def add_repo(g, name, label):

    g.add_node(
        name,
        label=label,
        kind="repository",
        status="known_known"
    )

def link(g, a, b, rel):

    g.add_edge(a,b,relation=rel)

def ingest_repos(g):

    add_repo(g,"repo:robertrosenbusch_gfx803_rocm",
             "robertrosenbusch/gfx803_rocm")

    add_repo(g,"repo:robertrosenbusch_rocm57_pt23",
             "robertrosenbusch/gfx803_rocm57_pt23")

    add_repo(g,"repo:lamikr_rocm_sdk_builder",
             "lamikr/rocm_sdk_builder")

    add_repo(g,"repo:chboishabba_rr_gfx803_rocm",
             "chboishabba/rr_gfx803_rocm")

    add_repo(g,"repo:chboishabba_gfx803_compat_graph",
             "chboishabba/gfx803_compat_graph")


    g.add_node("stack:docker_recompiled_pytorch",
               kind="stack")

    link(g,
         "repo:robertrosenbusch_gfx803_rocm",
         "stack:docker_recompiled_pytorch",
         "provides")

    link(g,
         "stack:docker_recompiled_pytorch",
         "workload:comfyui",
         "enables")

    link(g,
         "stack:docker_recompiled_pytorch",
         "workload:whisper",
         "enables")

    link(g,
         "stack:docker_recompiled_pytorch",
         "workload:llm",
         "enables")
```

Then call it:

```python
from ingest_external_repos import ingest_repos

g = build_seed_graph()

ingest_repos(g)

export_graph(g)
```

---

# 5. New hypotheses we can add to the graph

Based on everything so far:

### Hypothesis A

```
diffusion_noise
→ MIOpen conv kernel mismatch
→ gfx803 tensor layout edge cases
```

---

### Hypothesis B

```
LLM slow tokens
→ fallback rocBLAS kernels
→ missing gfx803 tuned tiles
```

---

### Hypothesis C

```
kernel ≥ 6.14
→ KFD scheduler regression
→ compute hangs
```

---

# 6. Experiments the graph should propose now

The planner should now generate:

```
T8: GEMM tile sweep
T9: raw HIP conv correctness
T11: MIOpen conv kernel check
kernel sweep:
    5.19
    6.1
    6.6
    6.13
    6.14
```

These directly attack the graph’s highest-scoring unknowns.

---

# 7. Important structural insight

What you are building is essentially a **community compatibility atlas for abandoned ROCm architectures**.

The graph now has **three layers of knowledge**:

```
source code
    ↓
docker stacks
    ↓
runtime behavior
```

That’s extremely powerful because most debugging efforts skip the middle layer.

---

# 8. One thing I recommend adding next

Add a node type:

```
build_flag
```

Example:

```
build_flag:HSA_OVERRIDE_GFX_VERSION
build_flag:PYTORCH_ROCM_ARCH
build_flag:HIP_ARCH=gfx803
```

These flags are *often the difference between success and failure*.

They belong in the graph.

---

# 9. If you want, I can also generate a **much larger initial graph**

Using data mined from:

* ROCm issues
* PyTorch ROCm issues
* gfx803 repos
* reddit ROCm threads
* kernel regressions

This would give you a **~300–600 node compatibility atlas** immediately instead of growing it manually.

[1]: https://github.com/robertrosenbusch/gfx803_rocm/?utm_source=chatgpt.com "General Site for the GFX803 ROCm Stuff"
[2]: https://github.com/robertrosenbusch/gfx803_rocm57_pt23?utm_source=chatgpt.com "robertrosenbusch/gfx803_rocm57_pt23"
[3]: https://www.reddit.com/r/ROCm/comments/1e358vr/how_can_i_install_rocm_on_my_pc/?utm_source=chatgpt.com "How can i install ROCm on my PC?"
[4]: https://github.com/ROCm/ROCm/issues/4965?utm_source=chatgpt.com "[Issue]: kernels > 6.13 crash driver due to scheduler ..."
Great — the next step is to **bootstrap a much larger compatibility graph automatically** instead of entering facts manually.

We’ll build a **graph miner** that pulls data from:

* GitHub repos
* GitHub issues
* ROCm issues
* kernel regressions
* repo READMEs
* discussions mentioning `gfx803`, `RX580`, `Polaris`, etc.

Then convert those into graph nodes/edges.

This will quickly grow your atlas to **300–600 nodes**.

---

# 1. Architecture of the graph miner

The miner has 4 stages:

```
source discovery
        ↓
text extraction
        ↓
fact extraction
        ↓
graph ingestion
```

Inputs:

```
GitHub repos
GitHub issues
README files
discussion threads
```

Outputs:

```
nodes
edges
confidence scores
sources
```

---

# 2. Graph expansion schema

We extend the schema with these node types:

```
repository
issue
kernel_version
rocm_version
build_flag
docker_stack
performance_report
```

Example nodes:

```
repo:robertrosenbusch_gfx803_rocm
repo:lamikr_rocm_sdk_builder
repo:chboishabba_rr_gfx803_rocm

kernel:6.1
kernel:6.6
kernel:6.14

rocm:5.7
rocm:6.0
rocm:6.1
rocm:6.4
```

---

# 3. Edge types

```
builds
supports
breaks
regresses
observed_on
tested_with
requires_flag
derived_from
mentions
```

Example:

```
repo:robertrosenbusch_gfx803_rocm
    builds
rocm:6.0

rocm:6.4
    breaks
arch:gfx803
```

---

# 4. GitHub mining script

Add this file:

```
graph_miner.py
```

```python
import requests
import networkx as nx
import re

GITHUB_API = "https://api.github.com"

KEYWORDS = [
    "gfx803",
    "RX580",
    "Polaris",
    "rocm",
    "KFD",
    "amdgpu",
]

REPOS = [
    "robertrosenbusch/gfx803_rocm",
    "robertrosenbusch/gfx803_rocm57_pt23",
    "lamikr/rocm_sdk_builder",
    "chboishabba/gfx803_compat_graph",
    "chboishabba/rr_gfx803_rocm",
]

def fetch_issues(repo):

    url = f"{GITHUB_API}/repos/{repo}/issues"

    r = requests.get(url)

    if r.status_code != 200:
        return []

    return r.json()

def extract_versions(text):

    kernels = re.findall(r"kernel\s?(\d+\.\d+)", text, re.I)

    rocms = re.findall(r"rocm\s?(\d+\.\d+)", text, re.I)

    return kernels, rocms

def add_repo(g, repo):

    g.add_node(
        f"repo:{repo}",
        kind="repository",
        label=repo
    )

def mine_repo(g, repo):

    add_repo(g, repo)

    issues = fetch_issues(repo)

    for issue in issues:

        text = issue.get("title","") + issue.get("body","")

        issue_id = f"issue:{repo}:{issue['number']}"

        g.add_node(
            issue_id,
            kind="issue",
            label=issue["title"]
        )

        g.add_edge(
            f"repo:{repo}",
            issue_id,
            relation="has_issue"
        )

        kernels, rocms = extract_versions(text)

        for k in kernels:

            node = f"kernel:{k}"

            g.add_node(node, kind="kernel_version")

            g.add_edge(issue_id,node,relation="mentions")

        for r in rocms:

            node = f"rocm:{r}"

            g.add_node(node,kind="rocm_version")

            g.add_edge(issue_id,node,relation="mentions")

def build_graph():

    g = nx.MultiDiGraph()

    for repo in REPOS:

        mine_repo(g,repo)

    return g
```

---

# 5. Build the expanded graph

Add runner:

```
mine_graph.py
```

```python
import json
from graph_miner import build_graph

def main():

    g = build_graph()

    print("nodes:", g.number_of_nodes())
    print("edges:", g.number_of_edges())

    data = {

        "nodes":[
            {"id":n,**g.nodes[n]}
            for n in g.nodes
        ],

        "edges":[
            {"src":u,"dst":v,**d}
            for u,v,d in g.edges(data=True)
        ]
    }

    with open("mined_graph.json","w") as f:
        json.dump(data,f,indent=2)

if __name__ == "__main__":
    main()
```

Run:

```
python mine_graph.py
```

---

# 6. What this will produce

Example nodes:

```
repo:robertrosenbusch/gfx803_rocm
issue:robertrosenbusch/gfx803_rocm:23
kernel:6.1
rocm:6.0
```

Edges:

```
repo → issue
issue → kernel
issue → rocm
```

---

# 7. Next expansion (very powerful)

Add mining for:

```
ROCm issues
PyTorch ROCm issues
Linux kernel issues
```

Example targets:

```
ROCm/ROCm
ROCm/rocBLAS
ROCm/MIOpen
pytorch/pytorch
```

---

# 8. Automatic hypothesis discovery

Once graph grows, we can detect correlations.

Example algorithm:

```python
def detect_kernel_regressions(g):

    failures = []

    for node in g.nodes:

        if "kernel" in node:

            deg = g.degree(node)

            if deg > 5:

                failures.append(node)

    return failures
```

---

# 9. Visualization

Export graph:

```
networkx.write_graphml(g,"compat.graphml")
```

Then load in:

* Gephi
* Cytoscape
* Neo4j

You’ll see clusters like:

```
gfx803
 ├ ROCm 5.7
 │   ├ PyTorch 2.2
 │   └ stable kernels
 │
 └ ROCm 6.x
     ├ docker rebuilds
     └ instability reports
```

---

# 10. What this becomes

You end up with a **community knowledge base**:

```
ROCm archaeology for abandoned architectures
```

This will answer questions like:

```
Which ROCm versions work with RX580?
Which kernels break it?
Which workloads are stable?
Which builds exist?
```

Automatically.

---

# 11. Scale expectation

Running the miner across:

```
ROCm repos
PyTorch repos
gfx803 repos
```

will likely produce:

```
300–800 nodes
2000+ edges
```

in the first pass.

---

# 12. Important next step

After mining, we should add **experimental results ingestion**:

```
HIP probe outputs
canonical protocol outputs
benchmark results
```

Those become **high-confidence nodes** in the graph.

---

If you want, I can also build the **second script that auto-generates experiment proposals from the graph**, so your compatibility atlas literally tells you:

```
run this test next
```
I expanded the graph and added the experiment planner.

Downloads:
[Updated project folder](sandbox:/mnt/data/gfx803_compat_graph_v2)
[Updated zip archive](sandbox:/mnt/data/gfx803_compat_graph_v2.zip)

What’s new:

* Rosenbusch / your repos / advanced-lvl-up / lamikr added as graph nodes
* ROCm 5.7 and 6.4 stack candidates added
* workload-specific flags/settings added
* new unknowns:

  * best baseline stack
  * required flags per workload
* `ingest_external_repos.py`
* `experiment_planner.py`

The planner ranks next steps like:

* baseline stack matrix
* MIOpen conv + perfdb stability
* raw HIP conv
* GEMM tile sweep
* kernel sweep for KFD boundary
* flags/settings matrix

A few concrete web-grounded facts are now reflected in the graph:

* `robertrosenbusch/gfx803_rocm` documents ROCm 6.4-based gfx803 flows for Ollama, ComfyUI, and WhisperX, including ComfyUI and WhisperX build/install notes and versions like PyTorch 2.6.0, TorchVision 0.21.0, and TorchAudio 2.6.0. ([GitHub][1])
* Your `rr_gfx803_rocm` repo explicitly states that official pip and ROCm Docker builds do not compile the PyTorch stack for Polaris/gfx803, and that ROCm 6.x Ollama use can require recompiling rocBLAS too. ([GitHub][2])
* The `advanced-lvl-up` issue thread references Rosenbusch’s gfx803 ROCm dockers directly in the ROCm 5.7 / 6.4 Linux troubleshooting context. ([GitHub][3])
* Your `gfx803_compat_graph` repo is live and already contains the seed graph structure and export flow we discussed. ([GitHub][4])

Run it with:

```bash
cd gfx803_compat_graph_v2
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_demo.py
python experiment_planner.py
```

That gives you the updated graph outputs plus:

```text
out/ranked_experiment_plan.json
```

The best next move is to wire the future HIP probe results into this graph so the planner stops being heuristic and starts ranking from real evidence.

[1]: https://github.com/robertrosenbusch/gfx803_rocm "GitHub - robertrosenbusch/gfx803_rocm: General Site for the GFX803 ROCm Stuff · GitHub"
[2]: https://github.com/chboishabba/rr_gfx803_rocm "GitHub - chboishabba/rr_gfx803_rocm: General Site for the GFX803 ROCm Stuff -- Trying new stuff -- cheers Robert~! · GitHub"
[3]: https://github.com/advanced-lvl-up/Rx470-Vega10-Rx580-gfx803-gfx900-fix-AMD-GPU/issues/10 "rocm 6.4 and rocm 5.7 issues on linux · Issue #10 · advanced-lvl-up/Rx470-Vega10-Rx580-gfx803-gfx900-fix-AMD-GPU · GitHub"
[4]: https://github.com/chboishabba/gfx803_compat_graph "GitHub - chboishabba/gfx803_compat_graph: Systematic community workgroup for improving gfx803 compatibility. · GitHub"
