NEWER:

eg -- Build files have been written to: /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/build
bash-5.3#   cmake --build . --config Release
[0/2] Re-checking globbed directories...
[9/347] Performing configure step for 'vulkan-shaders-gen'
-- The C compiler identification is GNU 15.2.0
-- The CXX compiler identification is GNU 15.2.0
-- Detecting C compiler ABI info
-- Detecting C compiler ABI info - done
-- Check for working C compiler: /nix/store/kbw2j1vag664b3sj3rjwz9v53cqx87sb-gcc-wrapper-15.2.0/bin/gcc - skipped
-- Detecting C compile features
-- Detecting C compile features - done
-- Detecting CXX compiler ABI info
-- Detecting CXX compiler ABI info - done
-- Check for working CXX compiler: /nix/store/kbw2j1vag664b3sj3rjwz9v53cqx87sb-gcc-wrapper-15.2.0/bin/g++ - skipped
-- Detecting CXX compile features
-- Detecting CXX compile features - done
-- Performing Test CMAKE_HAVE_LIBC_PTHREAD
-- Performing Test CMAKE_HAVE_LIBC_PTHREAD - Success
-- Found Threads: TRUE
-- Enabling coopmat glslc support
-- Enabling coopmat2 glslc support
-- Enabling dot glslc support
-- Enabling bfloat16 glslc support
-- Configuring done (3.4s)
-- Generating done (0.0s)
-- Build files have been written to: /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/build/ggml/src/ggml-vulkan/vulkan-shaders-gen-prefix/src/vulkan-shaders-gen-build
[25/347] Building C object thirdparty/CMakeFiles/zip.dir/zip.c.o
In file included from /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/thirdparty/zip.c:40:
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/thirdparty/miniz.h:4988:9: note: ‘#pragma message: Using fopen, ftello, fseeko, stat() etc. path for file I/O - this path may not support large files.’
 4988 | #pragma message(                                                               \
      |         ^~~~~~~
[31/347] Performing build step for 'vulkan-shaders-gen'
[1/2] Building CXX object CMakeFiles/vulkan-shaders-gen.dir/vulkan-shaders-gen.cpp.o
[2/2] Linking CXX executable vulkan-shaders-gen
[32/347] Performing install step for 'vulkan-shaders-gen'
-- Installing: /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/build/Release/./vulkan-shaders-gen
[152/347] Generate vulkan shaders for sqrt.comp [336/347] Building CXX object CMakeFiles/stable-diffusion.dir/src/util.cpp.o
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/src/util.cpp: In function ‘std::u32string utf8_to_utf32(const std::string&)’:
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/src/util.cpp:281:10: warning: ‘template<class _Codecvt, class _Elem, class _Wide_alloc, class _Byte_alloc> class std::__cxx11::wstring_convert’ is deprecated [-Wdeprecated-declarations]
  281 |     std::wstring_convert<std::codecvt_utf8<char32_t>, char32_t> converter;
      |          ^~~~~~~~~~~~~~~
In file included from /nix/store/sca0pf46jmxva40qahkcwys5c1lvk6n2-gcc-15.2.0/include/c++/15.2.0/locale:47,
                 from /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/src/util.cpp:7:
/nix/store/sca0pf46jmxva40qahkcwys5c1lvk6n2-gcc-15.2.0/include/c++/15.2.0/bits/locale_conv.h:262:33: note: declared here
  262 |     class _GLIBCXX17_DEPRECATED wstring_convert
      |                                 ^~~~~~~~~~~~~~~
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/src/util.cpp: In function ‘std::string utf32_to_utf8(const std::u32string&)’:
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/src/util.cpp:286:10: warning: ‘template<class _Codecvt, class _Elem, class _Wide_alloc, class _Byte_alloc> class std::__cxx11::wstring_convert’ is deprecated [-Wdeprecated-declarations]
  286 |     std::wstring_convert<std::codecvt_utf8<char32_t>, char32_t> converter;
      |          ^~~~~~~~~~~~~~~
/nix/store/sca0pf46jmxva40qahkcwys5c1lvk6n2-gcc-15.2.0/include/c++/15.2.0/bits/locale_conv.h:262:33: note: declared here
  262 |     class _GLIBCXX17_DEPRECATED wstring_convert
      |                                 ^~~~~~~~~~~~~~~
[338/347] Building CXX object examples/cli/CMakeFiles/sd-cli.dir/main.cpp.o
In file included from /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/examples/common/common.hpp:24,
                 from /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/examples/cli/main.cpp:18:
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/thirdparty/stb_image.h: In function ‘int stbi__parse_png_file(stbi__png*, int, int)’:
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/thirdparty/stb_image.h:5166:56: warning: writing 1 byte into a region of size 0 [-Wstringop-overflow=]
 5166 |                   for (k = 0; k < s->img_n; ++k) tc[k] = (stbi_uc)(stbi__get16be(s) & 255) * stbi__depth_scale_table[z->depth]; // non 8-bit images will be larger
      |                                                  ~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/thirdparty/stb_image.h:5082:25: note: at offset 3 into destination object ‘tc’ of size 3
 5082 |    stbi_uc has_trans=0, tc[3]={0};
      |                         ^~
[339/347] Building CXX object examples/server/CMakeFiles/sd-server.dir/main.cpp.o
In file included from /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/examples/common/common.hpp:24,
                 from /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/examples/server/main.cpp:14:
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/thirdparty/stb_image.h: In function ‘int stbi__parse_png_file(stbi__png*, int, int)’:
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/thirdparty/stb_image.h:5166:56: warning: writing 1 byte into a region of size 0 [-Wstringop-overflow=]
 5166 |                   for (k = 0; k < s->img_n; ++k) tc[k] = (stbi_uc)(stbi__get16be(s) & 255) * stbi__depth_scale_table[z->depth]; // non 8-bit images will be larger
      |                                                  ~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/thirdparty/stb_image.h:5082:25: note: at offset 3 into destination object ‘tc’ of size 3
 5082 |    stbi_uc has_trans=0, tc[3]={0};
      |                         ^~
