# gfx803 Nix binary factory: build and distribution roadmap (2026-11-04)

## Scope and ownership

The product is **both a reproducible build environment and independently installable gfx803 binaries**. Consumers should not need Docker, an old Ubuntu root filesystem, or ROCm compilation; developers should be able to reconstruct accepted packages from exact sources, patches, compiler and package graph.

- Schaka/rocm-gfx803 owns the original ROCm 10.x GFX8 fixes, source build recipes and correctness suite. Reuse and credit them; do not independently re-implement wave64, WGM, cache-coherency or MIOpen fixes.
- gfx803_compat_graph owns reproducible Nix packaging, build inputs, compatibility evidence, release policy, Cachix and upgrades.
- ROCm/TheRock remains the desired upstream destination. Existing PR #4 addresses that separately; this lane must not replace it.
- Application projects are optional consumers and canaries, not the definition of build-system correctness.

## State, as of this branch

| Gate | Current evidence | Status |
|---|---|---|
| Extracted ROCm 6.4 control | Existing measured direct_only pass, plus retained negative results | PRESERVED |
| Pinned Schaka revision | nix/gfx803/upstream.json names full 40-byte SHA and release | SOURCE-WRITTEN |
| Nix bootstrap tools | Root flake exports daemonless OCI tool shell, importer, policy, checks | SOURCE-WRITTEN |
| Digest-pinned upstream image import | skopeo + umoci -> Nix store paths + candidate.json | SOURCE-WRITTEN, not run |
| GPU numerical/reset admission | Seven required receipt types, exact hardware/provenance | OPEN |
| Accepted cached binary packages | Optional fetchClosure flake outputs after accepted manifest | DEFINED, no accepted release |
| Native, source-built ROCm Nix derivations | Patched runtime, math, compiler, frameworks in separate outputs | OPEN |
| Upstream change discovery | Scheduled weekly source update PR | SOURCE-WRITTEN, not run on default branch |
| Automatic native build/publish | DAG changes, CI, hardware gate and release promotion | OPEN |

SOURCE-WRITTEN is **not** built, run, hardware validated or production ready.

## Entry points

The **root flake** is the new canonical interface; gfx803_flake_v1 continues to preserve existing control and diagnostic shells.

- `nix develop .#gfx803-oci-build`: reproducible OCI/Nix tooling with NO unrelated Nixpkgs ROCm shared-library injection.
- `nix run .#gfx803-schaka-import -- --help`: import immutable image parts to Nix store (candidate only).
- `nix run .#gfx803-release-policy -- --help`: inspect source and evidence policy.
- `nix build .#gfx803-schaka-upstream-lock`: source pin artifact.
- `nix build .#checks.x86_64-linux.gfx803-release-policy`: offline mock-import and policy tests.
- Only with a committed hardware-accepted release manifest: `nix build .#gfx803-rocm-binary` (and optional `gfx803-venv-binary`), fetched from gfx803-rocm.cachix.org.

The latter use experimental `builtins.fetchClosure`, and current input-addressed paths require the configured Cachix trust key. Eventually use `nix store make-content-addressed` and record rewritten hashes to remove that dependency.

## Phase A: reuse the existing successful binaries first

The bootstrap imports an image **by OCI SHA256 digest**, via skopeo and rootless umoci; no Docker daemon is required. It adds only selected /opt/rocm and optional /opt/venv subtrees to the Nix store, not a full image tarball. It is an intentionally transitional **binary import**, not a native Nix compilation and not yet a minimal/runtime-relocated closure.

Example, with the image digest resolved independently:

```bash
nix develop .#gfx803-oci-build
repo=ghcr.io/schaka/rocm-migraphx-ort-torch-builder
digest="$(skopeo inspect --format '{{.Digest}}' "docker://$repo:rocm10.1-gfx803")"
rev="$(python3 -c 'import json; print(json.load(open("nix/gfx803/upstream.json"))["source_revision"])')"
gfx803-import-schaka --image "$repo@$digest" --source-revision "$rev" \
  --with-venv --out out/schaka-oci/rocm10.1
```

This has NOT run here. It produces an unvalidated candidate manifest and Nix store paths. Before large image download, the importer checks Schaka's published OCI labels for exact source SHA, release line, final stage and resolved component pins. A label mismatch fails closed. Label agreement is publisher metadata evidence, not an independent reproducible-build attestation; runtime relocatability and on-card correctness still need real receipts.

## Phase B: close the first accepted binary release

