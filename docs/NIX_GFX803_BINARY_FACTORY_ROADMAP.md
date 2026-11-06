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
| Nix bootstrap tools | Root flake exports daemonless OCI shell, digest-lock policy, evidence capture, importer, closure audit and checks | SOURCE-WRITTEN; Nix evaluation not run |
| Digest-pinned image import | skopeo digest+8-SHA pin verification; rootless umoci; image-root-based /etc/alternatives symlink staging; Nix store candidate plus link and component-source reports | SOURCE-WRITTEN, not run on a real image |
| GPU numerical/reset admission | Seven required receipt types plus retained log hashes; receipt recorder rejects 6/7 diffusion PARTIAL_PASS despite process exit 0 | LOGIC SOURCE-WRITTEN; actual hardware gates OPEN |
| Accepted cached binaries | Optional fetchClosure outputs; publication re-hashes retained original evidence, requires locked image digest | DEFINED, no accepted release |
| Native, source-built ROCm Nix derivations | Exact 8-SHA upstream component source graph and transitive rebuild plan emitted; actual native Nix compilation still absent | SOURCE GRAPH WRITTEN; COMPILATION OPEN |
| Upstream change discovery | Weekly Schaka source SHA and independently inspected OCI image digest PR workflows | SOURCE-WRITTEN, not run on default branch |
| Automatic native build/publish | DAG changes, CI, hardware gate and release promotion | OPEN |

SOURCE-WRITTEN is **not** built, run, hardware validated or production ready.

## Entry points

The **root flake** is the new canonical interface; gfx803_flake_v1 continues to preserve existing control and diagnostic shells.

- `nix develop .#gfx803-oci-build`: reproducible OCI/Nix tooling with NO unrelated Nixpkgs ROCm shared-library injection.
- `nix run .#gfx803-schaka-import -- --help`: import immutable image parts to Nix store (candidate only).
- `nix run .#gfx803-release-policy -- --help`: inspect source, lock an independently inspected OCI image, and review admission policy.
- `nix run .#gfx803-capture-evidence -- --help`: run commands, retain hash-backed original logs and reject partial diffusion reports.
- `nix run .#gfx803-comfyui-images -- --help`: compare original real 5.7-good / 6.4-bad and candidate 10.1 images, requiring hashes of the workflow and model, explicit thresholds, and a fixed seed.
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