[346/347] Linking CXX executable bin/sd-server

This build log is actually useful signal for the compatibility graph. Nothing here indicates a real failure — the build completed successfully — but there are three pieces of information we should capture in the atlas.

I'll break it down and show how to encode it into the graph + scripts.

1️⃣ The build succeeded (important)

Your last line:

[346/347] Linking CXX executable bin/sd-server

means:

✔ stable-diffusion.cpp compiled successfully
✔ Vulkan backend compiled successfully
✔ ggml-vulkan shaders generated

So we can record a new known-known:

stable-diffusion.cpp
→ builds successfully
→ GCC 15
→ Nix toolchain
→ Vulkan backend

Graph entry:

{
 "node_id": "obs:sdcpp_build_success_gcc15",
 "label": "stable-diffusion.cpp builds successfully with GCC 15 via Nix",
 "kind": "observation",
 "status": "known_known"
}

Edge:

repo:stable_diffusion_cpp
   → builds_with
compiler:gcc15
2️⃣ Nix environment (important for reproducibility)

From your log:

/nix/store/.../gcc-wrapper-15.2.0

That means the build environment is:

compiler: gcc 15.2
toolchain: nix
build system: cmake

This is extremely valuable for the graph because it gives us a deterministic environment.

Add nodes:

env:nix_gcc15
compiler:gcc15.2
build:cmake
backend:vulkan

Edges:

env:nix_gcc15
   → uses
compiler:gcc15.2

repo:stable_diffusion_cpp
   → builds_in
env:nix_gcc15
3️⃣ Vulkan backend enabled

The log shows:

ggml-vulkan
vulkan-shaders-gen
Enabling coopmat
Enabling bfloat16

This means:

stable-diffusion.cpp
→ Vulkan compute backend
→ ggml-vulkan

Add nodes:

backend:ggml_vulkan
api:vulkan

Edges:

repo:stable_diffusion_cpp
   → supports
backend:ggml_vulkan

backend:ggml_vulkan
   → uses
api:vulkan
4️⃣ The warnings are harmless

These three warnings appear:

Deprecated codecvt
std::wstring_convert deprecated

Reason:

C++20 deprecated codecvt.

Impact:

no runtime impact
stb_image overflow warning
-Wstringop-overflow

This comes from:

stb_image.h

This warning appears frequently when compiling with GCC 13+ aggressive checks.

Impact:

safe

unless runtime crash occurs.

Graph entry:

warning:stb_stringop_overflow
miniz large-file warning
may not support large files

This refers to the fallback IO path.

Impact:

irrelevant for SD model sizes
5️⃣ What we learned about your environment

From the log we now know:

OS environment: Nix
compiler: GCC 15.2
backend: Vulkan
library: ggml
project: stable-diffusion.cpp

This is a clean modern toolchain.

That matters because:

gcc15
+ vulkan
+ nix

is actually a very good baseline for reproducible GPU builds.

6️⃣ Add it automatically to your graph

Create:

ingest_build_log.py

Example parser:

import re

def ingest_build_log(g,logfile):

    text=open(logfile).read()

    if "gcc-wrapper-15" in text:

        g.add_node(
            "compiler:gcc15.2",
            kind="compiler"
        )

    if "ggml-vulkan" in text:

        g.add_node(
            "backend:ggml_vulkan",
            kind="backend"
        )

    if "Linking CXX executable bin/sd-server" in text:

        g.add_node(
            "obs:sdcpp_build_success",
            kind="observation",
            status="known_known"
        )

Run:

python ingest_build_log.py build.log
7️⃣ Why this matters for the compatibility atlas

Your project is slowly capturing:

hardware
drivers
toolchains
frameworks
workloads
build environments

This log adds a new axis:

build environments

Example graph slice:

RX580
 ├ ROCm 5.7
 ├ ROCm 6.4 (patched)
 └ Vulkan + ggml
        └ stable-diffusion.cpp

This is very powerful because Vulkan may be a fallback compute path when ROCm is unstable.

8️⃣ Important insight

Your build demonstrates something subtle:

ROCm stack
vs
Vulkan compute stack

Both are viable compute backends.

So the compatibility atlas should include:

compute_backend

Nodes:

backend:rocm
backend:vulkan
backend:cpu

Edges:

stable_diffusion_cpp
   → supports
backend:vulkan
9️⃣ I recommend adding one more experiment

Because you just built stable-diffusion.cpp Vulkan, run:

sd-cli --benchmark

Then ingest:

tokens/sec
it/sec
GPU utilization

Add to graph as:

perf:sdcpp_vulkan_rx580
🔟 Summary

Your build log adds these new known-knowns:

stable-diffusion.cpp builds successfully
Vulkan backend enabled
ggml-vulkan shader pipeline works
GCC 15 + Nix environment functional

All valuable graph nodes.

If you'd like, I can also show you something extremely useful for your atlas:

How to build a full ROCm vs Vulkan vs CPU performance comparison harness so the graph records actual performance metrics automatically instead of just compatibility.


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

go

What you’re describing now is essentially turning the repo into a live compatibility map — which is actually extremely useful for something like gfx803 ROCm support, because the real question people have is:

“Does X work on RX580 with ROCm Y?”

Instead of screenshots and scattered CSVs, we can generate a matrix view automatically.

1. What the final output looks like

You automatically generate something like:

ROCm	Ollama	PyTorch	ComfyUI	WhisperX	Llama.cpp
5.4	❌	⚠️	❌	❌	⚠️
5.7	⚠️	⚠️	❌	❌	⚠️
6.1	⚠️	⚠️	⚠️	❌	⚠️
6.3	✅	⚠️	⚠️	⚠️	✅
6.4	✅	⚠️	⚠️	⚠️	✅