1. Resolve and pin immutable OCI digest and verify the published build revision matches the selected Schaka SHA.
2. Import on a Nix machine. Audit ELF DT_NEEDED, RPATH, duplicate ROCm/HIP/HSA/LLVM libraries, absolute /opt/rocm paths, wheel shebangs and runtime dependencies. Eliminate or wrap nonrelocatable paths without blending ABI lines.
3. Run Schaka's tools/imgvalidate.sh, verify.py and relevant negative controls on actual Polaris hardware; integrate the compat graph's drift, repeated-run and reset diagnostics.
4. Record source provenance, GPU enumeration, kernel dispatch, numerical correctness, repeatability, sustained load, and runtime linkage. Each must have pass status, executed command, relative log_path, and retained log SHA256. Promotion opens the real log files under --evidence-root and checks their bytes against those digests; also include actual gfx803 device, kernel, driver and runner.
5. Only after all gates pass, run the release policy promoter to generate an accepted-release.json and review it. Then publish only those accepted store paths via the Cachix script.
6. Fetch the resulting Nix outputs on a clean client and verify they work without Docker or mixed system ROCm.

```bash
python3 scripts/gfx803_release.py promote \
  --manifest out/schaka-oci/rocm10.1/candidate.json \
  --out nix/gfx803/accepted-release.json \
  --evidence-root out/schaka-oci/rocm10.1/logs
bash scripts/publish-gfx803-accepted.sh nix/gfx803/accepted-release.json --dry-run
bash scripts/publish-gfx803-accepted.sh nix/gfx803/accepted-release.json
```

The promoter is deliberately fail-closed: importing, compiling or enumerating a GPU is insufficient. Acceptance does not assert universal gfx803 correctness or official AMD support.

## Phase C: native, modular Nix source builds

Port Schaka's exact source and patch graph into independently cacheable derivations, retaining original attribution:

`patched ROCr/CLR -> rocBLAS + MIOpen -> rocSOLVER -> MIGraphX -> PyTorch / ONNX Runtime / optional Triton and consumers`.

Use a **matched ROCm release compiler, headers and device-libs**. The earlier LLVM 22 versus 19 and old/new HIP-HSA mixups are reasons to isolate the entire SDK, not to extend ad hoc LD_LIBRARY_PATH wrappers.

Separate runtime, development, device-code, tools and Python wheel outputs; avoid duplicating the ROCm tree across packages or shipping compilers in consumers' runtime closures. Reuse upstream build scripts and patches with only packaging adaptations; run the same on-card tests against the native binaries. Never rebuild an unchanged component just because an unrelated project changed.

## Phase D: automatic source/update/build/release

The weekly upstream-watch workflow *only* proposes changed source revisions. It never asserts a successful new GPU build. Once native derivations exist, CI should rebuild precisely the derivations invalidated by their hashes, re-run hosted source checks, then run physical gfx803 checks on a self-hosted runner. Candidate Cachix artifacts and receipts should be separate from accepted stable closures. Promotion is explicit and evidence-dependent; retain earlier accepted manifests and Nix store closures for rollback.

## Existing public issue lineage and no-duplication policy

These are public observations/reports, not all accepted upstream fixes.
Retain their hardware, kernel, ROCm, and test-scope qualifiers.