**Short critical path:** resolve actual image digest via the hosted inspect-only PR workflow (with all eight component SHAs validated) → merge reviewed lock → run real import on Nix/Polaris hardware → check staging/audit reports and runtime linkage → execute historic ComfyUI, GEMM/WGM8, diffusion, WhisperX and Schaka correctness suites → rehash evidence, admit and publish → test clean Nix client → implement native source derivations. The original, narrower plan was: pin real OCI digest → check its published source
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
| 2025–26 first-party ComfyUI + community comparison | **Actual ComfyUI images were tested on gfx803**: the project reports correct generated images on ROCm 5.7 and corrupted/gradient-like images in the affected ROCm 6.4 configuration, followed by real `direct_only` and extracted-runtime trials. Independent contemporaneous [issue #43](https://github.com/robertrosenbusch/gfx803_rocm/issues/43) captures related RX570/580 results and the [user's August 27 participation](https://github.com/robertrosenbusch/gfx803_rocm/issues/43#issuecomment-3226617434). This repo's [March 19 changelog](https://github.com/chboishabba/gfx803_compat_graph/blob/master/CHANGELOG.md) confirms extracted 6.4 ComfyUI coverage. | **First-party application tests exist and predate this Nix 10.1 roadmap.** Do not relabel them as a future test or a MiniUNet-only finding. Historical full-workflow model/config/output-image hashes are not all linked to one currently committed receipt; inventory and attach available originals before claiming bit-for-bit replay. |
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

### 5 Nov 2026: Leech failed despite legacy *default* safe profile

The uploaded original [Leech GPU gate receipt](https://github.com/chboishabba/LeechTransformer/blob/experiment/consumer-preserving-multiscale-codec-20261031/docs/receipts/gfx803_control_leech_c2_rejected_20261104.json)
(SHA-256 `1e3b5640995eaf7ca93517a19cad7f85639926d1e9b817c8b6c0b296e516aa79`)
reports **no GPU admission** on
`torch 2.6.0+gitdae14f9`, HIP `6.4.43483-a187df25c`,
Linux `7.3.0-2-cachyos-bore`, batch 2, 64 tokens and an
actual 8 GiB `gfx803` device. Failures precede focused C2 computation:
dense logits max abs **28.5573**, layer-1 normalized input **2.3884**,
FFN output **1.1904**, and same-GPU repeats **0.2023/0.2371**.

**Important correction to causal ordering:** the
[original extracted-runtime launcher](https://github.com/chboishabba/gfx803_compat_graph/blob/master/scripts/host-docker-python.sh)
already **defaults** to the proven MIOpen convolution direct-only flags:
`DIRECT=1`, `GEMM=0`, `WINOGRAD=0`, `FFT=0`,
determinism/cache controls, `TORCH_BLAS_PREFER_HIPBLASLT=0` and
`CUBLAS_WORKSPACE_CONFIG=:4096:8`. The Nix Leech launcher uses that
original wrapper. The uploaded old receipt did not capture individual
MIOpen values, so inherited explicit overrides remain possible, but
there is **no basis to conclude the safe launcher was omitted**.

The legacy safe flags act on **MIOpen convolutions**, not every
rocBLAS GEMM, attention/materialization, QKV, FP32 layer normalization,
or positional embedding operation. They cannot establish same-input
transformer correctness. The original `gfx803_flake_v1` shell also
contains broader ROCm dev inputs and the wrapper preserves some
inherited library search paths: a **mixed actual dynamic-library
selection** is another measurable hypothesis, **not a proven cause**.

[LeechTransformer PR #4](https://github.com/chboishabba/LeechTransformer/pull/4)
now includes `scripts/gfx803_runtime_attestation.py` and propagates
its read-only **effective environment + actually mapped HIP/rocBLAS**
snapshot into subsequent gate and operator-boundary receipts, plus an
opt-in diagnostic-only PyTorch deterministic-algorithms run. Source-written;
**no new physical execution reported**. Preserve the original negative
receipt unchanged. This diagnostic precedes attributing any Leech
failure to Schaka's WGM!=1 class; the selected actual QKV/Tensile solution
and the first unperturbed failing Leech module remain unmeasured.

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
5. **Replay the already-performed first-party real ComfyUI image
   comparison** on the new modern stack, with fixed seed/model/solver
   and output-image hashes. Preserve the user's historical 5.7-correct
   versus affected-6.4-corrupted observations and community #43
   references. Identify retained original workflow/PNG/log files to
   make this a hash-verifiable acceptance fixture. The MiniUNet
   surrogate is a separate, additional test, not a replacement.

The outstanding work is **source-pinned ROCm 10.1 integration and
re-execution of existing qualified tests**, not invention of a first
GPU hang/debugging suite. Retain original test authorship and failed
historical results.

### Offline-first source admission tools implemented on this branch

- `scripts/gfx803_component_graph.py` parses Schaka's **eight exact 40-byte
  resolved component SHAs**, rejects moving refs and computes the transitive
  rebuild set from the actual published upstream build DAG. It writes
  `component-sources.json` for the Nix-native phase. The graph is **not**
  a compilation or a content-addressed input derivation.
- `scripts/audit_gfx803_closure.py` now treats **all** unresolved ELF
  `DT_NEEDED` SONAMEs as hazards, not just ROCm-specific ones. Explicit
  `--provider-root /nix/store/...-libdrm` or glibc provider roots can be
  added when actually present in the runtime dependency closure; it never
  assumes system `/usr/lib` fills missing links. This is still a static
  audit, not runtime or GPU proof.
- `scripts/gfx803_oci_links.py` stages `/opt/rocm` and optional `/opt/venv`,
  resolving OCI-internal `/etc/alternatives/rocm-*` chains to relative
  in-tree links. It reports missing and outside-tree aliases instead of
  pretending those dependencies are present. ELF and wheel relocation
  remains separate.
- `scripts/gfx803_release.py lock-image` binds only a publisher-inspected
  image SHA256 to the exact source lock and its eight resolved commit SHAs.
  Promotion refuses a missing/mismatched digest, even with green receipts.
- `scripts/gfx803_capture.py` runs real commands and saves their original
  logs with hashes. An explicit `--expect-diffusion-all-pass` checks
  `PROBE_JSON` so the historic `6/7` outcome cannot be promoted merely
  because the probe exits 0.
- `scripts/gfx803_comfyui_images.py` scores **actual** ComfyUI output PNGs
  against the original first-party 5.7-good/6.4-bad comparison, requiring
  matching model/workflow/seed and explicit tolerances. It is an optional
  downstream application canary; no historical PNGs are invented.
- `scripts/publish-gfx803-accepted.sh` now requires `--evidence-root` and
  reopens/hashes all original logs **at publication time**. A committed
  accepted JSON with missing/tampered logs cannot publish.
- `.github/workflows/gfx803-schaka-image-digest.yml` resolves the tag
  to a reviewed immutable digest candidate, and the GPU import workflow
  requires that digest already be committed. Neither workflow claims GPU
  correctness or creates accepted binaries without the physical tests.

A core candidate has seven mandatory receipts. If the manifest also claims
`claimed_capabilities: ["comfyui_images"]`,
`["whisperx_long_run"]` or `["ollama_gpu"]`, admission additionally requires
respectively `comfyui_image`, `async_hang_regression` or
`ollama_gpu_inference` passing hash-backed logs. No generic GPU
smoke proves those workload-level claims.

Record an actual diffusion gate (after creating a candidate manifest from
the real imported release), for example:

```bash
nix run .#gfx803-capture-evidence -- \
  --candidate out/schaka-oci/rocm10.1/candidate.json \
  --evidence-root out/schaka-oci/rocm10.1/logs \
  --gate numerical_correctness --expect-diffusion-all-pass \
  -- bash scripts/host-docker-python.sh probe_diffusion.py
```

The ComfyUI comparison app requires real PNGs from matched executions and
its deliberately selected `--max-rmse` must be justified by the workflow's
baseline variance. This tool does not itself run the ComfyUI image-generation
pipeline or claim access to the earlier output files.

The command must run against the **candidate 10.1 runtime**, not silently
against the legacy extracted 6.4 control. Replace that example launcher
with the verified candidate environment wrapper when relocation is ready.
A failed/partial run leaves a retained `fail` receipt and cannot promote.

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
bash scripts/publish-gfx803-accepted.sh nix/gfx803/accepted-release.json \
  --evidence-root out/schaka-oci/rocm10.1/logs --dry-run
bash scripts/publish-gfx803-accepted.sh nix/gfx803/accepted-release.json \
  --evidence-root out/schaka-oci/rocm10.1/logs
```

The promoter is deliberately fail-closed: importing, compiling or enumerating a GPU is insufficient. The separate publisher re-opens the same `--evidence-root` and hashes all receipt logs again; it also refuses a candidate without a reviewed immutable image digest. Acceptance does not assert universal gfx803 correctness or official AMD support.

## Phase C: native, modular Nix source builds

Port Schaka's exact source and patch graph into independently cacheable derivations, retaining original attribution:

`patched ROCr/CLR -> rocBLAS + MIOpen -> rocSOLVER -> MIGraphX -> PyTorch / ONNX Runtime / optional Triton and consumers`.

Use a **matched ROCm release compiler, headers and device-libs**. The earlier LLVM 22 versus 19 and old/new HIP-HSA mixups are reasons to isolate the entire SDK, not to extend ad hoc LD_LIBRARY_PATH wrappers.

Separate runtime, development, device-code, tools and Python wheel outputs; avoid duplicating the ROCm tree across packages or shipping compilers in consumers' runtime closures. Reuse upstream build scripts and patches with only packaging adaptations; run the same on-card tests against the native binaries. Never rebuild an unchanged component just because an unrelated project changed.

## Phase D: automatic source/update/build/release

The weekly upstream-watch workflow *only* proposes changed source revisions. The separate `gfx803-schaka-image-digest.yml` checks the OCI manifest digest and all eight resolved source pins without downloading its layers, and proposes a reviewable source-to-image lock PR. It never asserts a successful new GPU build. Once native derivations exist, CI should rebuild precisely the derivations invalidated by their hashes, re-run hosted source checks, then run physical gfx803 checks on a self-hosted runner. Candidate Cachix artifacts and receipts should be separate from accepted stable closures. Promotion is explicit and evidence-dependent; retain earlier accepted manifests and Nix store closures for rollback.

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

**Updated exact remaining max-cut (source vs physical gates, 2026-11-04):**

| Gate | What now exists in this PR | Irreducible remaining evidence |
|---|---|---|
| G0 — baseline/attribution | 5.7/6.4 and historical ComfyUI, GEMM/WGM8, diffusion, Ollama/WhisperX incident evidence linked | Preserve original raw workflow/images where available and explicitly mark missing hashes; do not recast tests as never run |
| G1 — digest | Schaka source lock verified to the currently selected full SHA; eight-source pin parser; hosted immutable digest-lock proposal workflow | **Run** hosted OCI inspection, review the true digest, commit it to upstream.json (currently null), ensure actual published labels/pins correspond |
| G2 — Nix bootstrap | Source-written importer, staged in-image symlink resolver, hardlink scratch optimization, component source graph, mocked negative tests | Execute Nix flake eval/checks and real skopeo/umoci import on a Nix builder, preserve real candidate and source graph |
| G3 — runnable binary | Complete DT_NEEDED audit (including non-ROCm libraries) with explicit provider roots; RPATH/symlink static checks | Actually link/relocate the selected ROCm and venv payloads and supply a coherent compiler/libc/driver interface; demonstrate clean host execution without Ubuntu/Docker/foreign ROCm |
| G4 — physical acceptance | Real-command receipt capture and hash policy; partial 6/7 diffusion gate fails; ComfyUI image comparator; application capability receipts | Run Schaka suite + original ComfyUI image/workflow, WGM8/GemmFwdRest, repeat/miniUNet, WhisperX hangs and long-load controls **on documented physical gfx803 hardware**, retain bytes/sha256, inspect any failures |
| G5 — first release | Frozen accepted manifest policy, evidence-rechecking Cachix publish script, conditional fetchClosure outputs | Promote only from executed G1–G4 receipts; publish actual closures and prove clean Nix client substitution and numerical smoke |
| G6 — native source Nix | Full resolved source provenance and exact component DAG/rebuild impact from Schaka | Implement and **compile** source derivations for ROCr/CLR, rocBLAS, MIOpen, rocSOLVER, MIGraphX, PyTorch, ORT/Triton as required; pin all compiler/base and patch artifacts; verify same G4 suite |
| G7 — incremental fleet | Source and OCI change PR workflows, self-hosted import candidate workflow | Execute CI and self-hosted Polaris jobs; implement hash-based incremental source builds, candidate/stable separation, rollback and reproducible publication |

**No G1–G7 physical gate has been falsely marked complete.** PR #5 remains
draft pending real Nix execution, a reviewed digest lock and on-card receipts.
The 2025 Linux KFD callback repair is **already upstream** and not part
of G1–G7. Previously recorded newer hangs remain a distinct correctness
qualification; Schaka's WGM and MIOpen patches are original upstream work
reused with attribution, not new fixes claimed here.



## 4 November 2026: actual Leech/C2 dense GPU rejection and binary-factory join

**Physical host observation, source receipt preserved byte-for-byte:**
`docs/receipts/leech_gfx803_rocm64_dense_parity_rejected_20261104.json`,
SHA-256
`1e3b5640995eaf7ca93517a19cad7f85639926d1e9b817c8b6c0b296e516aa79`.
This is the actual **gfx803** GPU's extracted ROCm **6.4**
control stack, `torch 2.6.0+gitdae14f9`,
`HIP_LAUNCH_BLOCKING=1`, with the existing host-Python wrapper
correctly resolving the now-moved
`/mnt/truenas/comet-net/gfx803_compat_graph` checkout.
The host imported torch and enumerated the **8 GiB** device:
no failure in installation, Docker extraction, Python import,
old-ABI wrapper or device visibility.

The admission gate tested the original actual dense
**LeechTransformer** first, using batch=2, sequence=64,
hidden width=384 and vocabulary size=2048:

| Original CPU/HIP dense gate test | max absolute difference | exact gate status |
| --- | ---: | --- |
| Dense full logits, shape 2×64×2048 | **28.5572929382** | FAIL |
| Teacher normalized layer-1 input, shape 2×64×384 | **2.3883841038** | FAIL |
| Teacher layer-1 FFN, shape 2×64×384 | **1.1904456615** | FAIL |
| Same-device GPU repeat #1, logits | **0.2023429871** | FAIL |
| Same-device GPU repeat #2, logits | **0.2370784283** | FAIL |

The unmodified numerical gate correctly exited at **teacher
numerical parity**, did not reach C2-specific forward/gradient
tests and **did not authorize GPU training**. The receipt's
teacher SHA256 is
`581fdc3b4b6d169a03e2b06896e10d454fd4f819b40a2836c1d5b76849e4c674`.
The specific current C2 candidate digest
`f26a5d9246bd0e1f89330b4864124835e3df82bb86e4d1da23fdf5fb3c09224c`
differs from the earlier matched-objective CPU quality receipt's
student digest. Do not conflate student checkpoint identities
when later comparing outcomes; the dense-teacher failure
precedes any student-specific logic regardless.

The user reports the historic **direct-only** configuration was
active, but the original gate JSON did NOT record each individual
`MIOPEN_DEBUG_CONV_*` environment variable. New gate
source records those flags on future runs. Treat
`direct-only zero drift` as **valid for its measured
MIOpen/convolution scope**, not proof of Leech transformer
GEMM/attention correctness. This is not a reappearance of the
already-fixed 2025 KFD reset-callback regression; neither
does it prove the cause of later GPU reset incidents.

### Source-exact patch-class join, not a false solved claim

The frozen Schaka source lock at
`8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78`
contains
`patches/rocblas/wgm-miscompute-source.patch`,
`small-gemm-assembly-miscompute.patch`, and
`patches/miopen/winograd-fused-conv-miscompute.patch`.
The *WGM* patch itself identifies the bad class:
`gfx803` Tensile **assembly** kernels, with
`KernelLanguage=Assembly` / `ISA803_KLA`, that
use nonidentity `WorkGroupMapping`; Schaka forces WGM=1
at the solution-normalization stage. Its source notes retain
on-card evidence for this class. Schaka's source-class finding
and our March 2026 first-party `GemmFwdRest` kernel
ending `_ISA803_K1_KLA_..._WGM8` are a real
**kernel-class intersection**. But neither this receipt
nor our original direct-only flag proves that Leech's
QKV/attention GEMMs selected one of these exact faulty
solutions; an actual on-host kernel trace is the next
discriminator. The Winograd patch fixes a separate
1×1 fused-convolution selection miscompute; it has
no automatic relevance to transformer linear GEMMs.

The immediately relevant *candidate* linear algebra shape
set, inferred from the model layout (NOT measured selected
rocBLAS solutions), is:

| Original Leech operator | candidate (M,K,N) or grouped GEMM shape |
| --- | --- |
| QKV projection, 384 → 1152 | (128,384,1152) |
| Attention score QKᵀ, 8 heads × batch 2, width 48 | 16 × (64,48,64) |
| Attention-weighted V | 16 × (64,64,48) |
| Output attention projection, 384 → 384 | (128,384,384) |
| Dense FFN first projection, 384 → 1536 | (128,384,1536) |
| Dense FFN second projection, 1536 → 384 | (128,1536,384) |
| Final vocabulary head, 384 → 2048 | (128,384,2048) |

The exact transposition/stride/leading-dimension layout
and chosen Tensile solution require **runtime measurement**;
(M,K,N) alone does not determine kernel selection. Prior
Leech 6.4 records placed a first bad value near
`block0.q_raw`, so the **QKV projection** is the
initial highest-value test, not another MIOpen Winograd
benchmark. Do not equate a 1×1 convolution test with a
small GEMM test.

### Existing and newly joined test owners

- Existing first-party `check_drift_1x1.py`,
  `tests/drift_core.py`, `probe_diffusion.py`,
  profiler records and long-run WhisperX/Ollama incident
  RCA remain canonical for their original shapes and failure
  classes. They must not be rewritten to manufacture
  a green test.
- New `scripts/classify_leech_gfx803_gate.py` and
  `tests/test_leech_gfx803_gate_receipt.py`
  check that the original physical receipt is hash-locked,
  **negative**, teacher-first, and cannot be reported
  as C2-tested or Schaka-fixed; this is a source-regression
  check, **not a GPU test**.
- LeechTransformer PR #4 now has
  `scripts/diagnose_gfx803_leech_operator_boundary.py`
  and `scripts/run_gfx803_dense_diagnosis_nix.sh`.
  These reuse original checkpoint/token loaders and exact
  model hooks at embedding, block0 LN1, QKV, attention,
  LN2, FFN and output. Bare forward/repeat runs are compared
  with instrumented runs to detect host-copy synchronization
  **observer effects**; a passing hooked run must never
  override failed bare forward.
- Keep the existing Leech `gfx803_moe_gpu_gate.py`
  as the **independent fail-closed authoritative gate**:
  stage diagnostics only narrow the bug, never authorize
  training or upgrade the ROCm compatibility status.

### The revised exact physical/packaging max-cut

1. **G0, already discharged negatively:** original ROCm
   6.4 control imports/enumerates but fails numerical
   parity for the original dense Leech workload. Retain
   the original failure receipt without changing thresholds.
2. **G1, SOURCE-WRITTEN not executed:** on the same GPU,
   runtime, teacher digest and exact token-window digest,
   run the new real-module first-bad-stage probe, retaining
   both bare and hooked output. If hooks affect outputs,
   investigate launch-order/synchronization before
   blaming the apparently first bad named module.
3. **G2, OPEN:** capture actual selected rocBLAS/Tensile
   assembly kernel name, ISA, WGM, shapes, strides and
   current backend profile at the first failing GEMM.
   Establish whether `ISA803_KLA` and WGM!=1 are present.
   If NOT present, Schaka WGM normalization is not yet
   shown to address the Leech failure; redirect to the
   correct operator/class. Distinguish GEMM, small GEMM,
   fused MIOpen convolution, and layout/race problems.
4. **G3, OPEN:** repeat same-checkpoint/same-shape CPU↔GPU,
   exact numerical drift and intra-device repeat tests
   under the **pinned, actually imported and audited**
   Schaka 10.1 candidate, as well as Schaka's own suite.
   The source lock and an OCI importer by themselves
   are not evidence that 10.1 fixes the problem.
5. **G4, OPEN:** once dense teacher is numerically correct,
   rerun **strict focused C2** gradient parity, one AdamW
   step and long async stability on-card. Keep the
   independent dense-vs-C2 quality finding unchanged:
   CPU matched dense control CE **2.21605** still beats
   strict focused C2 **2.89186**.
6. **G5, OPEN:** accept a Nix/Cachix binary only after
   PR #5's required existing source/closure/provenance
   checks and on-card numerical/reset gates pass. A
   release may legitimately exclude **Leech** from its
   supported workload set while this canary fails;
   no release may claim Leech correctness based on
   a scoped convolution zero-drift test.

No new Golden Agda claim should promote project-run
hardware compatibility evidence to a mathematical or
vendor-guaranteed truth. The existing `GPUCompatibilityObservationExact`
and `GFX803CompatibilityReceiptExact` separate
visibility, numerical correctness and sustained reset safety.


## 6 Nov 2026: Leech QKV WGM8 trace and mandatory SGEMM preload

**Real, user-supplied hardware receipts** (not assistant GPU execution):
the [Leech PR #4 attribution receipt](https://github.com/chboishabba/LeechTransformer/blob/experiment/consumer-preserving-multiscale-codec-20261031/docs/receipts/gfx803_qkv_wgm8_attribution_20261106.json)
records the **unrenamed** kernel trace tar SHA256
`20abfb4c72b2cde0da42e5a1e1792ece80a162911bc59d9119a5fade22c3d9aa`.
In the `leech:block0:qkv` ROCTX interval a real rocBLAS
`sgemm(T,N,M=1152,N=128,K=384)` dispatch ran
`Cijk_Alik_Bljk_...ISA803_K1_KLA...WGM8`.
The exact original isolated QKV CUDA/HIP parity error was **4.1276249886**
with byte-identical profiled and unprofiled GPU output hashes and zero
same-GPU QKV repeat drift. The other uploaded tar has its kernel-name
field overwritten by profiler marker labels; its empty candidate list is
not a contradictory kernel observation.

This is now **G0 kernel-attribution CLOSED** for that observed QKV
dispatch. It is **not** yet a causal *fix* or proof of full dense/C2
numerical parity. In the **original native-input profile**, CPU and GPU QKV input bytes differed, despite native LayerNorm1 passing numerical tolerance. The **new physical CPU-copy control has now executed** and reports identical FP32 input bytes (SHA-256 `6e33dd589ce2fdc69f953fe1e195016076b883a7948f72a002de05fb49056cb5`, input max error **0.0**). With the same checkpoint and QKV, the output error persisted at **4.127624988555908**, repeats remained **0.0/0.0**, and the same `ISA803_KLA...WGM8` dispatched. The CPU-copy profiled/unprofiled GPU output SHA-256 is `5cf48cfd8c88fc29fbe4f10131232f7a6c245a5291039debada0e5f5349a1607`. This is a **first-party measurement reported in [commit `469bf00`](https://github.com/chboishabba/LeechTransformer/commit/469bf0026a05bb4ed57271a9aa1b9d038128dd79)**; full raw archives remain local at `artifacts/gfx803_qkv_cpu_copy/` and have not been independently rehashed from this branch. LN1 input mismatch is ruled out for the *isolated* QKV failure; WGM8 as the *sole cause* remains unproved.

Upstream authorship and independently produced observations are tracked explicitly in the [attribution/evidence ledger](GFX803_QKV_ATTRIBUTION_LEDGER_20261106.md): *Schaka's measured 0/14 vs 39/39 WGM assembly scan and source patch* ≠ *Schaka's independently discovered pervasive FP32 SGEMM failure and replacement* ≠ *this project's real QKV WGM8 dispatch and CPU-copy measurement* ≠ *future causal repair*.

### Schaka repair classes are distinct

- [WGM swizzle patch](https://github.com/Schaka/rocm-gfx803/blob/main/patches/rocblas/wgm-miscompute-source.patch)
  gates assembly `ISA803` solutions to `WorkGroupMapping=1`.
  Schaka's original same-ABI candidate scan recorded WGM8 assembly
  **0/14** correct and WGM1 assembly **39/39** correct.
- A **second FP32 SGEMM corruption mechanism** survived WGM repair in
  Schaka's historical 6.4.4 research and motivated
  [`gfx803_sgemm` and the preload shim](https://github.com/Schaka/rocm-gfx803/blob/main/patches/rocblas/sgemm-shim/sgemm_shim.cpp).
  His published final ROCm 10.1 image explicitly declares
  `LD_PRELOAD=/opt/rocm/lib/libgfx803_sgemm_shim.so`. It is an
  **essential part of his tested runtime contract**, not an optional
  user flag that Nix may discard while importing `/opt/rocm`.
- Existing [`rocm6.4.4/tools/rocblas_solution_scan.cpp`](https://github.com/Schaka/rocm-gfx803/blob/main/rocm6.4.4/tools/rocblas_solution_scan.cpp)
  uses the beta `rocblas_gemm_ex_get_solutions` API to enumerate
  same-library solution indices. Adapt its T,N dimensions and actual
  checkpoint data; do not copy solution indices across ROCm versions.

### New source-written release guard — not yet physically tested

- `scripts/gfx803_oci_runtime_contract.py` now rejects OCI manifests
  lacking Schaka's required `LD_PRELOAD`, `HSA_OVERRIDE_GFX_VERSION`,
  `ROC_ENABLE_PRE_VEGA` and `TORCH_BLAS_PREFER_HIPBLASLT`; it checks
  that the shim actually exists **inside the staged ROCm tree**, and
  records the equivalent relocated Nix preload path.
- The importer writes `runtime-env.json` and a **candidate-only**
  `required_sgemm_shim_preload`. The image digest-lock command also
  refuses a published image whose runtime environment fails the
  contract.
- The accepted `gfx803-sdk` Nix shell requires the relocated shim,
  exports the original Polaris/HIPBLAS settings, enables the shim and
  sets its store-backed `LD_PRELOAD`. This has **not** been Nix-evaluated
  or executed on a GPU in this environment.
- Promotion now requires a separate
  `sgemm_shim_loaded_and_correct="verified"` producer in addition to
  exact-path provenance, actual ELF relocation, and hash-backed
  numerical/device evidence. **Neither the importer nor this change
  manufactures that producer.**
- Tests cover absent/disabled/escaping preload library and rejection
  when an otherwise green candidate has no verified shim. Code
  committed; GH Actions run receipts remain outstanding.

### Decisive remaining targeted max-cut

1. **G1 — COMPLETED (first-party reported physical control):** native vs `--input-source cpu-copy` QKV compared at the same checkpoint/shapes; identical copied input bytes, error still 4.127624988555908, `WGM8` dispatch persists and profile/no-profile hash matches. Raw CPU-copy output receipts remain **local**, so this status is not an independently rehashed release acceptance receipt.
2. **G2 — OPEN:** execute WGM8-versus-WGM1 **same-library** candidate
   comparisons using Schaka's existing 6.4.4 solution scan, with
   exact T,N 1152×128×384, saved operands, 100+ repetitions and
   explicit rocBLAS status/trace receipts. Do not directly mix
   6.4/10.1 device libraries or assume WGM1 cures the other FP32 bug.
3. **G3** import reviewed, digest-pinned Schaka 10.1 into the Nix
   candidate; run QKV with the **stock shim enabled** and separately
   `GFX803_SGEMM_SHIM_DISABLE=1` as a same-image negative control,
   verifying the actual loaded preload and dispatch. No training.
4. **G4** re-run uninstrumented full teacher CPU↔GPU parity
   and repeated inference; only after its approval run strict C2
   gradient/AdamW gate. Then long-run hang/no-reset controls,
   ComfyUI original image regression, accepted Cachix release and
   native component derivations remain separate physical deliverables.

**New physical execution is now reported for the ROCm 6.4 CPU-copy QKV control only**, via LeechTransformer commit `469bf00`; the gfx803 Nix PR did not itself execute that test. **No WGM1 causal repair test, patched ROCm 10.1 hardware execution, training admission or native ROCm 10.1 binary release is claimed.** See the [typed upstream and first-party evidence ledger](GFX803_QKV_ATTRIBUTION_LEDGER_20261106.md) for original authorship and validation limits.


## 6 November: original-QKV causal A/B source implementation complete — physical runs pending

The source-level Leech A/B implementation has been pushed to
[LeechTransformer PR #4](https://github.com/chboishabba/LeechTransformer/pull/4).
The user has already physically executed and reported the **exact-byte
CPU-copy QKV negative control** in commit
[`469bf00`](https://github.com/chboishabba/LeechTransformer/commit/469bf0026a05bb4ed57271a9aa1b9d038128dd79):
FP32 QKV input SHA256 identical across CPU and GPU; **4.1276249886**
output error persists; GPU repeats 0.0/0.0; `ISA803_KLA...WGM8`
dispatch persists. The earlier LN1 input difference is thus *not*
the cause of that isolated original QKV failure.

### Implemented runnable operator path

- [`scripts/export_gfx803_qkv_fixture.py`](https://github.com/chboishabba/LeechTransformer/blob/experiment/consumer-preserving-multiscale-codec-20261031/scripts/export_gfx803_qkv_fixture.py)
  uses the **actual dense model checkpoint** and original token IDs to
  freeze CPU-produced LN1 QKV input, original QKV weights/bias,
  float32 and float64 CPU GEMM references as little-endian FP32 binary,
  with byte lengths, SHA-256, model/token/config identity and
  a fail-closed expected-input SHA check. No synthesized data.
- [`scripts/gfx803_qkv_solution_ab.py`](https://github.com/chboishabba/LeechTransformer/blob/experiment/consumer-preserving-multiscale-codec-20261031/scripts/gfx803_qkv_solution_ab.py)
  binds the **actual mapped 6.4 librocblas** from the existing
  `lib-compat`, implements the beta
  `rocblas_gemm_ex_get_solutions` / forced
  `rocblas_gemm_ex` calls on original T,N 1152×128×384 operands,
  checks real API statuses and each repeated GPU output, and
  refuses solution IDs from another library SHA.
  This is an adaptation of **Schaka's original existing scanner**,
  not an independently discovered upstream ROCm fix.
- [`scripts/run_gfx803_qkv_solution_ab_nix.sh`](https://github.com/chboishabba/LeechTransformer/blob/experiment/consumer-preserving-multiscale-codec-20261031/scripts/run_gfx803_qkv_solution_ab_nix.sh)
  reuses the **preserved** extracted 6.4 Nix control, runs every
  library-local solution in its own timeout-bounded process (100
  repetitions default) and profiles the named `leech:qkv:solution:ID`
  ROCTX marker. Source locks, original output bytes, hashes,
  failures and tool logs are retained. It is resumable, not a
  replacement for the actual user runtime.
- [`scripts/parse_gfx803_qkv_solution_ab.py`](https://github.com/chboishabba/LeechTransformer/blob/experiment/consumer-preserving-multiscale-codec-20261031/scripts/parse_gfx803_qkv_solution_ab.py)
  joins only actual profiler symbols inside the range; requires
  matching profiled/unprofiled first GPU output hash, same library
  and frozen fixture. **Do not** infer WGM1 from solution IDs or
  confuse `rocblas_gemm_ex` with the original PyTorch
  `rocblas_sgemm` path. Same-shape output differences support
  a mapping hypothesis, **not** complete patch validation.
- [`scripts/run_gfx803_qkv_shim_ab.sh`](https://github.com/chboishabba/LeechTransformer/blob/experiment/consumer-preserving-multiscale-codec-20261031/scripts/run_gfx803_qkv_shim_ab.sh)
  requires a **coherent real 10.1 Nix ROCm/Python/shim tuple**,
  uses the stock Schaka shim with `GFX803_SGEMM_SHIM_DISABLE=0`
  versus `1` in **separate processes** on the same QKV fixture;
  records 100 repeats, first actual GPU FP32 output bytes,
  actual mapped ROCm/shim paths and ROCTX profiler traces.
  It refuses to splice the 10.1 shim into the legacy 6.4 control.
- [`scripts/parse_gfx803_qkv_shim_ab.py`](https://github.com/chboishabba/LeechTransformer/blob/experiment/consumer-preserving-multiscale-codec-20261031/scripts/parse_gfx803_qkv_shim_ab.py)
  requires the real **on/off** marker-to-kernel joins and no
  profiler observer-effect before comparing the two arms. An
  unprofiled success or `LD_PRELOAD` declaration alone cannot
  establish a patched runtime or original Leech correctness.

### New binary-factory consumer and acceptance boundary

This gfx803 repository now contains
[`scripts/gfx803_leech_qkv_admission.py`](../scripts/gfx803_leech_qkv_admission.py)
and a Nix application:

```bash
nix run .#gfx803-verify-leech-qkv -- \
  --source /path/to/LeechTransformer/artifacts/gfx803_qkv_shim_101 \
  --fixture /path/to/LeechTransformer/artifacts/gfx803_qkv_wgm_ab/fixture \
  --runtime-root /nix/store/EXACT-ROCM101-ROCM \
  --evidence-root /path/to/gfx803-release-evidence \
  --candidate /path/to/imported-candidate.json \
  --lock nix/gfx803/upstream.json
```

**Only after the real 10.1 run and digest lock exist**:
the verifier copies *original bytes* atomically into an immutable
`evidence-root/leech_qkv` bundle, reopens actual `rocprofv3` marker and
kernel CSVs and exit codes, checks original model/input identities,
recomputes all FP32 output errors from the retained CPU reference
versus GPU tensor, requires **100 repeated on/off executions** and
exact SHA matches for the loaded rocBLAS and Schaka preload shim.
It can then attach **only the optional** `claimed_capabilities:
["leech_qkv"]` receipt to the still-unaccepted candidate.

The release/publish policy re-executes this **same raw-byte verifier**
whenever a manifest claims the optional `leech_qkv` capability;
a self-asserted green JSON or manually typed
`sgemm_shim_loaded_and_correct="verified"` does not suffice for that
claim. The independent seven required core gates, runtime relocation,
physical sustained-load, ComfyUI claims, digest pin and clean-client
Cachix promotion are still required as applicable. **A scoped QKV pass
does not admit C2 training, universal math kernels or a system-wide
no-reset guarantee.**

### Provenance and exact status

All original WGM and SGEMM investigations and patches remain **Schaka's**.
The user owns their independent kernel trace, CPU-copy control and
future on-card runs; this repo owns Nix integration/acceptance
infrastructure. See
[`GFX803_QKV_ATTRIBUTION_LEDGER_20261106.md`](GFX803_QKV_ATTRIBUTION_LEDGER_20261106.md).

| Gate | Current evidence |
| --- | --- |
| Original isolated QKV WGM8 identified | **Reported physical proof complete** |
| Exact CPU-derived input control | **Reported physical proof complete**, QKV still wrong |
| Same-library WGM1-versus-WGM8 forcing | **Source-implemented; not run** |
| Original 10.1 stock SGEMM shim on/off | **Source-implemented; no imported 10.1 runtime/physical execution** |
| Leech-specific source/trace/numeric evidence to Nix release | **Source-implemented, optional gate; not run** |
| Full dense, C2, sustained stable and downloadable binary release | **Open** |

CPU-only tests (not GPU proof):
`python -m unittest discover -s tests -p 'test_gfx803_leech_qkv_admission.py' -v`
and the Leech-side
`python -m unittest discover -s tests -p 'test_gfx803_qkv_*ab.py' -v`.
Both existing PRs remain draft pending real physical receipts.

### 6 November — Leech QKV causal A/B now operator-ready, not hardware-accepted

The [Leech original-operand A/B runbook](https://github.com/chboishabba/LeechTransformer/blob/experiment/consumer-preserving-multiscale-codec-20261031/docs/GFX803_QKV_WGM_SHIM_AB_RUNBOOK_20261106.md) and [Leech PR #4](https://github.com/chboishabba/LeechTransformer/pull/4) contain the source-written QKV fixture exporter, same-6.4-rocBLAS `rocblas_gemm_ex_get_solutions` candidate runner, ROCTX/rocprofv3 index-to-actual-WGM join and separate **coherent** Schaka 10.1 SGEMM shim ON/OFF runner. Each operates on the real original teacher's QKV operands and produces SHA-backed diagnostic receipts, not a training admission.

**Phase distinction:** QKV input identity was physically established by commit `469bf00`; **same-build WGM1-vs-WGM8, actual Schaka 10.1 import/shim-on-off, full dense parity and physical C2 are still open**. The Nix factory image digest is still awaiting review. Tests/CI are source-written and not yet verified on Actions. Schaka originated the WGM investigation/source patch and separate SGEMM correctness-first replacement; the local work is *independent first-party instrumentation and packaging*. See [contributor attribution ledger](GFX803_QKV_ATTRIBUTION_LEDGER_20261106.md).

## 6 November — Leech original-input WGM/shim hardening (no physical promotion)

Leech PR #4 now supplies stricter operator-ready 6.4 WGM8/WGM1 and imported
10.1 shim ON/OFF probes. Its source verifier requires >=100 complete
unprofiled repeats, source/runtime/tolerance and original-QKV hash binding,
real traced GEMM kernels and absence of profiler observer effects. The
standalone release-side consumer `scripts/gfx803_leech_qkv_admission.py`
checks the new **v2 joined trace-arm receipts**, independently rehashes
original output tensor bytes and requires actual `gfx803_sgemm_kernel`
in the ON control and its absence in OFF. The tests exercise rejection,
not physical success. Credit for the WGM fix and distinct FP32/GSU
correctness-first shim remains with Schaka.

| Evidence cut | Source implementation | Actual required next event |
| --- | --- | --- |
| A. Original ROCm 6.4 WGM8-vs-WGM1 | Leech solution scanner, fresh-run guard, repeated exact operands, traced kernel join | Run both mappings on hardware, check no observer effect, preserve raw hashes and failed cases |
| B. Schaka 10.1 image pin | Digest source lock, rootless OCI importer, relocated Nix preload contract | Obtain **real immutable image digest**, inspect labels, import coherent runtime |
| C. Same-image SGEMM-shim ON/OFF | Separate-process experiment and independent release-side byte verifier | Run both arms with genuine 10.1 Python/Torch and actual attached interposer |
| D. Physical application admission | Existing dense/C2 gates, original ComfyUI controls, kernel/reset and watchdog probes | Recheck actual bare dense parity, C2 gradients, long-run stability |
| E. Binary publication | Nix/Cachix manifest and closure policy source-written | Full accepted upstream/candidate evidence + independent clean-client install |

The first three source interfaces exist; the five **physical/digest/release
acceptance cuts are open**. A scoped QKV correction cannot authorize GPU
training or an accepted distro binary by itself. No new GitHub Actions or
Nix evaluation success is asserted.

### 10.1 profiling/runtime coherence addition

The original-QKV shim operator no longer lets a legacy system profiler or
an inherited interposer enter the 10.1 supervisor: the profiler executable
must be under the **selected imported ROCm Nix root**. The HIP process
captures actually mapped ROCm libraries and refuses foreign HIP/HSA/BLAS
components; the source parser and independent release-side verifier require
the mapping record and check its file paths under the selected root. A
candidate without an accessible same-runtime profiler can still obtain
numeric-only diagnostics, **not** a traced shim mechanism or a release gate.

The real image/digest, matching 10.1 profiler existence, ELF relocation and
physical zero-mismatch results remain to be established by the operator.
This is a stricter source gate, not an additional hardware success.


## 6 November — original LILA two-lane repair integration (not hardware acceptance)

LeechTransformer PR #4 now has the original-model dual-lane runner
`scripts/run_gfx803_lila_repair_gate.sh` and source contracts.

- **A / 6.4-cpu-linear:** retains the original extracted Nix 6.4 runtime but
  replaces GPU `nn.Linear` FP32 GEMMs through explicitly differentiable CPU
  GEMMs. It measures whether non-GEMM GPU operators, full dense forward,
  focused C2 backwards and optimizer step still diverge. This is a CPU/GPU
  **hybrid diagnostic**, NOT a demonstrated WGM1 in-place GPU dispatch fix,
  full GPU numerical correctness, training speedup or training admission.
  Source gate fails closed and refuses actual training promotion.
- **B / 10.1-schaka:** passes the original Schaka FP32 SGEMM shim as the
  *sole* preload to exact selected Nix runtime Python; before and after model
  execution the Leech gate checks actual mapped shim, HIP, rocBLAS, root
  identity and HIP 10.1 ABI. It reuses the checkpoint-bound original
  dense/C2 CPU/GPU forward, repeated forwards, gradients and AdamW update.
  **Still requires** immutable digest/OCI import, Schaka ON/OFF original
  QKV profiler evidence, physical model parity and sustained stress.
- **Independent evidence consumer:** this repository now contains
  `scripts/gfx803_lila_two_lane_receipts.py` with fail-closed offline
  adjudication and synthetic negative tests. It forbids hybrid promotion;
  for B it joins original source/checkpoint SHA with profiled ON/OFF shim
  traces, matching mapped roots, and original model parity. Even a positive
  B *candidate* never alone authorizes long-run training or a Nix/Cachix
  release. Command:

```bash
python3 scripts/gfx803_lila_two_lane_receipts.py \
  --lane 10.1-schaka \
  --gate-receipt /path/to/gfx803_lila_101_shim_new.json \
  --shim-ab-dir /path/to/original_qkv_shim_ab \
  --out /path/to/new_lila_101_adjudication.json
```

For A, omit `--shim-ab-dir` and choose `--lane 6.4-cpu-linear`.
Operator commands and limitations are in LeechTransformer
`docs/GFX803_LILA_DUAL_REPAIR_RUNBOOK_20261106.md`.
Additional **6.4-wgm1-qkv** diagnostic: LeechTransformer now reuses an
actual kernel-attributed correct WGM1 100-repeat original-QKV join, checks
the identical checkpoint and loaded rocBLAS SHA, and issues the selected
`rocblas_gemm_ex` kernel through an autograd-aware PyTorch forward wrapper.
All other GPU FP32 linear operations and that QKV's gradient GEMMs remain
CPU based. The release-side verifier now **reopens the exact prior 100-repeat
`trace_join.json`** and verifies its SHA against the model-process receipt,
rather than trusting a claimed WGM1 kernel label. Run this additional
diagnostic adjudication with:

```bash
python3 scripts/gfx803_lila_two_lane_receipts.py \
  --lane 6.4-wgm1-qkv \
  --gate-receipt /path/to/gfx803_lila_64_wgm1_new.json \
  --wgm-join /path/to/100_repeat_WGM1/trace_join.json \
  --out /path/to/new_lila_wgm1_adjudication.json
``` The independent adjudicator recognizes this as a third
**diagnostic mode** and still refuses native-GPU or training promotion.
The original `rocblas_sgemm` dispatcher is not modified.
No new hardware, ROCm 10.1 image digest, full native WGM1 dispatcher,
or numerically drift-free LILA installation is claimed by these changes.