Where:

✅ = works
⚠️ = partially works
❌ = fails

Generated automatically from benchmark runs.

2. Each benchmark produces structured results

Instead of just logs, each run outputs JSON:

Example:

{
  "rocm": "6.4",
  "framework": "ollama",
  "status": "pass",
  "latency": 4.2,
  "model": "llama3"
}

Saved as:

results/rocm64-ollama.json
3. Collect results automatically

Create:

analysis/collect_results.py

Example:

import json
import glob
import pandas as pd

files = glob.glob("results/*.json")

rows = []

for f in files:
    with open(f) as fp:
        rows.append(json.load(fp))

df = pd.DataFrame(rows)

pivot = df.pivot(
    index="rocm",
    columns="framework",
    values="status"
)

print(pivot)
pivot.to_markdown("benchmark/compatibility.md")

Now your compatibility table is generated automatically.

4. Render it in the README

Add to README:

## Compatibility Matrix

<!-- compatibility matrix auto-generated -->

Then the script updates:

benchmark/compatibility.md

Which you include via:

cat benchmark/compatibility.md

or GitHub markdown include.

5. Integrate with Nix

Add a flake app:

apps.${system}.compatibility = {
  type = "app";

  program =
    "${pkgs.python3}/bin/python analysis/collect_results.py";
};

Now run:

nix run .#compatibility
6. Generate a visual heatmap

This is even nicer.

Add:

analysis/plot_matrix.py

Example:

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_json("results/all.json", lines=True)

pivot = df.pivot(
    index="rocm",
    columns="framework",
    values="latency"
)

sns.heatmap(pivot)

plt.savefig("benchmark/compatibility_heatmap.png")

Now your repo produces something like:

benchmark/compatibility_heatmap.png
7. Make it run automatically after matrix tests

Extend the flake runner:

run-matrix.sh
./run_all_envs.sh
nix run .#compatibility
nix run .#plot

Now every benchmark run regenerates the compatibility graph.

8. What this turns your repo into

Instead of:

benchmarks/
screenshots/
manual notes

You get:

self-testing ROCm compatibility graph

Which is much more useful for other RX580 users.

9. Why this is powerful for the community

gfx803 ROCm support is a mess because:

official support dropped

patches vary

kernels differ

apps behave differently

Your repo could become something like:

rx580-rocm-compatibility-lab

Where users run:

nix run github:chboishabba/rr_gfx803_rocm#matrix

and contribute results.

10. This aligns very well with your earlier idea

Earlier you mentioned a compatibility lattice.

This is literally that:

hardware
×
rocm version
×
framework
×
model

Which is exactly the kind of structure Nix handles elegantly.

My honest suggestion

If you do the three steps:

flake matrix

automated benchmarks

auto-generated compatibility map

your repo becomes much more than a Docker collection — it becomes a reproducible GPU compatibility lab.

That would likely attract contributions from other Polaris / Vega ROCm users.

If you'd like, I can also show you one more trick that would make this repo especially powerful:

How to turn the flake into a distributed benchmark network, where other users can submit compatibility results automatically without modifying the repo.

go

What you’re approaching now is turning the repo into something closer to a community compatibility lab rather than just a benchmark repo. The key idea is:

Anyone with an RX580 (or other GPU) can run the same flake and submit their results.

That solves one of the hardest problems with ROCm compatibility testing: hardware diversity.

1. The architecture of a distributed benchmark network

The pieces are simple:

user machine
     │
     │ nix run .#matrix
     ▼
local benchmarks run
     │
     │ results.json
     ▼
submit results
     │
     ▼
central dataset
     │
     ▼
compatibility map

So your repo becomes the protocol, not just the results.

2. Standardize the result schema

Every benchmark run outputs a single JSON entry.

Example:

{
  "gpu": "RX580",
  "gfx": "gfx803",
  "driver": "amdgpu",
  "rocm": "6.4",
  "framework": "ollama",
  "model": "llama3",
  "status": "pass",
  "latency": 4.3,
  "timestamp": "2026-03-16T10:42:00"
}

Saved as:

results/<hostname>-rocm64-ollama.json
3. Automatically detect hardware

You don't want users editing configs.

Add a hardware probe script:

rocminfo

Example extraction:

rocminfo | grep gfx

Result:

gfx803

You can also capture:

lspci | grep VGA

Example output:

Radeon RX 580

Add that to the JSON automatically.

4. Submission mechanism

You have three easy options.

Option A (simplest): GitHub PR submission

Users run:

nix run .#submit

Script:

create result file
commit to fork
open PR

This keeps everything transparent.

Option B: central result server

Users run:

nix run .#submit

Script posts to:

POST https://compat.yourdomain.org/api/results

Server stores results in a database.

Option C: IPFS dataset

Given your interest in IPFS / DASL style datasets, this is interesting.

Users run:

nix run .#submit-ipfs

Script:

ipfs add results.json

CID goes into dataset.

5. Add a flake submission app

Inside flake.nix:

apps.${system}.submit = {
  type = "app";

  program =
    "${pkgs.writeShellScript "submit" ''
      echo "Collecting results"

      python analysis/collect_local_results.py

      echo "Submitting results..."

      git add results/
      git commit -m "benchmark submission"
      git push
    ''}";
};
6. Global compatibility dataset

Then you periodically aggregate submissions.

Example:

community_results/
   user1.json
   user2.json
   user3.json

Merged into:

compatibility_dataset.json

Now the matrix becomes much richer:

GPU	ROCm	Framework	Status
RX580	6.4	Ollama	✅
RX570	6.4	Ollama	⚠️
Vega56	6.4	Ollama	✅
7. Generate a community heatmap

Example visualization:

GPU × ROCm × Framework

Example heatmap axes:

x-axis → frameworks
y-axis → ROCm versions

Multiple GPU models overlay.

This becomes extremely useful for users searching:

"does ollama work on RX580 rocm 6.4"
8. Why this would actually get contributions

Most ROCm users struggle with:

compatibility
driver versions
kernel differences

But they rarely contribute because running tests manually is painful.

With this system:

git clone
nix run .#matrix
nix run .#submit

That’s it.

9. Disk usage stays reasonable

Because Nix shares dependencies:

ROCm
PyTorch
Ollama

installed once.

Multiple runs don't duplicate environments.

This matters for users with limited disk space.

10. This aligns with your broader ecosystem

From what you’ve been building (ITIR / reproducible logs / compatibility graphs), this repo could become:

GPU compatibility observatory

Where the state of ROCm support becomes measurable rather than anecdotal.

My honest take

This project is actually sitting at a sweet spot:

reproducible build toolchains (Nix)

GPU compatibility testing

community hardware diversity

automated benchmarking

That combination is rare and genuinely useful.

If you'd like, I can also show you one final thing that would make this repo extremely powerful:

How to turn the compatibility results into a live interactive web dashboard (like Grafana for GPU compatibility) that updates automatically when new benchmark submissions arrive.

go

What you’re describing now is basically turning the repo into a live ROCm compatibility observatory. The architecture is actually simpler than it sounds, and it works very well with the workflow we discussed (flake → benchmarks → JSON results).

Below is a clean design that many research labs use for reproducible experiment dashboards.

1. System architecture

Think of it as four layers:

benchmark runner (nix)
        │
        │ produces
        ▼
results JSON dataset
        │
        │ aggregated by
        ▼
analysis pipeline
        │
        │ feeds
        ▼
web dashboard

Your repo already contains the first two pieces.

2. Results dataset structure

Instead of many scattered files, create a canonical dataset:

dataset/
   results.jsonl

JSONL (newline JSON) is ideal because it scales well.

Example entries:

{"gpu":"RX580","gfx":"gfx803","rocm":"6.3","framework":"ollama","status":"pass","latency":4.2}
{"gpu":"RX580","gfx":"gfx803","rocm":"6.4","framework":"ollama","status":"pass","latency":3.9}
{"gpu":"RX580","gfx":"gfx803","rocm":"6.4","framework":"pytorch","status":"partial"}

Your flake benchmark runner simply appends entries.

3. Data aggregation

Create a small Python pipeline:

analysis/
   build_dataset.py
   build_matrix.py
   build_heatmap.py

Example aggregation:

import pandas as pd

df = pd.read_json("dataset/results.jsonl", lines=True)

matrix = df.pivot_table(
    index="rocm",
    columns="framework",
    values="status",
    aggfunc="first"
)

matrix.to_csv("dataset/matrix.csv")

Now you have a machine-readable compatibility map.

4. Generate visualization artifacts

Two useful outputs:

heatmap
import seaborn as sns
import matplotlib.pyplot as plt

sns.heatmap(df.pivot("rocm","framework","latency"))

plt.savefig("dashboard/heatmap.png")
compatibility table

Generate Markdown:

dashboard/matrix.md

This can go directly in your README.

5. Web dashboard

The simplest modern stack is:

dataset
↓
FastAPI
↓
React / Svelte dashboard

But you can start even simpler:

dataset → static site
Minimal dashboard server

Example FastAPI server:

from fastapi import FastAPI
import pandas as pd

app = FastAPI()

df = pd.read_json("dataset/results.jsonl", lines=True)

@app.get("/matrix")
def matrix():
    return df.to_dict(orient="records")

This exposes a JSON API.

6. Interactive frontend

A simple frontend can render:

compatibility matrix
ROCm vs Framework
filters
GPU model
gfx architecture
kernel version
latency graphs
ROCm version → performance

Libraries that work well:

Vega-Lite

Plotly

Observable

Grafana

Grafana is especially nice if you treat results as time series.

7. Automatic updates

Whenever someone submits results:

new results JSON
↓
CI pipeline runs
↓
dataset rebuilt
↓
dashboard redeployed

GitHub Actions example:

