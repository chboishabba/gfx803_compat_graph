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

## Phase and deliverable accounting — concrete exit gates

The release factory has **two consumer deliverables** plus the retained
compatibility qualification receipts: **(1) a reproducible native build
environment/SDK** and **(2) minimal patched ROCm and framework binaries
distributed through Nix/Cachix**. A binary import is the fast bootstrap, not
a substitute for a source-built Nix derivation.

| Phase | Artifact/deliverable | Status on PR #5 | Exact exit criterion |
| --- | --- | --- | --- |
| 0 — Retain measured controls | Existing Nix 6.4 direct-only lane, prior 5.7 comparison and drift/stress receipts | **Retained** | No changed behavior or relabeling of previously accepted/failed baselines |
| A — Pinned import tooling | Schaka 10.1 source lock, OCI digest/label verifier, rootless importer, Nix bootstrap shell, manifest, ELF auditor | **Source-written only; actual OCI import not executed** | One real immutable Schaka image resolves to the pinned component SHAs, imports cleanly into the Nix store, and is audited for relocation/ELF/ABI conflicts |
| B — First Nix-distributed modern binary | Cachix-published, scoped ROCm 10.1 runtime and optional framework output, with independent GPU admission receipt | **Open: no imported accepted binary or Nix/Cachix release** | Clean Nix client substitutes working packages; numeric/repeated/stress tests pass on stated host/card; exact logs and acceptance manifest are retained |
| C — Native reproducible source builds | Separate derivations for matched ROCm compiler/headers, ROCR/CLR, rocBLAS, MIOpen, rocSOLVER, MIGraphX, PyTorch and optional ORT/Triton | **Open; not provided by the OCI bootstrap shell** | Clean Nix builder reproducibly compiles from immutable Schaka/ROCm sources and patches, caches component closures and passes matching GPU acceptance tests |
| D — Automatic candidate → stable lifecycle | Upstream change monitor, dependency-based incremental rebuild, self-hosted Polaris gates, release pin/promotion and rollback | **Source monitor and manual import workflow written; no branch workflow runs or native rebuild/promotion proven** | Changing one component triggers only the derivation DAG dependents, test evidence distinguishes candidates from accepted release, and a previous stable closure can be restored |
| E — Upstream contributions (parallel) | Small attributed patches/reproducers proposed to TheRock and responsible AMD component owners | **Existing issue and separate PR #4; not a gate for Nix binary distribution** | Maintainer-reviewed targeted changes only after independent reproduction; no duplication of Schaka's patch suite |

**Current phase:** retained historical controls and a **source-written
Phase A bootstrap**, **not yet Phase B** (a usable/tested/published
ROCm 10.1 Nix binary) and **not yet Phase C** (native Nix source builds).
No new kernel patch development is on the critical path for the already
resolved 2025 KFD callback regression.

**Short critical path:** pin real OCI digest → check its published source
and resolved component SHAs → import and relocate selected Nix store paths
→ independent GPU dispatch/numerical/long-run tests → Cachix publish an
accepted first ROCm 10.1 binary → translate the same component graph into
native cacheable Nix builds → automate upgrades after hardware gates.

The first practical deliverable is **a small substitutable modern binary
closure and a validated package manifest**. The final project deliverables
add a **native Nix build SDK and modular source derivations**, plus verified
automatic incremental releases. Do not require an application-specific
ComfyUI or vLLM package for the core runtime to count as complete.

## Historical first-party numerical and hang evidence — preserve, do not rediscover

The earlier roadmap only indexed **third-party issue #43**. This repository
already has **first-party measurement code, retained result summaries,
failure-specific probes and incident reports**. Reuse those as the baseline
against Schaka's patched ROCm 10.1 stack before creating redundant testers.

