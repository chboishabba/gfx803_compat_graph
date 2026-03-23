# Nix migration checklist from the working gfx803 Docker line

This note translates the original working Ubuntu `ROCm 6.4` Dockerfiles from `rr_gfx803_rocm` into a Nix-first migration plan.

The intent is not to preserve the Dockerfiles as the delivery mechanism. The intent is to preserve the parts that made gfx803 work, then rebuild them in a form that is easier to upgrade, compare, cache, and share.

If the first Nix-owned framework rebuild lane blocks, the fallback is still to extract or rebuild from the known working Robert container lineage and feed those results back into the Nix graph. That fallback should stay documented, but it is not the primary path.

## Source of truth

The working reference recipe came from the original Ubuntu `6.4` Dockerfiles in `../rr_gfx803_rocm/`:

- `Dockerfile_rocm64_base`
- `Dockerfile_rocm64_pytorch`
- `Dockerfile_rocm64_comfyui`
- `Dockerfile_rocm64_whisperx`
- `Dockerfile_rocm64_ollama`

These are treated here as:

- proof that a working gfx803 PyTorch-era stack existed
- a record of required environment, patches, and build order
- not the long-term packaging target

## Current decision

Start with PyTorch before Ollama.

That means the first Nix-owned target is the shared gfx803 PyTorch stack:

- rebuilt PyTorch
- rebuilt TorchVision
- rebuilt TorchAudio
- the minimum runtime/math layers needed to load and use them on Polaris

Ollama remains a later consumer of that graph, not the first artifact boundary.

Do not touch the control lane while doing this.

The intended flake surface is:

- control stack:
  - frozen known-working Python/framework layer
  - known-working selected runtime/math layer
- upgrade stack:
  - the same frozen Python/framework layer
  - newer runtime/math layers underneath it

That keeps attribution clean. If the upgrade stack breaks, the change is in ROCm/runtime space, not in the Python/framework layer.

## 1. Exact working gfx803 recipe to preserve

These are the inputs that look materially tied to getting the original stack working.

### Runtime environment

- `HSA_OVERRIDE_GFX_VERSION=8.0.3`
- `ROC_ENABLE_PRE_VEGA=1`
- `PYTORCH_ROCM_ARCH=gfx803`
- `ROCM_ARCH=gfx803`
- `TORCH_BLAS_PREFER_HIPBLASLT=0`
- `USE_ROCM=1`
- `FORCE_CUDA=1`
- `USE_NINJA=1`

These belong in runtime wrappers and build derivations, not in ad hoc shell history.

### Rebuilt math/runtime stack

- `rocBLAS` was rebuilt for `gfx803` in the original base image
- PyTorch was rebuilt from ROCm source, not taken from stock wheels
- TorchVision and TorchAudio were rebuilt against that rebuilt PyTorch
- Ollama required its own source patching plus a compatible ROCm userspace

This means the Nix target is not “use upstream binaries with a couple env vars.” It is “control the build graph.”

### Application-specific source changes

#### Ollama

From the original Docker line:

- patch `discover/gpu.go` so `RocmComputeMajorMin` accepts gfx803 by lowering the expected major/minor gate
- comment out `find_package(hip REQUIRED)` in `CMakeLists.txt`

These should become explicit patch files in Nix, not inline `sed` edits.

#### PyTorch build hygiene learned later

From the newer repo context and later build path:

- keep `PYTHONNOUSERSITE=1` for the TorchVision build
- keep `PYTHONPATH` empty for the TorchVision build
- avoid leaving the PyTorch source tree visible after installing the built wheel

These are not cosmetic. They prevent the `RpcBackendOptions` duplicate-`torch` import failure.

## 2. Essential vs historical workarounds

Not everything in the Dockerfiles should be carried into Nix unchanged.

### Essential to preserve first

- gfx803 runtime env:
  - `HSA_OVERRIDE_GFX_VERSION=8.0.3`
  - `ROC_ENABLE_PRE_VEGA=1`
  - `PYTORCH_ROCM_ARCH=gfx803`
  - `ROCM_ARCH=gfx803`
  - `TORCH_BLAS_PREFER_HIPBLASLT=0`
- rebuilt `rocBLAS` for gfx803
- rebuilt PyTorch/TorchVision/TorchAudio stack
- explicit Ollama source patches
- isolated TorchVision build environment

If these are missing, we are not really reproducing the known working path.

### Useful but secondary

- `amdgpu_top`
- `tmux`, `mc`, `pigz`, `plocate`, `vim`
- benchmark helpers like `llm-benchmark`
- convenience startup scripts such as `ol_serve.sh` and `comfi.sh`

These can be added later as apps or helper packages once the core runtime is stable.

### Historical or brittle and should not be copied literally

- mutating the system Python package graph with `pip --break-system-packages`
- forced `dpkg -r --force-depends` removals
- inline `sed` patching in Dockerfiles instead of tracked patch files
- app images recompiling PyTorch repeatedly instead of consuming a single shared built artifact
- Docker-specific startup assumptions baked into build steps