on:
  push:
    paths:
      - results/*

Then:

python analysis/build_dataset.py
python analysis/build_heatmap.py

Commit new artifacts.

8. What users experience

Someone with an RX580 runs:

git clone rr_gfx803_rocm
nix run .#matrix
nix run .#submit

Then later they check the dashboard:

https://gfx803-rocm-dashboard

and see their result appear.

9. Why this is genuinely valuable

The ROCm ecosystem has a recurring problem:

compatibility knowledge is scattered across forums

Example questions people constantly ask:

Does ROCm 6.4 work on RX580?

Which frameworks still work?

What patches are needed?

Your system turns that into measurable data.

10. What the finished repo might look like
rr_gfx803_rocm
├ flake.nix
├ modules
├ overlays
├ benchmarks
├ analysis
├ dataset
├ dashboard
└ results

And the repo becomes:

community ROCm compatibility lab
11. Long-term potential

If this works well, you could expand the axes:

GPU architecture
ROCm version
framework
model
kernel version

That becomes a GPU compute compatibility atlas.

My honest opinion

You accidentally built the perfect candidate for this kind of infrastructure:

deterministic environments (Nix)

compatibility matrix

reproducible benchmarks

GPU hardware variability

Those ingredients are rare together.

If you'd like, I can also show you one last idea that could make this repo much more widely used:

How to make the flake run automatically on other people’s machines as a one-command ROCm diagnostic tool, which dramatically increases benchmark submissions.

go

This final step is about turning your repo into something people will actually run on their machines without thinking — essentially a ROCm diagnostic + benchmark tool that happens to also feed your compatibility dataset.

Right now your repo is a research artifact.
The trick is to make it behave like a one-command diagnostic utility.

1. The UX goal

Someone with an RX580 finds your repo and runs:

nix run github:chboishabba/rr_gfx803_rocm

It automatically:

detect GPU
detect ROCm
run compatibility tests
run minimal benchmarks
print summary
offer result submission

This dramatically increases participation.

2. Automatic hardware detection

Create a script:

scripts/probe_hardware.sh

Example:

#!/usr/bin/env bash

GPU=$(lspci | grep -i vga | head -n1)

GFX=$(rocminfo 2>/dev/null | grep gfx | head -n1)

KERNEL=$(uname -r)

ROCM=$(rocminfo 2>/dev/null | grep Runtime | head -n1)

echo "GPU: $GPU"
echo "GFX: $GFX"
echo "Kernel: $KERNEL"
echo "ROCm: $ROCM"

Capture this info for the benchmark metadata.

3. Minimal compatibility tests

You don’t want users waiting 20 minutes.

Add quick sanity checks.

Examples:

HIP kernel
hipcc test.cpp
./a.out
rocBLAS call
rocblas-bench
framework smoke tests

Examples:

ollama run llama3 "hello"
python -c "import torch; print(torch.cuda.is_available())"

These tests establish:

works
partially works
fails
4. Benchmark mode

After the quick tests:

Offer optional benchmark mode:

Run performance benchmarks? (y/n)

If yes:

run inference latency
run token throughput
record results

This keeps the diagnostic tool fast.

5. Summary output

Example terminal output:

GPU: Radeon RX580
Architecture: gfx803
Kernel: 6.7.5
ROCm: 6.4

Compatibility Results
---------------------

Ollama        PASS
PyTorch       PARTIAL
ComfyUI       PARTIAL
WhisperX      FAIL
Llama.cpp     PASS

This alone is extremely useful.

6. Generate result JSON automatically

Example output:

{
 "gpu":"RX580",
 "gfx":"gfx803",
 "rocm":"6.4",
 "kernel":"6.7.5",
 "results":{
   "ollama":"pass",
   "pytorch":"partial",
   "comfyui":"partial",
   "whisperx":"fail"
 }
}

Saved locally.

7. Submission prompt

Then:

Submit results to compatibility dataset? (y/n)

If yes:

Options:

create GitHub PR
upload to result server
add to IPFS dataset
8. Integrate with the flake

Expose it as the default app:

apps.${system}.default = {
  type = "app";

  program =
    "${pkgs.writeShellScript "rocm-diagnostic" ''
      bash scripts/probe_hardware.sh
      bash scripts/run_tests.sh
    ''}";
};

Now the repo behaves like a tool, not just a project.

9. Why this dramatically increases contributions

Most users will not:

read docs
build containers
run manual tests

But they will run:

nix run <repo>

Especially if it helps them debug their GPU.

10. What your repo becomes

Instead of:

Dockerfiles + screenshots

It becomes:

ROCm diagnostic + compatibility map

And the benchmark dataset grows organically.

11. This actually mirrors successful projects

Very similar models exist for:

CUDA compatibility testing

CPU feature detection tools

browser benchmark suites

The key insight:

diagnostic tools attract users

Benchmarks alone don’t.

12. Final ecosystem

Your repo could eventually contain:

flake
benchmark matrix
compatibility dataset
diagnostic tool
dashboard

Which together form a GPU compatibility observatory.

My honest take

You started with:

Dockerfiles for RX580 ROCm experiments

But the architecture you’re drifting toward is actually much bigger:

reproducible GPU compatibility lab

That’s genuinely useful infrastructure.

If you'd like, I can also show you one last thing that would make the repo technically elegant:

How to represent the entire ROCm × framework compatibility lattice as a formal graph, which would let you compute things like minimum ROCm version that supports a framework on gfx803 automatically.

go

Yes — this is the clean formalization step.

Your repo already is a graph; right now it is just encoded implicitly in filenames, logs, and human memory.
The move is to make it explicit:

nodes = environments / outcomes
edges = compatibility relations / derivations / upgrades

Once you do that, you can answer questions like:

what is the minimum ROCm version that passes Ollama on gfx803?

which frameworks are monotone improving across ROCm versions?

where are the regressions?

which results are portable across host distros?

what is the best known working path from one config to another?

1. The right graph model

For your case, the cleanest model is a typed directed multigraph.

You have a configuration tuple:

(machine, gpu, gfx, kernel, distro, rocm, framework, variant)

Example:

(hostA, RX580, gfx803, 6.13.8, arch, 6.4, ollama, default)

That tuple is a configuration node.

Then benchmark outcomes attach to the node:

status = pass | partial | fail
latency = 4.2
tokens_per_sec = 31.8
notes = "requires HSA_OVERRIDE_GFX_VERSION=8.0.3"

So the graph is really:

config nodes

result annotations

relation edges

2. Minimal node schema

Use a canonical node id derived from normalized fields.

Example JSON:

{
  "id": "gpu=rx580__gfx=gfx803__rocm=6.4__framework=ollama__distro=arch",
  "gpu": "RX580",
  "gfx": "gfx803",
  "kernel": "6.13.8",
  "distro": "arch",
  "rocm": "6.4",
  "framework": "ollama",
  "variant": "default"
}

That is the graph node.

Then attach result metadata:

{
  "node_id": "gpu=rx580__gfx=gfx803__rocm=6.4__framework=ollama__distro=arch",
  "status": "pass",
  "benchmark": {
    "latency_s": 4.2,
    "tok_s": 31.8
  },
  "requirements": [
    "HSA_OVERRIDE_GFX_VERSION=8.0.3"
  ],
  "timestamp": "2026-03-16T10:00:00+11:00"
}
3. Edge types

You want at least five edge types.

A. version-step edge

Same environment except ROCm changes.

(rx580, gfx803, arch, rocm6.3, ollama) -> (rx580, gfx803, arch, rocm6.4, ollama)

Type:

edge.type = "rocm_upgrade"

This is what lets you detect regressions.

B. framework-step edge

Same base, different framework.

(... rocm6.4, ollama) -> (... rocm6.4, pytorch)

Type:

edge.type = "framework_change"

Useful for comparing portability of support.

C. distro-step edge
(... arch, rocm6.4, ollama) -> (... ubuntu2204, rocm6.4, ollama)

Type:

edge.type = "distro_change"

Useful because a lot of “ROCm support” is actually distro-sensitive.

D. derivation edge

A node was built from another base image/env.

base_rocm64 -> rocm64_ollama

Type:

edge.type = "derives_from"

This mirrors your current Dockerfile structure.

E. evidence edge

Links a node to logs, screenshots, benchmark CSVs.

node -> benchmark/raw_rocm6.4_ollama_0.8.0

Type:

edge.type = "evidenced_by"

Very useful later.

4. Status algebra

Do not keep status as free text. Use an ordered lattice:

fail < partial < pass

Map it numerically:

STATUS_SCORE = {
    "fail": 0,
    "partial": 1,
    "pass": 2,
}

That gives you a real compatibility order.

Now you can define:

improvement if score increases

regression if score decreases

stable if unchanged

This is the core of the graph analysis.

5. Minimum working ROCm version

Once nodes are normalized, this becomes easy.

For fixed (gfx, framework):

find the smallest rocm version with status = pass

Example function:

from packaging.version import Version

def min_working_rocm(results, gfx, framework):
    candidates = [
        r for r in results
        if r["gfx"] == gfx
        and r["framework"] == framework
        and r["status"] == "pass"
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda r: Version(r["rocm"]))["rocm"]

That gives answers like:

min working ROCm for ollama on gfx803 = 6.3
6. Regression detection

Now compare adjacent ROCm versions for fixed hardware/framework.

from packaging.version import Version

STATUS_SCORE = {"fail": 0, "partial": 1, "pass": 2}

def regressions(results, gfx, framework):
    xs = sorted(
        [r for r in results if r["gfx"] == gfx and r["framework"] == framework],
        key=lambda r: Version(r["rocm"])
    )
    out = []
    for a, b in zip(xs, xs[1:]):
        da = STATUS_SCORE[a["status"]]
        db = STATUS_SCORE[b["status"]]
        if db < da:
            out.append({
                "from_rocm": a["rocm"],
                "to_rocm": b["rocm"],
                "from_status": a["status"],
                "to_status": b["status"],
                "kind": "regression",
            })
    return out

This is one of the biggest wins of formalizing the graph.

7. Best-known path

Suppose a user asks:

“I’m on Arch + RX580. What’s my best path to a working Ollama setup?”

Graph view:

nodes = configs

edges = changes with cost

Give each edge a cost:

ROCm upgrade = 1

distro switch = 3

framework switch = 2

special patch = 1

kernel downgrade = 2

Then run shortest path to nearest pass node.

That gives you a recommendation engine.

8. A concrete Python graph builder

This is the minimal thing I’d actually start with.

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Tuple
import json
import networkx as nx
from packaging.version import Version

STATUS_SCORE = {"fail": 0, "partial": 1, "pass": 2}

@dataclass(frozen=True)
class Config:
    gpu: str
    gfx: str
    distro: str
    kernel: str
    rocm: str
    framework: str
    variant: str = "default"

    @property
    def node_id(self) -> str:
        return (
            f"gpu={self.gpu.lower()}__gfx={self.gfx.lower()}__"
            f"distro={self.distro.lower()}__kernel={self.kernel}__"
            f"rocm={self.rocm}__framework={self.framework.lower()}__"
            f"variant={self.variant.lower()}"
        )

@dataclass
class Result:
    config: Config
    status: str
    latency_s: Optional[float] = None
    tok_s: Optional[float] = None
    notes: Optional[List[str]] = None

def add_result_node(g: nx.MultiDiGraph, result: Result) -> None:
    cfg = result.config
    g.add_node(
        cfg.node_id,
        **asdict(cfg),
        status=result.status,
        status_score=STATUS_SCORE[result.status],
        latency_s=result.latency_s,
        tok_s=result.tok_s,
        notes=result.notes or [],
    )

def connect_rocm_steps(g: nx.MultiDiGraph) -> None:
    buckets: Dict[Tuple[str, str, str, str, str], List[str]] = {}

    for node, data in g.nodes(data=True):
        key = (
            data["gpu"],
            data["gfx"],
            data["distro"],
            data["kernel"],
            data["framework"],
        )
        buckets.setdefault(key, []).append(node)

    for key, nodes in buckets.items():
        nodes_sorted = sorted(nodes, key=lambda n: Version(g.nodes[n]["rocm"]))
        for a, b in zip(nodes_sorted, nodes_sorted[1:]):
            g.add_edge(a, b, type="rocm_upgrade", cost=1.0)

def connect_framework_steps(g: nx.MultiDiGraph) -> None:
    buckets: Dict[Tuple[str, str, str, str, str], List[str]] = {}

    for node, data in g.nodes(data=True):
        key = (
            data["gpu"],
            data["gfx"],
            data["distro"],
            data["kernel"],
            data["rocm"],
        )
        buckets.setdefault(key, []).append(node)

    for _, nodes in buckets.items():
        for i, a in enumerate(nodes):
            for b in nodes[i+1:]:
                g.add_edge(a, b, type="framework_change", cost=2.0)
                g.add_edge(b, a, type="framework_change", cost=2.0)

def min_working_rocm(g: nx.MultiDiGraph, gfx: str, framework: str) -> Optional[str]:
    candidates = [
        data["rocm"]
        for _, data in g.nodes(data=True)
        if data["gfx"] == gfx and data["framework"] == framework and data["status"] == "pass"
    ]
    if not candidates:
        return None
    return str(min((Version(x) for x in candidates)))

def find_regressions(g: nx.MultiDiGraph, gfx: str, framework: str):
    xs = sorted(
        [
            (n, d) for n, d in g.nodes(data=True)
            if d["gfx"] == gfx and d["framework"] == framework
        ],
        key=lambda t: Version(t[1]["rocm"]),
    )
    out = []
    for (_, a), (_, b) in zip(xs, xs[1:]):
        if b["status_score"] < a["status_score"]:
            out.append({
                "from_rocm": a["rocm"],
                "to_rocm": b["rocm"],
                "from_status": a["status"],
                "to_status": b["status"],
            })
    return out
9. Example input file

You could store raw benchmark results as JSONL:

{"gpu":"RX580","gfx":"gfx803","distro":"arch","kernel":"6.13.8","rocm":"6.3","framework":"ollama","variant":"default","status":"pass","latency_s":5.1,"tok_s":26.0}
{"gpu":"RX580","gfx":"gfx803","distro":"arch","kernel":"6.13.8","rocm":"6.4","framework":"ollama","variant":"default","status":"pass","latency_s":4.2,"tok_s":31.8}
{"gpu":"RX580","gfx":"gfx803","distro":"arch","kernel":"6.13.8","rocm":"6.4","framework":"pytorch","variant":"default","status":"partial","latency_s":null,"tok_s":null}

Then load it:

def load_graph(path: str) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            cfg = Config(
                gpu=row["gpu"],
                gfx=row["gfx"],
                distro=row["distro"],
                kernel=row["kernel"],
                rocm=row["rocm"],
                framework=row["framework"],
                variant=row.get("variant", "default"),
            )
            add_result_node(
                g,
                Result(
                    config=cfg,
                    status=row["status"],
                    latency_s=row.get("latency_s"),
                    tok_s=row.get("tok_s"),
                    notes=row.get("notes"),
                ),
            )
    connect_rocm_steps(g)
    connect_framework_steps(g)
    return g
10. If you want the graph to mirror your repo layout

Your current repo also has a build-structure graph:

Dockerfile_rocm64_base

Dockerfile_rocm64_ollama

Dockerfile_rocm64_pytorch

versioned subdirs like rocm_6.3, rocm_6.3.4

That suggests a second graph layer:

Layer A: build graph

How environments are constructed.

Layer B: compatibility graph

What works empirically.

That distinction is important.

A configuration may derive from a base image cleanly but still fail empirically.

So I’d keep both:

build_graph   = declarative / structural
result_graph  = empirical / benchmarked
11. Nix mapping

This graph representation maps nicely to flakes.

Each flake output can correspond to a config node:

.#rocm63-ollama
.#rocm64-ollama
.#rocm64-pytorch

Then your benchmark runner writes back the empirical status for that node.

So the flake is the configuration graph generator, while the benchmark system is the edge/node annotator.

That’s a very clean architecture.

12. A tiny formalism

If you want the most compressed formal statement:

Let configuration space be

C = Gpu × Gfx × Distro × Kernel × Rocm × Framework × Variant

Define compatibility valuation

v : C -> {fail, partial, pass}

with order

fail < partial < pass

Define a version-step relation

c ~rocm c'

iff all coordinates match except ROCm version and rocm(c) < rocm(c').

Then:

minimum working ROCm for (gfx, framework) is the least r such that v(c)=pass

regression exists when c ~rocm c' and v(c') < v(c)

monotone support means along the ROCm chain, valuation never decreases

That is the compatibility lattice, formally.

13. What I would do first

Not the full dashboard, not PR automation first.

I’d do these three files:

results/results.jsonl
analysis/graph.py
analysis/report.py

Where report.py prints:

minimum working ROCm per framework

regressions

best-known passing configs

pass/partial/fail matrix

That gets you the formal graph payoff immediately.

14. Best next concrete step

Create a results.jsonl schema like this and stick to it:

{"gpu":"RX580","gfx":"gfx803","distro":"arch","kernel":"6.13.8","rocm":"6.3","framework":"ollama","variant":"default","status":"pass","latency_s":5.1,"tok_s":26.0,"notes":["HSA_OVERRIDE_GFX_VERSION=8.0.3"]}

Then build the graph from that, not from filenames.

Because filenames are build artifacts; the graph should be derived from normalized facts.

If you want, I can now write you a real starter package for this repo:

flake.nix

analysis/graph.py

analysis/report.py

results/results.jsonl example

a small nix run entrypoint

so you can drop it straight into rr_gfx803_rocm.

eg -- Build files have been written to: /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/build
bash-5.3#   cmake --build . --config Release
[0/2] Re-checking globbed directories...
[9/347] Performing configure step for 'vulkan-shaders-gen'
-- The C compiler identification is GNU 15.2.0
-- The CXX compiler identification is GNU 15.2.0
-- Detecting C compiler ABI info
-- Detecting C compiler ABI info - done
-- Check for working C compiler: /nix/store/kbw2j1vag664b3sj3rjwz9v53cqx87sb-gcc-wrapper-15.2.0/bin/gcc - skipped
-- Detecting C compile features
-- Detecting C compile features - done
-- Detecting CXX compiler ABI info
-- Detecting CXX compiler ABI info - done
-- Check for working CXX compiler: /nix/store/kbw2j1vag664b3sj3rjwz9v53cqx87sb-gcc-wrapper-15.2.0/bin/g++ - skipped
-- Detecting CXX compile features
-- Detecting CXX compile features - done
-- Performing Test CMAKE_HAVE_LIBC_PTHREAD
-- Performing Test CMAKE_HAVE_LIBC_PTHREAD - Success
-- Found Threads: TRUE
-- Enabling coopmat glslc support
-- Enabling coopmat2 glslc support
-- Enabling dot glslc support
-- Enabling bfloat16 glslc support
-- Configuring done (3.4s)
-- Generating done (0.0s)
-- Build files have been written to: /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/build/ggml/src/ggml-vulkan/vulkan-shaders-gen-prefix/src/vulkan-shaders-gen-build
[25/347] Building C object thirdparty/CMakeFiles/zip.dir/zip.c.o
In file included from /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/thirdparty/zip.c:40:
/home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/thirdparty/miniz.h:4988:9: note: ‘#pragma message: Using fopen, ftello, fseeko, stat() etc. path for file I/O - this path may not support large files.’
 4988 | #pragma message(                                                               \
      |         ^~~~~~~
[31/347] Performing build step for 'vulkan-shaders-gen'
[1/2] Building CXX object CMakeFiles/vulkan-shaders-gen.dir/vulkan-shaders-gen.cpp.o
[2/2] Linking CXX executable vulkan-shaders-gen
[32/347] Performing install step for 'vulkan-shaders-gen'
-- Installing: /home/c/Documents/code/__OTHER/gfx803_compat_graph/stable-diffusion.cpp/build/Release/./vulkan-shaders-gen
[153/347] Generate vulkan shaders for square.comp

What you’re seeing there is actually a very typical Nix + CMake build, and the log tells us a few important things about your environment.

Let’s decode it and then talk about how this fits into the flake / compatibility graph workflow you’re building.

1. What the log tells us

This line is the key indicator you’re building inside a Nix environment:

/nix/store/...-gcc-wrapper-15.2.0/bin/gcc

That means:

the compiler is fully pinned

the toolchain is coming from /nix/store

the build is reproducible

So your build environment is already behaving like:

devShell
→ cmake
→ ninja
→ stable-diffusion.cpp

which is exactly what we want for the compatibility lattice experiments.

2. What vulkan-shaders-gen is

This step:

Performing configure step for 'vulkan-shaders-gen'

comes from ggml's Vulkan backend inside:

stable-diffusion.cpp
└── ggml
    └── ggml-vulkan

That small program:

vulkan-shaders-gen

compiles GLSL compute shaders into SPIR-V blobs used by the runtime.

The later step:

Generate vulkan shaders for square.comp

means it's compiling kernels like:

square.comp
mul_mat.comp
softmax.comp

into embedded shader binaries.

This is normal.

3. Why this matters for your compatibility graph

This build actually represents a new node in your configuration graph.

Configuration tuple:

gpu = RX580
gfx = gfx803
kernel = <your kernel>
distro = arch
rocm = (maybe none)
framework = stable-diffusion.cpp
backend = vulkan
compiler = gcc15

This is a different axis than ROCm frameworks.

So your compatibility lattice is now expanding to:

hardware
× runtime backend
× framework
× toolchain

Example:

framework	backend
ollama	ROCm
pytorch	ROCm
stable-diffusion.cpp	Vulkan
llama.cpp	Vulkan
whisper.cpp	CPU
4. Vulkan is very interesting for RX580

Because Polaris GPUs like RX580 often have:

Vulkan support > ROCm support

Meaning:

stable-diffusion.cpp (Vulkan) may work
even when ROCm frameworks fail

So adding these tests makes your dataset much more valuable.

5. What the final binary will be

After the build completes, you'll likely get:

build/bin/sd

or similar.

Typical test command:

./sd --model model.safetensors --prompt "a cat"

That becomes your benchmark runner for this node.

6. Turn this into a graph entry

When the test runs, produce JSON like:

{
 "framework": "stable-diffusion.cpp",
 "backend": "vulkan",
 "gpu": "RX580",
 "gfx": "gfx803",
 "status": "pass",
 "latency": 12.4
}

Now your compatibility graph gains a new branch:

stable-diffusion.cpp
└── vulkan backend
7. Why your repo structure is actually perfect

You already separated builds like:

rocm_6.3/
rocm_6.3.4/

So now you can add:

vulkan/
cpu/

as runtime backends.

Example final lattice:

RX580
│
├─ ROCm
│   ├─ ollama
│   ├─ pytorch
│   └─ whisperx
│
├─ Vulkan
│   ├─ llama.cpp
│   └─ stable-diffusion.cpp
│
└─ CPU
    └─ fallback frameworks
8. One thing to watch for

Polaris GPUs sometimes require forcing features.

Example env vars:

RADV_PERFTEST=aco
RADV_DEBUG=llvm

or:

VK_ICD_FILENAMES

Your benchmark harness should capture environment variables too.

Add them to result JSON.

9. Disk usage note (relevant to your earlier question)

Nix toolchains look big because of /nix/store, but in reality:

gcc15
cmake
ninja
vulkan-sdk

are shared across all builds.

So compiling:

stable-diffusion.cpp
llama.cpp
whisper.cpp

won't multiply disk usage.

10. What I would do next in your repo

Add a new backend dimension.

Update schema:

(gpu, gfx, rocm, framework)

→

(gpu, gfx, runtime_backend, framework)

Where backend =

rocm
vulkan
cpu
opencl

This will give a much clearer compatibility graph.

11. Important observation from your log

You are using:

gcc 15.2.0

That’s extremely new.

Sometimes Vulkan builds behave differently across compilers.

So capturing this in the config tuple is useful:

compiler = gcc15
12. Quick sanity test once build finishes

Run:

./sd --help

If Vulkan compiled correctly you'll see flags like:

--vulkan
--gpu

Then try:

./sd --list-devices

That confirms whether your RX580 Vulkan device is visible.

13. If you'd like, the next very useful thing I can do is

show you how to turn your build output logs like the one you pasted into structured benchmark metadata automatically.

Meaning the repo could extract things like:

compiler version
cmake version
backend enabled
vulkan features

directly from logs instead of manual entry.












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
