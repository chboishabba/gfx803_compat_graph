# gfx803 / Leech QKV attribution and evidence ledger — 6 November 2026

This is a **typed source/claim ownership record**, not a credit transfer or proof that a particular patch repairs Leech. Read it beside [the Nix factory roadmap](NIX_GFX803_BINARY_FACTORY_ROADMAP.md) and [LeechTransformer PR #4](https://github.com/chboishabba/LeechTransformer/pull/4).

## Attribution firewall

**Source assertion ≠ first-party reproduction ≠ numerical replay ≠ mechanism identification ≠ tested repair ≠ stable physical release.** The GitHub checkout, read access, Nix importer, and authoring of a comparator do not confer authorship of the upstream work or turn a reported result into independent verification. Preserve the original primary link and author, source revision, exact test/receipt producer, bounded claim, reproduction conditions, and any unverified/promotable edge. A source-author's board measurements are not our board measurements. A correctly identified dispatch is not proof of causal failure, and a numerical pass at one shape is not generalized ROCm support.

| Owner and primary authority | Bounded supported result | Local reuse and non-promotion |
| --- | --- | --- |
| **Schaka** — [original WGM8 investigation](https://github.com/Schaka/rocm-gfx803/blob/8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78/patches/rocblas/wgm-miscompute.sh), [WGM source patch](https://github.com/Schaka/rocm-gfx803/blob/8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78/patches/rocblas/wgm-miscompute-source.patch) | Schaka's RX 470, ROCm 6.4.4 solution scan: **0/14 WGM8 gfx803 assembly solutions correct**, **39/39 WGM1 gfx803 assembly solutions correct**; **2/2 WGM8 HIP-source solutions correct**. He identified an assembly mapping defect and implemented the gfx803-scoped WorkGroupMapping=1 correction. | Do **not** attribute that empirical result or patch implementation to this repository; Leech's independently captured `ISA803_KLA...WGM8` is an overlapping *kernel class*, not proof that changing WGM alone fixes it. |
| **Schaka** — [6.4.4 kernel research](https://github.com/Schaka/rocm-gfx803/blob/8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78/rocm6.4.4/KERNEL_BUGS.md), [original correctness-first SGEMM kernel](https://github.com/Schaka/rocm-gfx803/blob/8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78/patches/rocblas/sgemm-shim/gfx803_sgemm.h), [dispatch shim](https://github.com/Schaka/rocm-gfx803/blob/8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78/patches/rocblas/sgemm-shim/sgemm_shim.cpp) | Independent *second* FP32 GEMM failure mode: repeated standard-path rocBLAS/Tensile calls can corrupt results even after WGM repair. Schaka wrote/validated a replacement and a dispatch interposer; this is distinct from MIOpen Winograd, the small-shape assembly issue, or the 2025 KFD callback. | Reuse the patch and tests with immutable source identity. **Do not** state WGM1 will solve all Leech parity or that the local Nix wrapper authored the replacement. |
| **Schaka** — [published final OCI runtime declaration](https://github.com/Schaka/rocm-gfx803/blob/8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78/docker/final.Dockerfile) | His runtime explicitly sets `LD_PRELOAD=/opt/rocm/lib/libgfx803_sgemm_shim.so`, `HSA_OVERRIDE_GFX_VERSION=8.0.3`, `ROC_ENABLE_PRE_VEGA=1`, `TORCH_BLAS_PREFER_HIPBLASLT=0`. | Nix repackaging must retain a correctly relocated interposer and independently prove it was loaded and computes correctly. Copying `/opt/rocm` without the environment is **not** equivalent to his intended container runtime. No real 10.1 Nix replay accepted here. |
| **chboishabba / first-party gfx803 and Leech GPU tester** — [original negative Leech gate](https://github.com/chboishabba/LeechTransformer/blob/469bf0026a05bb4ed57271a9aa1b9d038128dd79/docs/receipts/gfx803_control_leech_c2_rejected_20261104.json), [original trace attribution ledger](https://github.com/chboishabba/LeechTransformer/blob/469bf0026a05bb4ed57271a9aa1b9d038128dd79/docs/receipts/gfx803_qkv_wgm8_attribution_20261106.json) | On the user's actual gfx803 6.4 control, original model: first divergent `block0.qkv`; `sgemm(T,N,1152,128,384)`, `ISA803_KLA...WGM8`, QKV max CPU↔GPU error **4.127624988555908**. Original unrenamed profiler tar SHA-256 `20abfb4c72b2cde0da42e5a1e1792ece80a162911bc59d9119a5fade22c3d9aa`. | These are the user's **new independent measurements**, not Schaka's 0/14 vs 39/39 study or an implemented repair. The logged profile and unprofiled outputs match for this isolated call. C2 training remained rejected. |
| **chboishabba / first-party gfx803 and Leech GPU tester** — [CPU-copy control commit `469bf00`](https://github.com/chboishabba/LeechTransformer/commit/469bf0026a05bb4ed57271a9aa1b9d038128dd79) | CPU-derived LN1 input copied to GPU: **identical CPU/GPU input SHA-256** `6e33dd589ce2fdc69f953fe1e195016076b883a7948f72a002de05fb49056cb5`, input max difference 0.0; QKV output error **4.127624988555908**; isolated GPU repeat errors 0.0/0.0, same `ISA803...WGM8`, profiled and unprofiled GPU output SHA-256 `5cf48cfd8c88fc29fbe4f10131232f7a6c245a5291039debada0e5f5349a1607`. | **Exact-input confounder eliminated for the isolated QKV test**, as described in the user's commit. The raw `artifacts/gfx803_qkv_cpu_copy/` logs are local and are **not** themselves committed; this document is a bounded report from the committed account, **not** an independently rehashed raw receipt. Still **no** same-build WGM1 A/B, patched 10.1 shim-on/off control, accepted Leech or C2 training. |
| **chboishabba / gfx803_compat_graph integrator** — [draft Nix binary-factory PR #5](https://github.com/chboishabba/gfx803_compat_graph/pull/5) | OCI metadata/pins, Nix import policy, static shim contract, candidate evidence admission and checks, and roadmap integration. | This is **repackaging/consumer verification infrastructure**, not Schaka's kernel-source patch or proof of a runnable/published modern ROCm binary. |
| **AMD and kernel contributors** — [Linux upstream commit `34659c1`](https://github.com/torvalds/linux/commit/34659c1a1f4fd4c148ab13e13b11fd64df01ffcd) | KFD gfx7/8 SDMA doorbell callback repair authored by Alex Deucher, `Reported-by: Johl Brown`, reviewed by Jonathan Kim. | This particular 2025 KFD regression was upstream-fixed; it is not the cause of the proven QKV numerical error by default, and newer hangs are separate measured cases. |
| **Other upstream/community owners** — [lamikr/rocm_sdk_builder](https://github.com/lamikr/rocm_sdk_builder), [Robert Rosenbusch/gfx803_rocm](https://github.com/robertrosenbusch/gfx803_rocm), [Luca Bruni CLR #269](https://github.com/ROCm/clr/issues/269), [AMD/TheRock](https://github.com/ROCm/TheRock/issues/9118) | Distinct source-build, compatibility, ROCm 7+ doorbell, and upstream target-restoration contributions. | Retain direct links and individual authors; community 10.x operation does **not** equal AMD release certification. |

## Exact next ownership/evidence gates

1. **Causal workgroup mapping test (open):** adapt [Schaka's existing solution enumerator](https://github.com/Schaka/rocm-gfx803/blob/8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78/rocm6.4.4/tools/rocblas_solution_scan.cpp) for the same library, original T/N GEMM, and exact saved operands. Require independently executed WGM1-vs-WGM8 solution indices, return statuses, 100+ repeated comparisons, kernel names and hashes. The choice of index is not portable across library builds.
2. **Distinct SGEMM runtime test (open):** pin and import Schaka 10.1, preserve `LD_PRELOAD` to the relocated `libgfx803_sgemm_shim.so`, attest the actually mapped interposer and perform separate process *on* vs `GFX803_SGEMM_SHIM_DISABLE=1` *off* with identical original input. Preserve the author's upstream work; do not mix 6.4 and 10.1 libraries.
3. **Consumer acceptance (open):** repeat original bare Leech dense CPU↔GPU parity and GPU repeats; only if admitted test C2 gradients/AdamW and long-run reset safety. A core Nix/Cachix release separately needs complete closure, host-driver/runtime coherence, and clean independent installation.

**Current state:** first-party QKV **input identity and kernel identity verified by the reported physical tests**; *repair effectiveness, general numerical correctness, C2 training and accepted ROCm 10.1 binaries remain unproved*. Treat local-artifact-only measurements as reported until original bytes or independently reproducible receipts are available.

## Source-method and current consumer integration — 6 November

The Leech PR #4 implementation now binds the WGM experiment to 100+ complete
per-solution runs, one properly attributed profiled dispatch and the same
original teacher, CPU-copy input/weights, runtime SHA, tolerances and GEMM
geometry. Its 10.1 shim path requires source-identical separate-process
ON/OFF arms; the independent verifier in this repository reopened the raw
FP32 tensor and profiler CSV rather than trusting an asserted JSON pass.

**Additional original Schaka finding (attributed, not reproduced here):**
the [pinned shim source](https://github.com/Schaka/rocm-gfx803/blob/8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78/patches/rocblas/sgemm-shim/sgemm_shim.cpp)
records Schaka's diagnosis of the broader standard-path FP32 problem:
rocBLAS's device memory pool may reuse GlobalSplitU scratch without zeroing,
while the gfx803 GSU reduction assumes zero-initialized accumulation.
Schaka compared workspace-zeroing with his handwritten replacement and
reported the latter faster on tested shapes. This upstream mechanism claim
must remain distinct from (i) his separately measured WGM8 assembly-mapping
defect, (ii) the first-party Leech QKV observation, and (iii) an independent
kernel-level causal reproduction on this user's physical card. The actual
replacement kernel is `gfx803_sgemm_kernel` from his pinned header; merely
seeing `LD_PRELOAD` in the environment is not proof it dispatched.

**No unearned promotion:** the new source validators deliberately refuse
stale output directory reuse, truncated repeats, mismatched numeric
thresholds, replaced original bytes, profiler-renamed marker symbols and
foreign runtime hashes. The code remains source-written until its
regressions and both physical A/B arms have executed. The Nix digest,
full-model/C2 gates, reset endurance and Cachix publication remain OPEN.
