# TODO

## Immediate

- Record and preserve the completed old-ABI PyTorch framework rebuild result, including the ROCm header/toolchain shims that made the install succeed ✅
- Tighten the rebuilt torch runtime path so a direct `libtorch_python.so` smoke does not mix old-ABI and latest ROCm sonames (`libhipblas.so.3` vs the preserved `libhipblas.so.2` lane); reproducible compatibility aliases are now in the lane, and the isolated wrapper smoke now confirms `import torch` works without `setup.py develop` ✅
- Keep the wrapper smoke helper focused on the tiny `torch/csrc/stub.c` loader compile plus `torchgen`, not the full `setup.py develop` packaging path ✅
- Keep a single shareable user guide current for setup, cache usage, available surfaces, and contribution/reporting instructions ✅
- Keep a plain-language clone-to-ready onboarding section in the public guide for non-technical users ✅
- Record the extracted `6.4` host path as covering torch import / GPU visibility, ComfyUI, and general userspace bring-up, while keeping WhisperX outside the promoted stable baseline ✅
- Verify that the published `gfx803-rocm` Cachix entries can be consumed cleanly from another machine or a clean local profile

### Current-upstream TheRock / official-support lane

- Keep Arch/CachyOS ROCm `7.2.4` as the untouched distro control; do not call it `latest`
- Run `scripts/build-therock-gfx803-artifacts.sh --prepare-only` on the host and retain the exact patch-applicability receipt for current `ROCm/TheRock`
- If prepare succeeds, run `--core-only` before a full build; record build/enumeration/HIP/OpenCL states independently
- Keep Luca Bruni's `3d4ad609...` restoration as a known-restored reference, not the primary current source
- Preserve AMD's graceful unsupported-device skip behavior while re-admitting only legacy doorbell types whose queue semantics are actually restored/tested
- Use TheRock's out-of-tree `therock_custom_amdgpu_targets.cmake` hook during bring-up; upstream objective is a normal `gfx803` target plus corresponding release extra
- Treat `Build Passing`, `Sanity Tested`, and `Release Ready` as separate promotion states; endpoint is official AMD RX580/Polaris support

### ROCm 10 full-stack reference / patch snowball

- Probe the prebuilt `ghcr.io/schaka/rocm-migraphx-ort-torch-builder:rocm10.0-gfx803` image on this RX580 using `scripts/probe-schaka-rocm10-gfx803-reference.sh`
- Record image digest plus hardware/VBIOS/VRAM-clock state before interpreting any reset-class result
- Run the Leech tensor-only layout/determinism reproducer against the ROCm 10 reference before rebuilding current TheRock
- Run the smallest WhisperX/copy reproducer against the ROCm 10 reference
- Compare direct D2H versus staged D2H behavior before relating `d2h-staged-copy.patch` to our existing copy/wait sentinel
- Keep `d2h-null-dsthost.patch` and `va-reuse-defer-noremap.patch` as separate candidate mechanisms until our repro exercises their exact allocation/lifetime conditions
- Do not promote `sdma-doorbell-missing-sfence.patch` as causal: its own source history retracts the SFENCE and ring hypotheses and attributes the tested hang to VRAM-clock marginality
- Expand `docs/GFX803_UPSTREAM_PATCH_ATLAS.md` across Schaka's rocBLAS, MIOpen, rocSOLVER, MIGraphX, PyTorch and Triton patches; classify each as runtime prerequisite, correctness, fallback, performance, genuine ISA absence, superseded diagnostic, hardware/VBIOS, or release-policy debt
- Prefer alternative algorithms/fallback computation where modern fast paths require unavailable instructions; `unsupported instruction != unsupported GPU`
- Specifically retain bf16 as a truthful hardware limitation while keeping fp16/fp32 paths eligible for support
- Shrink the patch set toward the smallest upstreamable set instead of importing every community workaround into current TheRock

- Treat the Robert `6.4` Ollama image as the short-term practical GPU fallback until the Ollama-specific port is reproduced outside the full container ✅ (reference bundle extracted and published at `artifacts/ollama_reference/`, host stability still under investigation)
- Port the previously working Robert `6.4` Ollama GPU path into a smaller extracted or Nix-managed workflow so the full Robert container is no longer required for Ollama (in progress: reference bundle + host launcher + flake shell exist)
- Re-test the extracted `artifacts/ollama_reference/` host path after the AMDGPU `libdrm` copy fix and `HSA_ENABLE_SDMA=0` host launcher change, because the last host run triggered a GPU reset / PC crash
- Document the lower-level GPU execution-path model explicitly:
  - `init_user_pages` failure, VM fault, ring timeout, reset, VRAM loss
  - compositor redraw / `alt-tab` as a trigger hypothesis rather than a proven root cause
- Keep the Polaris stability blueprint current as the repo’s broad sanity / stabilization checklist for reset-class failures ✅
- Add a GPU execution-path admissibility registry so RCA claims can attach to queues, VM faults, reset paths, and profiler evidence instead of only to app stages
- Capture one debugger-backed `rocminfo` RCA note ✅
- Preserve current WhisperX classification: confirmed `ring gfx timeout` / queue forward-progress loss; copy/wait-adjacent exposure point; first `Host active wait ... for -1 ns` sentinel; VM/pinned-page and DMA/copy-path remain candidate triggers
- Rerun the `blocking` WhisperX success lane with `KEEP_SUCCESS_TRACE=1` so success retains logs/profiler evidence
- Preserve the current `5.7` extracted host path as a separate reusable artifact alongside the top-level extracted `6.4` baseline
- Keep Leech correctness-first status: `6.4` is wrong early, `5.7` is less wrong but still nondeterministic, CPU is the trustworthy output path until a GPU lane earns numerical receipts
- Turn the tensor-only layout repro plus `HIP_LAUNCH_BLOCKING=1` result into an upstream-quality operation/ordering reproducer
- Keep `artifacts/rocm-latest/` as a moving source/control lane rather than the primary runtime target
- Keep the preserved old-HSA/HIP ABI lane as the practical short-term control until current TheRock earns equivalent receipts
- Keep the first explicit Nix-owned artifact boundary as the shared `gfx803-pytorch-stack`

## Documentation

- Keep `6.4`, `5.7`, native Arch `7.2.4`, moving upstream extraction, current TheRock, Luca reference, and ROCm 10 full-stack reference clearly separated in newcomer docs and scripts
- Keep the Cachix cache name, URL, and public key documented anywhere Nix entrypoints are presented
- Keep the patch atlas explicit that a component exclusion is investigation debt, not an impossibility proof
- Keep source corrections/retractions visible; do not silently retain superseded root-cause narratives
- Keep the new shareable user guide aligned with README and START_HERE whenever promotion states change
- Keep the Leech docs aligned with the current correctness finding: GPU launch success is not trustworthy output
- Keep the WhisperX RCA workflow documented and aligned across README and user guide

## Deferred

- Decide whether the top-level `flake.nix` should be updated to match `gfx803_flake_v1` or explicitly marked legacy
- Add a self-hosted gfx803 hardware runner capable of paying TheRock-style Sanity Tested receipts once the current-source core lane is stable
- Draft upstream AMD target/roadmap PR only after the minimal current patch set and hardware sanity receipts are reproducible
- Promote compatibility graph outputs into a more obvious summary view for non-technical readers
