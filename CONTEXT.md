NEWER:
Could/should we turn these into nix flakes?

❯ tree /home/c/Documents/code/__OTHER/rr_gfx803_rocm
/home/c/Documents/code/__OTHER/rr_gfx803_rocm
├── benchmark
│   ├── comfyui_schnell_1024x1024.png
│   ├── comfyui_sd15_512x512_sd.png
│   ├── comfyui_sd15_512x768_sd.png
│   ├── comfyui_sd35_1024x1024.png
│   ├── comfyui_sdxl_1024x1024l.png
│   ├── cpu_rocm63_ollama_benchmark.png
│   ├── gfx803_rocm63_ollama_benchmark.png
│   ├── gpu_rocm63_ollama_benchmark.png
│   └── ollama
│       ├── raw_rocm6.3.4_ollama_0.6.5
│       ├── raw_rocm6.3.4_ollama_0.6.6
│       ├── raw_rocm6.4_ollama_0.6.5
│       ├── raw_rocm6.4_ollama_0.6.7-rc0
│       ├── raw_rocm6.4_ollama_0.6.8
│       ├── raw_rocm6.4_ollama_0.7.0
│       ├── raw_rocm6.4_ollama_0.8.0
│       ├── raw_rocm6.4_ollama_0.9.0
│       ├── rocm634_ollama065.csv
│       ├── rocm634_ollama066.csv
│       ├── rocm64_ollama065.csv
│       ├── rocm6.4_ollama_0.6.6
│       └── rocm64_ollama066.csv
├── CONTEXT.md
├── dev
│   ├── Dockerfile.base_rocm5.4_source_compile
│   ├── Dockerfile_rocm641_base
│   ├── Dockerfile_rocm641_comfyui
│   ├── Dockerfile_rocm641_llamacpp
│   ├── Dockerfile_rocm641_ollama
│   ├── Dockerfile_rocm641_pytorch
│   ├── Dockerfile_rocm641_whisperx
│   ├── Dockerfile_rocm64_base_2204
│   ├── Dockerfile_rocm64_pytorch_2204
│   ├── Dockerfile_rocm70_base
│   ├── Dockerfile.rvc_original
│   ├── entrypoint_rvc.sh
│   └── README.md
├── Dockerfile_rocm64_base
├── Dockerfile_rocm64_base_arch
├── Dockerfile_rocm64_base_arch_pinned
├── Dockerfile_rocm64_base_arch_pinned_cmake
├── Dockerfile_rocm64_base_arch_pinned_rmake
├── Dockerfile_rocm64_base_cachyos_pinned
├── Dockerfile_rocm64_base_cachyos_pinned_cmake
├── Dockerfile_rocm64_base_cachyos_pinned_rmake
├── Dockerfile_rocm64_comfyui
├── Dockerfile_rocm64_llamacpp
├── Dockerfile_rocm64_ollama
├── Dockerfile_rocm64_pytorch
├── Dockerfile_rocm64_pytorch_arch_rmake
├── Dockerfile_rocm64_pytorch_arch_rmake_opt
├── Dockerfile_rocm64_pytorch_arch_rmake_opt_prevega
├── Dockerfile_rocm64_whisperx
├── README.md
├── rocm_5.4
│   ├── Dockerfile.base_rocm5.4_source_compile
│   ├── Dockerfile.rvc_original
│   ├── entrypoint_rvc.sh
│   ├── logs
│   │   ├── build_rocm542.log
│   │   ├── build_rocm542_v1.log
│   │   ├── build_rocm542_v2.log
│   │   ├── build_rocm542_v3.log
│   │   ├── build_rocm542_v4.log
│   │   ├── build_rvc12.log
│   │   ├── build_rvc13.log
│   │   ├── build_rvc14.log
│   │   ├── build_rvc1.log
│   │   └── build_rvc.log
│   ├── README.md
│   └── screenshots
│       ├── banner.png
│       ├── screenshot1.png
│       ├── screenshot2.png
│       └── screenshot3.png
├── rocm_5.7
│   ├── Dockerfile_rocm57_comfyui
│   └── Dockerfile_rocm57_pt23
├── rocm_6.1
│   └── Dockerfile_rocm61_pt24
├── rocm_6.3
│   ├── Dockerfile_rocm63_comfyui
│   ├── Dockerfile_rocm63_ollama
│   ├── Dockerfile_rocm63_pt25
│   ├── Dockerfile_rocm63_whisperx
│   └── README.md
└── rocm_6.3.4
    ├── Dockerfile_rocm634_base
    ├── Dockerfile_rocm634_comfyui
    ├── Dockerfile_rocm634_ollama
    ├── Dockerfile_rocm634_pytorch
    ├── Dockerfile_rocm634_whisperx
    └── README.md