Nix should remove these, not preserve them.

## 3. Where each piece should live in the flake/build graph

The current repo already has the right rough split. This is the target mapping.

### A. `gfx803` runtime contract

What lives here:

- exported runtime env vars for Polaris
- wrapper scripts that set `LD_LIBRARY_PATH`, `HSA_OVERRIDE_GFX_VERSION`, `ROC_ENABLE_PRE_VEGA`, and related stability flags

Where it should live:

- shell wrappers such as `scripts/polaris-env.sh`
- flake app/shell glue in `gfx803_flake_v1`

This layer should not own source patches or wheel builds.

### B. ROCm support libs

What lives here:

- ROCR / HIP support layer
- `libhsa-runtime64`
- `libamdhip64`
- `libhiprtc`
- related non-math compatibility libs

Where it should live:

- extracted artifact sets like `lib-compat/`, `artifacts/rocm57/`, `artifacts/rocm-latest/`, and `artifacts/rocm64-upgrade/`
- or later, separate Nix derivations if we can rebuild them reproducibly

This layer is what the recent `6.4`-upgrade work has been probing.

### C. Math libs

What lives here:

- rebuilt `rocBLAS`
- `hipBLAS`, `hipBLASLt`, `rocSPARSE`, `hipSPARSE`, `MIOpen`, related math dependencies

Where it should live:

- separate extracted artifact subsets or separate derivations
- not bundled invisibly into every app shell

This is the layer that should be easiest to swap independently once Nix owns the graph more fully.

### D. Python / framework layer

What lives here:

- rebuilt PyTorch wheel
- rebuilt TorchVision wheel
- rebuilt TorchAudio wheel
- isolated Python environment that consumes those artifacts

Where it should live:

- a dedicated PyTorch derivation or shell input in `gfx803_flake_v1`
- not rebuilt separately by each app image

This should become the one shared framework artifact used by ComfyUI, WhisperX, and direct PyTorch shells.

### First concrete Nix boundary: `gfx803-pytorch-stack`

This is the first thing to build before touching Ollama:

- one shared Python environment
- one rebuilt `torch` wheel
- one rebuilt `torchvision` wheel
- one rebuilt `torchaudio` wheel
- explicit dependency on the selected gfx803 runtime/math layers

This boundary should exclude:

- ComfyUI
- WhisperX
- Ollama
- benchmark GUIs
- convenience start scripts

If the PyTorch boundary is not stable and reusable, the app layers will only hide the real compatibility work.

### First rebuild driver

The first Nix-owned rebuild driver should target the framework layer directly:

- use the Polaris/gfx803 build contract
- use the preserved old-ABI lane as the runtime/library source for the rebuild attempt
- use a coherent extracted old-ABI ROCm SDK root for headers, ROCm binaries, and cmake packages; changing only `LD_LIBRARY_PATH` is not enough
- build `torch`, then `torchvision`, then `torchaudio`
- write wheels and logs into a repo-local artifact directory
- carry over the conservative PyTorch build flags that already appeared in the later Docker attempts when the raw build proved brittle:
  - `BUILD_TEST=0`
  - `USE_NNPACK=0`
  - `USE_TENSORPIPE=0`
  - `USE_DISTRIBUTED=0`
  - `USE_RPC=0`
  - `USE_SYSTEM_PROTOBUF=1`
  - `BUILD_CUSTOM_PROTOBUF=OFF`
  - `CXXFLAGS=-Wno-error=maybe-uninitialized`
- insert a torch-only smoke gate before `torchvision`:
  - import the freshly built torch wheel inside the rebuild venv
  - record `torch.__version__`
  - reject the run if `ldd` shows ROCm payloads resolving from `/opt/rocm` latest instead of the intended old-ABI runtime/SDK roots
  - record `torch.cuda.is_available()`
  - stop before `torchvision` if that import path is still broken or the GPU is not visible
- reuse an already-built torch wheel by default when it exists in the rebuild `dist/` directory:
  - this keeps the next churn turn focused on the next blocker
  - it avoids paying for a full torch rebuild again after a later-stage packaging failure
- auto-discover runtime library directories for the built torch wheel instead of patching one missing `.so` at a time:
  - inspect the installed torch shared objects with `ldd`
  - collect `=> not found` entries
  - resolve them from known compat/system roots
  - augment `LD_LIBRARY_PATH` before the torch smoke gate and later stages

This is the first place where a long-running churn job is justified. If it fails, that failure is more meaningful than another round of partial library overlays.

Current result of that first rebuild lane:

- the torch wheel builds successfully
- the rebuild driver now reuses that wheel by default
- the driver now resolves runtime `.so` closure and keeps the wheel-local `torch/lib` ahead of system `libtorch_*`
- rebuilt latest-class torch now imports cleanly enough to report `torch.cuda.is_available()`
- but it still reports `False`
- the matching latest-class runtime below torch also fails `rocminfo` on Polaris with `HSA_STATUS_ERROR`

So the next work is below `torchvision`, not inside it.