| Date and origin | Retained evidence | Interpretation / qualification |
| --- | --- | --- |
| Aug 2025 community | [gfx803_rocm #43](https://github.com/robertrosenbusch/gfx803_rocm/issues/43) documents **RX570/580 ComfyUI image corruption in ROCm 6.4** while ROCm 5.7 produced working results on affected systems; [user's Aug 27 comment](https://github.com/robertrosenbusch/gfx803_rocm/issues/43#issuecomment-3226617434) engaged this exact comparison. | This is the **earlier externally reported cross-version image test**, not yet proven to be a first-party side-by-side ComfyUI image run. Record per-board/model/torch/driver details. |
| 16 Mar 2026 first-party | [probe_diffusion.py](https://github.com/chboishabba/gfx803_compat_graph/blob/master/probe_diffusion.py) committed March 16. [CONTEXT.md](https://github.com/chboishabba/gfx803_compat_graph/blob/master/CONTEXT.md) and [out/known_knowns.json](https://github.com/chboishabba/gfx803_compat_graph/blob/master/out/known_knowns.json) record **6/7** diffusion probes passed; `repeated_inference_drift` failed on a same-input five-run MiniUNet test. A separately recorded stable-profile drift was **0.001410** on `itir:latest`, kernel `6.19.7-1-cachyos-bore`. | **Our own direct reproduction of a numerical correctness failure**, using a mini-UNet surrogate rather than a full rendered ComfyUI image. Individual FP32/FP16, mixed and 50-step checks passed, but that did not establish stable repeated outputs. |
| Mar 2026 first-party bisection | [CONTEXT.md](https://github.com/chboishabba/gfx803_compat_graph/blob/master/CONTEXT.md), [check_drift_1x1.py](https://github.com/chboishabba/gfx803_compat_graph/blob/master/check_drift_1x1.py), [tests/drift_core.py](https://github.com/chboishabba/gfx803_compat_graph/blob/master/tests/drift_core.py), and [POLARIS_STABILITY_BLUEPRINT.md](https://github.com/chboishabba/gfx803_compat_graph/blob/master/POLARIS_STABILITY_BLUEPRINT.md): reported `GemmFwdRest` / GEMM-selected drift around **0.15**, direct-only zero drift in scoped repeated convolution, and 1×1 convolution differences approaching **0.98–1.0** after sustained kernel switches/context activity. | Solver-specific bisection is **existing first-party debugging**, not a hypothetical new test. Proposed Tensile YAML/register-reuse root cause and “state poisoning” mechanism are hypotheses, not independently proven kernel patch ownership. No scoped zero-drift convolution result implies full diffusion correctness. |
| 20 Mar 2026 | [Ollama Mistral incident](https://github.com/chboishabba/gfx803_compat_graph/blob/master/docs/INCIDENT_2026-03-20_OLLAMA_MISTRAL_KFD_RESET.md): output succeeded, then `init_user_pages` failures, compute-ring timeout, GPU reset, BACO, VRAM loss and compositor artifacts. | First-party **GPU reset** evidence on an older userspace lane, distinct from an import failure. |
| 25 Mar 2026 | [Wayland incident](https://github.com/chboishabba/gfx803_compat_graph/blob/master/docs/INCIDENT_2026-03-25_WAYLAND_GFX_TIMEOUT_RESET.md): repeated `ring gfx timeout`, BACO resets, VRAM loss and retained devcoredumps. | KWin was the named context, **not proven root cause**. This is not evidence that the fixed 2025 callback regression recurred. |
| 27–30 Mar 2026 | [WhisperX transcribe incident](https://github.com/chboishabba/gfx803_compat_graph/blob/master/docs/INCIDENT_2026-03-27_WHISPERX_TRANSCRIBE_RESET.md) and [March 30 trace](https://github.com/chboishabba/gfx803_compat_graph/blob/master/docs/INCIDENT_2026-03-30_WHISPERX_ALIGN_GPU_HANG_AND_ROCPROFV3_SUCCESS.md): confirmed active GPU work followed by `GPU Hang`, ring timeout, GPU reset and VRAM loss; later long-run sequence shows device-to-host copy → `Host active wait ... for -1 ns` → hang. `rocprofv3` sometimes altered survival and `HIP_LAUNCH_BLOCKING=1` yielded a summary-only exit 0. | **A substantial first-party hang/RCA programme**, including queue, VM/pinned-page and D2H hypotheses. The exposure point is observed; exact trigger/ownership and a durable successful long-run fix remain open. |
| 21 Mar 2026 | [CHANGELOG.md](https://github.com/chboishabba/gfx803_compat_graph/blob/master/CHANGELOG.md) / [USER_GUIDE.md](https://github.com/chboishabba/gfx803_compat_graph/blob/master/docs/USER_GUIDE.md) record 6.4 early Leech `block0.q_raw` divergence; 5.7 later repeated-run attention-layout drift, with the **tensor-only** 5.7 layout test stabilized by `HIP_LAUNCH_BLOCKING=1`. | Separate first-party attention/model correctness comparison, **not** the same full ComfyUI image test, and not proof the whole Leech model was fixed. |

### Exact crosswalk to already-solved Schaka patch classes

This is a **source/measurement join**, not a claim that the bugs
are byte-identical across releases:

- Our [CONTEXT.md](https://github.com/chboishabba/gfx803_compat_graph/blob/master/CONTEXT.md)
  documents the selected bad `GemmFwdRest` kernel with name containing
  `ISA803_K1_KLA` and ending `_WGM8`, together with scoped GEMM
  drift ~0.15. Schaka's
  [`wgm-miscompute-source.patch`](https://github.com/Schaka/rocm-gfx803/blob/main/patches/rocblas/wgm-miscompute-source.patch)
  independently reports that gfx803 **assembly** kernels with
  `WorkGroupMapping != 1` can mis-map workgroups to output tiles and
  silently compute incorrect GEMM answers. His patch forces WGM=1 at
  solution normalization for gfx803 assembly kernels, while retaining
  WGM!=1 for independently validated HIP-source kernels. That directly
  intersects the **kernel class** from our older profiler notes; re-run
  the same selected solution, shapes, process-lifetime and control
  profiles on the 10.1 Nix build to decide if it closes the exact
  earlier failure.
- Our older notes associate Winograd solver selection with GPU hangs
  and mark `MIOPEN_DEBUG_CONV_WINOGRAD=0` as a scoped mitigation.
  Schaka's [`winograd-fused-conv-miscompute.patch`](https://github.com/Schaka/rocm-gfx803/blob/main/patches/miopen/winograd-fused-conv-miscompute.patch)
  fixes a **different measured issue**: a legacy 3x3 fused Winograd
  solver being incorrectly selected for 1x1 shapes and returning
  wrong numerical values on RX 470. It does not yet demonstrate that
  our Winograd-associated **hang** shared that root cause. Keep
  hang and numerical-correctness receipts independently.
- Schaka's [`small-gemm-assembly-miscompute.patch`](https://github.com/Schaka/rocm-gfx803/blob/main/patches/rocblas/small-gemm-assembly-miscompute.patch)
  routes selected tiny assembly GEMMs to correct HIP-source kernels.
  This is worth testing against the full mini-UNet and attention/layout
  probes, but our 1×1 **convolution** stress test is not automatically
  equivalent to Schaka's 1×1×1 **matrix multiplication** reproducer.

The immediate high-alpha reuse target is therefore a **same-kernel-class
WGM8 differential test** under the existing drift probe with Schaka's
actual patch applied. Preserve original 2026 profiler/test authorship,
Schaka's later root-cause proof and his upstream patch provenance.

### Why the fixed 2025 KFD callback patch does not close these later incidents

[Linux commit 34659c1a1f4f](https://github.com/torvalds/linux/commit/34659c1a1f4fd4c148ab13e13b11fd64df01ffcd)
corrects the **specific missing gfx7/gfx8 SDMA reset callback** and
credits the reporter. The March 2026 host records include kernel
`6.19.7-1-cachyos-bore`, newer than the stable 6.15.7 backport; the
kernel must still be identified from an exact build and configuration
before claiming which patches were applied. The later trace of ring/
VM/DMA/hang events does **not** automatically mean the historical
callback regression remained unfixed; neither does the callback fix
explain away or solve the later failures. Schaka's 2026 vLLM hangs,
some tied in his documentation to out-of-spec VRAM clocking, are
another workload/board-specific evidence line that must not be
collapsed into the same mechanism without an equivalent reproducer.

### Reuse as the first independent Schaka 10.1 acceptance suite

1. Run the already-existing `tests/drift_core.py` and
   `check_drift_1x1.py` solver/context probes on an otherwise
   identical host/device; retain default, GEMM-selected and direct-only
   controls, including forced failure paths.
2. Run `probe_diffusion.py` on the 10.1 Nix candidate, preserving its
   20/50-step and same-input five-run criteria. Compare with prior
   `6.4` numeric receipts, rather than only checking NaN/Inf or import.
3. Run the existing WhisperX and Ollama short workload and long-run
   reset canaries on a fully documented kernel and within rated
   VBIOS/VRAM clocks. Record stage markers, last D2H/host wait,
   kernel `ring gfx timeout`, devcoredumps, and whether
   `HIP_LAUNCH_BLOCKING=1` changes the result.
4. Use Schaka's `tools/imgvalidate.sh`, `verify.py`, torch/GEMM/conv,
   Triton and coherence checks first; add only needed differential
   probes. Import and native Nix derivations must pass the same
   acceptance contract before releasing.
5. Treat a **real ComfyUI fixed-seed/model image comparison** as an
   application-level downstream canary whose historical 2025
   community reports provide expectations. Do not misrepresent the
   mini-UNet surrogate as a full ComfyUI run.

The outstanding work is **source-pinned ROCm 10.1 integration and
re-execution of existing qualified tests**, not invention of a first
GPU hang/debugging suite. Retain original test authorship and failed
historical results.

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

These are public observations, reports **and resolved upstream fixes**.
The 2025 KFD callback regression is fixed, not an outstanding Nix build blocker.
Retain hardware, kernel, ROCm and test-scope qualifiers for independent later regressions.

| Issue | Source-derived observation | Build/release implication |
|---|---|---|
| [ROCm/TheRock#9118](https://github.com/ROCm/TheRock/issues/9118) | Existing RX580 restoration request. Schaka reports ROCm 10.1 on his RX470 and qualified intermittent vLLM hangs in [his August 28 comment](https://github.com/ROCm/TheRock/issues/9118#issuecomment-6211403475); subsequent documentation attributes some hangs/VM faults to out-of-spec VRAM clocks. His README reports 202/202 PyTorch operations and 27/27 FP16 GEMM/convolution cases passing on ROCm 10.1, but says current-pin vLLM validation is open. | Reuse Schaka's source/patches and qualified receipts, but independently test our Nix binary on stated host/board before promotion; do not misattribute later VRAM/hang issues to the **fixed** 2025 KFD callback. |
| [ROCm/clr#269](https://github.com/ROCm/clr/issues/269) | Luca Bruni isolated ROCm 7+ rejection of gfx803 legacy DoorbellType 0/1, causing HSA_STATUS_ERROR before enumeration, and verified a restoration on RX550; Schaka confirmed his patches worked. The user's September 2026 reply tagged Schaka with the compat graph. | Pin and attribute Luca's ROCR/CLR restoration; require an actual enumeration gate rather than treating its build as proof of support. |
| [ROCm/legacy-rocm-build#4965](https://github.com/ROCm/legacy-rocm-build/issues/4965) and [#4919](https://github.com/ROCm/legacy-rocm-build/issues/4919) | **FIXED upstream**: user-reported 2025 gfx7/gfx8 KFD queue-reset regression led to [Linux commit 34659c1a1f4f](https://github.com/torvalds/linux/commit/34659c1a1f4fd4c148ab13e13b11fd64df01ffcd), adding missing `hqd_sdma_get_doorbell` callbacks. Authored by Alex Deucher, reviewed by Jonathan Kim, explicitly `Reported-by: Johl Brown`; backported to Linux 6.15.7. See the original [amd-gfx July mailing-list link](https://lists.freedesktop.org/archives/amd-gfx/2025-July/126884.html) and [June LKML exchange](https://lkml.rescloud.iu.edu/2506.3/04182.html). #4919 holds the related reporter's bisect/log evidence. | Do **not** list this historical KFD bug as an open build blocker. Retain kernel/firmware metadata and validate any *distinct* later reset or compute failure separately. Nix controls userspace, not host amdgpu/KFD. |
| [lamikr/rocm_sdk_builder#173](https://github.com/lamikr/rocm_sdk_builder/issues/173), [#220](https://github.com/lamikr/rocm_sdk_builder/issues/220) and [#259](https://github.com/lamikr/rocm_sdk_builder/issues/259) | The user requested gfx803 support in Nov 2024 and documented builds, exact SONAME/ROCm-SMI/ICU link errors and runtime crashes. Later reports cover Python heap corruption and an Eigen download hash mismatch. | Immutable source/pin and FOD hashes; never fake SONAME compatibility via copied libraries; coherent SDK/ABI and independent build vs load vs on-card tests. |
| [OpenNMT/CTranslate2#1072](https://github.com/OpenNMT/CTranslate2/issues/1072) and [arlo-phoenix/CTranslate2-rocm#4](https://github.com/arlo-phoenix/CTranslate2-rocm/issues/4) | The user commented extensively on ROCm acceleration, async allocator/device issues, and requested newer legacy ROCm builds in Oct 2024. Schaka reports wrong values for some CTranslate2/ORT workloads if his fixes are omitted. | Correctness probes must check outputs, not merely library import or GPU discovery. CTranslate2 is a useful optional representative integration fixture, not a mandatory application in the core runtime closure. |
| [robertrosenbusch/gfx803_rocm#43](https://github.com/robertrosenbusch/gfx803_rocm/issues/43) ([Schaka, October](https://github.com/robertrosenbusch/gfx803_rocm/issues/43#issuecomment-6519100882), [Schaka, 3 November](https://github.com/robertrosenbusch/gfx803_rocm/issues/43#issuecomment-6594618560)) | Users reported RX 570/580 ComfyUI corruption on some ROCm 6.4 builds even with `--lowvram` or attempted FP32 fallback, while ROCm 5.7 worked in those comparisons. Schaka specifically directs them to newer PyTorch kernel patches; original Nix 6.4 packages alone do not integrate them. This is a distinct **userspace numerical** concern, not evidence that the fixed 2025 KFD callback bug persists. | An optional negative/positive numerical canary comparing same inputs, model and hardware across 5.7 / 6.4 / patched 10.1; preserve actual output and version/provenance. Do not depend on ComfyUI to ship the core Nix SDK/runtime. |
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