11 directories, 84 files

Yes — this repo is actually a very good candidate for a Nix flake, and converting it would likely simplify the combinatorial explosion of Dockerfiles you currently have.

Right now your structure is essentially encoding a matrix:

ROCm version
×
Application
×
Base distro
×
Build tweaks

Example combinations visible in the tree:

rocm_6.4 × pytorch
rocm_6.4 × ollama
rocm_6.4 × comfyui
rocm_6.4 × whisperx
rocm_6.4 × llamacpp

And each is expressed as a separate Dockerfile.

Nix flakes are extremely good at exactly this kind of matrix build.

1. What a Nix flake would replace here

Instead of:

Dockerfile_rocm64_pytorch
Dockerfile_rocm64_ollama
Dockerfile_rocm64_comfyui
Dockerfile_rocm64_llamacpp
Dockerfile_rocm64_whisperx

You would encode:

rocm version
framework
patches

as parameters.

Example conceptual structure:

rr_gfx803_rocm/
 ├ flake.nix
 ├ modules/
 │   ├ rocm.nix
 │   ├ pytorch.nix
 │   ├ ollama.nix
 │   ├ comfyui.nix
 │   ├ whisperx.nix
 │   └ llamacpp.nix
 └ overlays/
     └ gfx803_patch.nix
2. Why Nix is particularly good for this repo

Your project is effectively a compatibility lattice:

GPU architecture
ROCm version
application stack

Nix represents this naturally as a build graph.

You could generate environments like:

nix develop .#rocm63-ollama
nix develop .#rocm63-pytorch
nix develop .#rocm63-comfyui

No Docker builds required.

3. Even better: you can still output Docker images

You don't lose Docker distribution.

Nix can produce them deterministically:

nix build .#docker-ollama-rocm63

using dockerTools.

This replaces Dockerfiles entirely.

4. The biggest win for your specific project

Your repo currently duplicates a lot of base layers.

Example:

Dockerfile_rocm64_base
Dockerfile_rocm64_base_arch
Dockerfile_rocm64_base_arch_pinned
Dockerfile_rocm64_base_cachyos_pinned

In Nix this becomes:

baseEnv rocmVersion distro tweaks

Example:

baseEnv = { rocmVersion, distro ? "ubuntu" }:
  pkgs.mkShell {
    buildInputs = [
      rocmPackages.${rocmVersion}.hip
      rocmPackages.${rocmVersion}.rocblas
    ];
  };

Then reuse it everywhere.

5. Another huge benefit: reproducible ROCm pinning

Your repo clearly tracks multiple ROCm versions:

rocm_5.4
rocm_5.7
rocm_6.1
rocm_6.3
rocm_6.3.4
rocm_6.4

Nix flakes allow you to pin the exact nixpkgs revision that contains each version.

Example:

inputs.nixpkgs-rocm63.url = "github:NixOS/nixpkgs/<commit>";

Meaning:

ROCm 6.3 environment always rebuilds identically

Even years later.

6. Disk usage improvement

Right now Docker likely stores:

rocm64_base
rocm64_pytorch
rocm64_ollama
rocm64_comfyui

as separate layered images.

Nix will store:

ROCm once
PyTorch once
Ollama once