The rebuild default should therefore target the preserved old-ABI upgrade lane first, not the full latest-class userspace.

### Two explicit shell roles

#### `gfx803-pytorch-stack`

Purpose:

- frozen control shell
- use the known-working extracted `6.4` Python/framework layer
- use the known-working selected libs

This is the baseline that should remain untouched.

#### `gfx803-pytorch-stack-upgrade`

Purpose:

- experimental ROCm-upgrade shell
- keep the same frozen extracted Python/framework layer as the control shell
- first swap only the low-risk support-lib layer underneath it

This is the shell to use when testing newer ROCm userspace on Polaris without changing the framework layer at the same time.

Current measured boundary:

- the shell split is now implemented
- the control shell still boots the frozen extracted `6.4` framework
- the first accepted upgrade shell is now a curated safe-support lane that overlays only:
  - `libamd_comgr`
  - `librocm-core`
  - `libelf`
  - `libnuma`
  - `libdrm`
  - `libdrm_amdgpu`
  - `libdrm_radeon`
- that safe-support lane keeps the frozen framework importing and still reports `torch.cuda.is_available() == True`
- the fully upgraded latest-class userspace remains a separate experiment lane, and that broader lane still crosses the HIP/HSA ABI boundary where the frozen framework expects `libamdhip64.so.6`

That is still a useful result: the first viable upgrade shell is now defined, and the next hard boundary is specifically the HIP/HSA ABI jump rather than shell composition.

## Current HSA/HIP seam

The runtime probes now show a stronger constraint than the earlier soname notes.

- latest `libhsa-runtime64` alone is enough to break `rocminfo` on Polaris/gfx803
- latest HIP userspace alone is not enough to break `rocminfo`
- restoring an old HSA-side cluster on top of the latest userspace can restore `rocminfo`
- but rebuilt latest-class torch still fails there because latest `libamdhip64.so.7` expects newer ROCR/HSA symbols than the old HSA runtime exports

That means:

- `rocminfo` can be restored on hybrid lanes such as:
  - old HSA runtime + old `libhsa-amd-aqlprofile64`
  - old HSA runtime + old profiler/tracing cluster
- rebuilt torch cannot yet use those same lanes as a real framework target

Migration consequence:

- do not plan around a naive `latest HIP on top of old HSA` hybrid
- the practical next target is to preserve the old HSA/HIP ABI where needed and upgrade around it deliberately, unless a newer Polaris-capable HSA/HIP fix becomes available

Current implementation direction:

- `gfx803-pytorch-stack-upgrade` should point at a preserved old-HSA/HIP ABI lane
- the framework rebuild driver should default to that same lane
- full latest-class userspace remains a separate diagnostic/runtime-investigation track

## PyTorch-first workaround classification

### Promote into the derivation now

- `HSA_OVERRIDE_GFX_VERSION=8.0.3`
- `ROC_ENABLE_PRE_VEGA=1`
- `PYTORCH_ROCM_ARCH=gfx803`
- `ROCM_ARCH=gfx803`
- `TORCH_BLAS_PREFER_HIPBLASLT=0`
- rebuilt `rocBLAS`
- rebuilt `torch` / `torchvision` / `torchaudio`
- clean TorchVision build env:
  - `PYTHONNOUSERSITE=1`
  - empty `PYTHONPATH`
  - do not leave the source-tree `torch` visible after wheel install

These are part of the real compatibility recipe.

### Keep as documentation only for now

- `pip --break-system-packages`
- forced `dpkg -r --force-depends` removals
- app-specific startup wrappers
- `llm-benchmark`
- Open-WebUI install flow
- Ollama source `sed` mutations

These are historical Docker transport details, not the PyTorch compatibility core.

### E. App layer

What lives here:

- ComfyUI
- WhisperX / Whisper-WebUI
- Ollama

Where it should live:

- separate app shells and launchers
- patches tracked as normal source patches

Apps should depend on the shared framework/runtime layers, not recreate them.

## Recommended migration order

1. Preserve the known working `6.4` runtime contract in wrappers and docs.
2. Split the current extracted `6.4` lane into:
   - support libs
   - math libs
   - python/framework layer
3. Recreate the PyTorch build as a single shared Nix artifact instead of per-app rebuilds.
4. Make that artifact the first explicit flake boundary: `gfx803-pytorch-stack`.
5. Expose both the frozen control shell and the upgrade shell from the flake.
6. Promote ComfyUI and WhisperX only after the shared framework layer is stable.
7. Move the Ollama source patches into tracked patch files after the PyTorch boundary is working.
8. Continue the `6.4`-upgrade lane as the upgrade laboratory for newer components.

## What success looks like

The practical target is:

- clone repo
- restore from Cachix
- enter a flake shell
- run the shared gfx803-compatible PyTorch stack
- swap one layer forward at a time when testing a newer ROCm userspace

That is the maintainable future path.

The original Dockerfiles remain valuable as source material, but they should become reference inputs to the flake graph, not the graph itself.