| Issue | Source-derived observation | Build/release implication |
|---|---|---|
| [ROCm/TheRock#9118](https://github.com/ROCm/TheRock/issues/9118) | Existing RX580 restoration request. Schaka explicitly asks contributors not to duplicate his ROCm 7.14/10.x build and patch work and reports ROCm 10.1 working on his card, with vLLM/system-hang qualifications. | Use as upstream coordination issue; native Nix should reuse source and patches rather than reimplementing kernel fixes. |
| [ROCm/clr#269](https://github.com/ROCm/clr/issues/269) | Luca Bruni isolated ROCm 7+ rejection of gfx803 legacy DoorbellType 0/1, causing HSA_STATUS_ERROR before enumeration, and verified a restoration on RX550; Schaka confirmed his patches worked. The user's September 2026 reply tagged Schaka with the compat graph. | Pin and attribute Luca's ROCR/CLR restoration; require an actual enumeration gate rather than treating its build as proof of support. |
| [ROCm/legacy-rocm-build#4965](https://github.com/ROCm/legacy-rocm-build/issues/4965) and [#4919](https://github.com/ROCm/legacy-rocm-build/issues/4919) | The user filed a 2025 Polaris compute-ring/KFD regression report (originally referenced as ROCm/ROCm#4965) and posted kernel/dmesg/bisect traces. AMD said unsupported kernels/card lacked guaranteed support and acknowledged an internal investigation. A proposed pair of revert commits in the issue was NOT fully independently verified by its author. #4919 contains the user's related trace contributions and AMD's advice to use a compatible kernel. | Nix controls userspace, NOT host amdgpu/KFD; retain kernel, firmware, reset, event/doorbell and tested hardware metadata, and never claim every host kernel safe. |
| [lamikr/rocm_sdk_builder#173](https://github.com/lamikr/rocm_sdk_builder/issues/173), [#220](https://github.com/lamikr/rocm_sdk_builder/issues/220) and [#259](https://github.com/lamikr/rocm_sdk_builder/issues/259) | The user requested gfx803 support in Nov 2024 and documented builds, exact SONAME/ROCm-SMI/ICU link errors and runtime crashes. Later reports cover Python heap corruption and an Eigen download hash mismatch. | Immutable source/pin and FOD hashes; never fake SONAME compatibility via copied libraries; coherent SDK/ABI and independent build vs load vs on-card tests. |
| [OpenNMT/CTranslate2#1072](https://github.com/OpenNMT/CTranslate2/issues/1072) and [arlo-phoenix/CTranslate2-rocm#4](https://github.com/arlo-phoenix/CTranslate2-rocm/issues/4) | The user commented extensively on ROCm acceleration, async allocator/device issues, and requested newer legacy ROCm builds in Oct 2024. Schaka reports wrong values for some CTranslate2/ORT workloads if his fixes are omitted. | Correctness probes must check outputs, not merely library import or GPU discovery. CTranslate2 is a useful optional representative integration fixture, not a mandatory application in the core runtime closure. |
| [advanced-lvl-up#10](https://github.com/advanced-lvl-up/Rx470-Vega10-Rx580-gfx803-gfx900-fix-AMD-GPU/issues/10) | User's Mar–Apr 2026 real-hardware reports on diffusion output noise, repeatability, context/kernel-switch poisoning, Nix-run alternatives and reset boundaries. They explicitly reported isolated pass alongside repeated-inference failure. | Preserve failure receipts and use stress/context-switch tests. Do not promote an isolated deterministic kernel to universal stack correctness. |
| [robertrosenbusch/gfx803_rocm#5](https://github.com/robertrosenbusch/gfx803_rocm/issues/5), [#6](https://github.com/robertrosenbusch/gfx803_rocm/issues/6), and [#51](https://github.com/robertrosenbusch/gfx803_rocm/issues/51) | Existing community containers and framework build/debugging lessons (TorchAudio, WhisperX, ComfyUI), plus later distributed-compute discussion. The user documented large images and repeated rebuild/storage cost. | Keep matched wheel outputs separate from runtime SDK; avoid recompiling apps' shared dependencies and require only relevant app fixtures on a given release. Distributed inference remains out of build-factory scope. |
| [ollama/ollama#2453](https://github.com/ollama/ollama/issues/2453) | Official Ollama older gfx803 ROCm binary support closed as not planned in July 2026; maintainers pointed to Vulkan as a possible route. User linked the compat graph on July 24. | Do not promise official Ollama ROCm gfx803 support. Build family should permit ROCm and Vulkan backends as independent consumers rather than forcing a monolithic package. |
| [ROCm/TheRock#9210](https://github.com/ROCm/TheRock/issues/9210) | FirePro WX7100 request and a comment asserting infeasibility of gfx803 restoration; this is a commenter claim, not an established impossibility theorem, and modern patched builds are relevant counterevidence. | Separate community opinion from actual build/test receipts and upstream support policy. |

### Four orthogonal acceptance dimensions

1. **Build provenance:** exact Schaka/ROCm/LLVM/framework/component commits, patch hashes and reproducible package dependency graph.
2. **Runtime/device support:** coherent userspace ABI and physical gfx803 enumeration, HIP/ROCr/CLR dispatch, correct ELF closure, no mixed system device-libs.
3. **Numerical/stress correctness:** selected GEMM, convolution, asynchronous copy/layout, CTranslate2/ORT-style fixtures, nondeterminism and sustained GPU reset measurements.
4. **Host compatibility:** actual Linux kernel, amdgpu/KFD, board, memory clocks, firmware and topology; not controlled by Nix and must be reported independently.

Do not automatically label host-only faults as ROCm userland bugs, userland numeric failures as missing gfx803 support, or successful imports as acceptance. No third-party issue or single benchmark result suffices to promote an untested local build.

## Definition of done

- A clean consumer downloads the needed **finished patched binaries** through Nix/Cachix without Docker or local compilation.
- A clean Nix builder can reproducibly construct the full patched SDK/runtime/math/framework stack from immutable, attributed source and patches.
- Every supported hardware/stack combination has reproducible numerical, dispatch, linkage and sustained-load evidence.
- Automated upstream change discovery and incremental builds produce candidates; only admitted candidates become stable.
- The original 6.4 control and historical failure receipts remain available and never get relabelled as universal correctness.

**Remaining exact max-cut:** first real digest import + relocation audit + on-card acceptance, then native source derivations and automated incremental build/promote. This branch implements the source lock, import/policy surface, conditional Cachix outputs, and candidate source-watch, but does not pretend the unexecuted gates are closed.