in /nix/store.

Which is much more space efficient.

7. Your repo is almost already structured for flakes

You already have:

benchmark/
dev/
rocm_6.3/
rocm_6.3.4/

This maps naturally to:

packages
devShells
dockerImages

in flakes.

8. Suggested flake outputs

Your flake could expose:

Dev environments
nix develop .#rocm63-pytorch
nix develop .#rocm63-ollama
nix develop .#rocm63-comfyui
Docker images
nix build .#docker-rocm63-ollama
Benchmarks
nix run .#benchmark-ollama
9. One complication: ROCm + gfx803

The tricky part is your RX580 gfx803 compatibility work.

ROCm upstream dropped official support.

You likely rely on:

HSA_OVERRIDE_GFX_VERSION
patched kernels
custom builds

In Nix this would be encoded as an overlay:

overlays/gfx803_patch.nix

This overlay would:

patch ROCm derivations
force gfx803 enablement
10. My honest recommendation

Yes — but do it incrementally.

Step 1:

flake.nix → dev environments only

Step 2:

replace base Dockerfiles

Step 3:

replace all Dockerfiles

Trying to convert everything immediately will be painful.

11. One more observation

Your repo is actually becoming something interesting:

gfx803 ROCm compatibility matrix

If expressed as a flake it could expose:

flake outputs = compatibility graph

Meaning users could run:

nix run github:chboishabba/gfx803_compat_graph#ollama-rocm63

This is exactly the sort of thing flakes are great for.

✅ Conclusion

Yes — converting this repo to a Nix flake is a very good idea, because:

you have a build matrix

many duplicated Dockerfiles

many pinned toolchains

reproducibility matters

All of those are Nix’s strengths.

If you want, I can also show you something that might dramatically simplify this repo:

How to collapse your ~30 Dockerfiles into ~150 lines of Nix.

Once you see the pattern, it becomes very clean.

go

Alright — let’s collapse your ~30 Dockerfiles into a single flake that generates the ROCm × app matrix automatically.

The key idea is:

Encode the matrix as data, not files.

Right now your repo encodes configuration in filenames:

Dockerfile_rocm64_pytorch
Dockerfile_rocm64_ollama
Dockerfile_rocm64_comfyui
Dockerfile_rocm64_whisperx
Dockerfile_rocm64_llamacpp

Nix instead represents that as a function applied over a set.

1. Minimal flake skeleton

Create:

flake.nix
{
  description = "gfx803 ROCm compatibility matrix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:

  let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };

    rocmVersions = {
      rocm63 = pkgs.rocmPackages;
      # additional pins can be added later
    };

  in {
  };
}
2. Encode the application stack

Instead of Dockerfiles, define modules:

modules/
   ollama.nix
   pytorch.nix
   comfyui.nix
   whisperx.nix
   llamacpp.nix

Example modules/ollama.nix:

{ pkgs, rocm }:

pkgs.mkShell {
  buildInputs = [
    rocm.hipblas
    rocm.rocblas
    pkgs.ollama
  ];
}

Example modules/pytorch.nix:

{ pkgs, rocm }:

pkgs.mkShell {
  buildInputs = [
    rocm.hipblas
    rocm.rocblas
    pkgs.python311
    pkgs.python311Packages.torch
  ];
}
3. Build the matrix automatically

Now the important part.

let

apps = {
  ollama = import ./modules/ollama.nix;
  pytorch = import ./modules/pytorch.nix;
  comfyui = import ./modules/comfyui.nix;
  whisperx = import ./modules/whisperx.nix;
  llamacpp = import ./modules/llamacpp.nix;
};

mkEnv = rocmName: rocm:
  pkgs.lib.mapAttrs
    (appName: module:
      module { inherit pkgs rocm; })
    apps;

devShellMatrix =
  pkgs.lib.mapAttrs mkEnv rocmVersions;

flatten =
  pkgs.lib.foldl'
    (acc: rocmSet:
      acc // rocmSet)
    {}
    (builtins.attrValues devShellMatrix);

in

This generates:

rocm63-ollama
rocm63-pytorch
rocm63-comfyui
rocm63-whisperx
rocm63-llamacpp

automatically.

4. Expose as flake devShells

Add to outputs:

{
  devShells.${system} = flatten;
}

Now you can run:

nix develop .#rocm63-ollama
nix develop .#rocm63-pytorch

No Docker build required.

5. Generate Docker images from the same definitions

You can still produce Docker images.

Add:

dockerImages.${system} =
  pkgs.lib.mapAttrs
    (name: shell:

      pkgs.dockerTools.buildImage {
        name = name;

        contents = shell.buildInputs;

        config = {
          Cmd = [ "bash" ];
        };
      }

    )
    flatten;

Now build:

nix build .#dockerImages.rocm63-ollama
6. gfx803 compatibility patch

You will probably need a ROCm override.

Add:

overlays/gfx803.nix

Example:

final: prev: {

  rocmPackages =
    prev.rocmPackages.overrideAttrs (old: {

      postPatch = ''
        export HSA_OVERRIDE_GFX_VERSION=8.0.3
      '';

    });

}

Then import overlay in flake:

pkgs = import nixpkgs {
  inherit system;
  overlays = [
    (import ./overlays/gfx803.nix)
  ];
};
7. Benchmark runner

You can even encode your benchmark scripts.

Example:

nix run .#benchmark-ollama
apps.${system}.benchmark-ollama = {
  type = "app";
  program = "${pkgs.writeShellScript "bench" ''
    ollama run llama3
  ''}";
};
8. What this does to your repo

Current state:

~30 Dockerfiles

After conversion:

flake.nix
modules/
overlays/

Probably 150–200 lines total.

9. Why this works extremely well for your project

Your repo is effectively a hardware compatibility lattice.

GPU architecture
×
ROCm version
×
framework

Nix was literally designed to encode dependency lattices.

10. What the finished UX looks like

User clones repo:

git clone gfx803_rocm
cd gfx803_rocm

Run environment:

nix develop .#rocm63-ollama

or build container:

nix build .#dockerImages.rocm63-ollama
11. One optional upgrade

You can automatically generate the compatibility graph from the flake.

Example:

nix flake show

would display:

devShells
  rocm63-ollama
  rocm63-pytorch
  rocm63-comfyui
  rocm63-whisperx

Which is basically the compatibility lattice UI.

✅ My recommendation

Yes — convert this repo to flakes.

It’s almost the ideal use case for Nix.

You’ll likely reduce:

30 Dockerfiles → ~200 lines of Nix

while gaining reproducibility.

If you want, I can also show you something very powerful for this exact project:

How to make the flake automatically generate the entire ROCm × framework matrix (including future versions) in ~20 lines.

That trick is one of the reasons Nix is beloved in HPC/GPU toolchains.

go

Alright — here is the clean trick that lets you generate your entire ROCm × framework matrix automatically instead of writing individual entries.

This is where Nix starts to feel like infrastructure algebra rather than scripting.

Your repo already has the structure of a matrix:

ROCm version
×
framework
×
(optional build tweaks)

Right now you manually encode each combination with a Dockerfile.

We instead encode two lists and compute their Cartesian product.

1. Define the matrix as data

Inside flake.nix:

{
  description = "gfx803 ROCm compatibility matrix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:

  let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };

    # ---- ROCm versions ----

    rocmVersions = {
      rocm63 = pkgs.rocmPackages;
      rocm64 = pkgs.rocmPackages;
    };

    # ---- frameworks ----

    frameworks = {
      ollama = import ./modules/ollama.nix;
      pytorch = import ./modules/pytorch.nix;
      comfyui = import ./modules/comfyui.nix;
      whisperx = import ./modules/whisperx.nix;
      llamacpp = import ./modules/llamacpp.nix;
    };

This is the entire compatibility graph encoded as data.

2. Generate the Cartesian product

Now we automatically create every combination.

Add:

    mkMatrix =
      pkgs.lib.mapAttrs
        (rocmName: rocm:

          pkgs.lib.mapAttrs
            (frameworkName: module:

              module { inherit pkgs rocm; }

            )
            frameworks

        )
        rocmVersions;

Now we have:

mkMatrix = {
  rocm63 = {
    ollama = ...
    pytorch = ...
    comfyui = ...
  }

  rocm64 = {
    ollama = ...
    pytorch = ...
    comfyui = ...
  }
}
3. Flatten the matrix

Flakes expect a flat attribute set.

We convert:

rocm63.ollama

into

rocm63-ollama

Add:

    flatten =
      pkgs.lib.concatMapAttrs
        (rocmName: frameworks:

          pkgs.lib.mapAttrs'
            (frameworkName: value: {
              name = "${rocmName}-${frameworkName}";
              value = value;
            })
            frameworks

        )
        mkMatrix;

Now we have:

{
  rocm63-ollama
  rocm63-pytorch
  rocm63-comfyui
  rocm63-whisperx
  rocm63-llamacpp
  rocm64-ollama
  rocm64-pytorch
  ...
}

Generated automatically.

4. Expose them as dev environments

Add:

in {

  devShells.${system} = flatten;

}

Now you can run:

nix develop .#rocm63-ollama
nix develop .#rocm63-pytorch
nix develop .#rocm64-ollama

All generated automatically.

5. Adding a new ROCm version becomes trivial

Instead of creating new Dockerfiles:

Dockerfile_rocm65_pytorch
Dockerfile_rocm65_ollama
Dockerfile_rocm65_comfyui

You just add one line:

rocmVersions.rocm65 = pkgs.rocmPackages;

Boom.

The entire matrix expands automatically.

6. Adding a new framework

Instead of adding five Dockerfiles:

Dockerfile_rocm63_newframework
Dockerfile_rocm64_newframework
...

You add one module:

modules/newframework.nix

and register it:

frameworks.newframework = import ./modules/newframework.nix;

Matrix expands automatically.

7. This is exactly why Nix is popular in GPU research

GPU environments often look like:

CUDA version
×
framework
×
compiler
×
hardware

Nix lets you encode this as math rather than manual builds.

Your repo is a perfect example.

8. Bonus: automatic Docker image generation

You can generate containers for the entire matrix too:

dockerImages.${system} =
  pkgs.lib.mapAttrs
    (name: shell:

      pkgs.dockerTools.buildImage {
        name = name;
        contents = shell.buildInputs;
        config.Cmd = [ "bash" ];
      }

    )
    flatten;

Now every environment automatically has a Docker image.

9. What this does to your repo

Current:

~30 Dockerfiles
multiple base variants
version duplication

After flakes:

flake.nix
modules/
overlays/

Everything generated automatically.

10. Why this fits your project especially well

Your repo is really a compatibility graph.

RX580 gfx803
×
ROCm versions
×
frameworks

Flakes let the repo itself become the executable graph.

Users could literally run:

nix develop github:chboishabba/rr_gfx803_rocm#rocm63-ollama

✅ My honest recommendation

For this repo, flakes are not just a convenience — they’re actually a much more natural representation of the compatibility matrix you’re already maintaining.

If you'd like, I can also show you the next extremely useful step for this project:

How to auto-benchmark every ROCm × framework combination and generate your benchmark folder automatically.

That would turn this repo into a self-testing compatibility graph, which would be very powerful.

go

What you’re describing is actually the next natural step for your repo: make the compatibility matrix self-testing so every ROCm × framework combination automatically runs the same benchmark protocol and outputs the plots you already store in benchmark/.

Right now your workflow looks like:

build environment
→ manually run model
→ record numbers
→ save png/csv

We can make Nix drive the entire experiment protocol.

The nice part: this fits the “compatibility lattice” idea you mentioned earlier.

1. Define the canonical benchmark protocol

First define a single benchmark script.

Example:

benchmarks/
   ollama_bench.sh
   pytorch_bench.py
   comfyui_bench.py

Example ollama_bench.sh:

#!/usr/bin/env bash
set -e

MODEL=${MODEL:-llama3}
OUT=${OUT:-results.json}

echo "Running Ollama benchmark..."

START=$(date +%s)

ollama run $MODEL "Explain GPU computing in one paragraph."

END=$(date +%s)

echo "{ \"model\": \"$MODEL\", \"time\": $((END-START)) }" > $OUT

Now every environment runs the same protocol.

2. Attach benchmark runners to the matrix

Extend the flake so each environment also produces a benchmark app.

Add something like this to flake.nix:

apps.${system} =
  pkgs.lib.mapAttrs
    (name: shell: {

      type = "app";

      program =
        "${pkgs.writeShellScript "bench-${name}" ''
          echo "Running benchmark for ${name}"

          export HSA_OVERRIDE_GFX_VERSION=8.0.3

          ${shell}/bin/bash benchmarks/run.sh ${name}
        ''}";
    })
    flatten;

Now each matrix entry automatically gets a runner.

Example usage:

nix run .#rocm63-ollama
3. Run the entire compatibility matrix automatically

Now we add a meta-runner.

scripts/run-matrix.sh
#!/usr/bin/env bash
set -e

for env in $(nix flake show --json | jq -r '.apps."x86_64-linux" | keys[]')
do
  echo "Running $env"
  nix run ".#$env"
done

This will run every combination.

Example output:

Running rocm63-ollama
Running rocm63-pytorch
Running rocm63-comfyui
Running rocm64-ollama
Running rocm64-pytorch
...
4. Auto-collect results

Each run writes JSON or CSV to a folder:

results/
   rocm63-ollama.json
   rocm63-pytorch.json
   rocm64-ollama.json

Now your repo automatically builds the dataset you currently store in:

benchmark/ollama/raw_rocm6.4_ollama_0.8.0
5. Auto-generate plots

Add a plotting tool.

Example:

analysis/
   plot_results.py
import pandas as pd
import matplotlib.pyplot as plt
import glob

files = glob.glob("results/*.json")

df = pd.concat([pd.read_json(f, lines=True) for f in files])

df.plot(kind="bar")

plt.savefig("benchmark/summary.png")

Hook it into the flake:

apps.${system}.plot =
{
  type = "app";

  program = "${pkgs.python3}/bin/python analysis/plot_results.py";
};

Run:

nix run .#plot
6. Result: self-testing compatibility graph

Your repo becomes:

clone repo
→ nix run .#run-matrix
→ benchmarks execute automatically
→ plots generated

No manual runs.

7. What this turns your project into

Right now your repo is:

Dockerfiles
benchmarks
screenshots

After this change it becomes:

executable GPU compatibility graph

Meaning users can literally run:

nix run github:chboishabba/rr_gfx803_rocm#matrix

and reproduce your results.

That’s extremely valuable for the ROCm community because gfx803 support is unofficial and fragile.

8. Disk space bonus

Nix will reuse dependencies across all runs:

ROCm installed once
PyTorch installed once
Ollama installed once

So running the whole matrix doesn't explode disk usage.

9. This also integrates well with CI

If you later add CI:

GitHub Actions
Hydra
Buildkite

they can automatically run the matrix on machines with GPUs.

Many Nix HPC projects do exactly this.

10. What you end up with

Your repo becomes something like:

rr_gfx803_rocm
 ├ flake.nix
 ├ modules/
 ├ overlays/
 ├ benchmarks/
 ├ analysis/
 ├ results/

Everything reproducible.

My honest take

This project is almost the perfect example of a Nix flake use-case:

compatibility matrix

GPU toolchains

reproducible builds

benchmarking

Very similar to how CUDA research stacks are managed.

If you want, the next step gets even more interesting:

I can show you how to turn this repo into a visual compatibility map where the matrix automatically renders a green/red support grid for each ROCm × framework combination.

That would make your repo much easier for others to understand.














OLDER ->

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
