# Devlog

## 2026-11-09 — Schaka 10.1 shim RPATH relocation

- Preserved the original imported candidate and created a separate
  content-addressed candidate from the same digest-pinned OCI image.
- Replaced only the SGEMM shim's verified upstream RPATH
  `/opt/rocm/lib:/opt/rocm/core-10.1/lib` with
  `$ORIGIN:$ORIGIN/../core-10.1/lib` in writable staging before Nix import.
- Verified the relocated shim retains `librocblas.so.5` and `libamdhip64.so.7`
  DT_NEEDED entries and its `rocblas_sgemm` interposer symbol. A shim-only
  preload probe mapped candidate ROCm libraries and no `/opt/rocm` library.
- The result fixes a closure-packaging defect. It does not explain or repair
  the prior C2 GPU memory fault; numerical model acceptance remains open.

## 2026-11-06 — Leech QKV hardware attribution and independent upstream fixes

- The LeechTransformer first-party CPU-copy experiment at [commit `469bf00`](https://github.com/chboishabba/LeechTransformer/commit/469bf0026a05bb4ed57271a9aa1b9d038128dd79) demonstrates **identical CPU/GPU QKV inputs** (SHA-256 `6e33dd589ce2fdc69f953fe1e195016076b883a7948f72a002de05fb49056cb5`), yet **4.127624988555908** max CPU↔GPU error on the original block-0 QKV. Repeats are 0.0; profiler again selects `ISA803_KLA...WGM8`. This resolves the previous LN1-input-confounder question for this isolated run; it does not prove WGM8 is the only issue.
- Attribution is **not interchangeable**: **Schaka's** original WGM8 assembly discovery/WorkGroupMapping=1 patch and **his independent pervasive FP32 SGEMM failure**/correctness-first interposer are separate upstream contributions. Original source, measured 0/14 vs 39/39 WGM count, pinned Schaka patch links, first-party observation producer and non-promotion rules are preserved in [the ledger](docs/GFX803_QKV_ATTRIBUTION_LEDGER_20261106.md).
- This repo's contribution is Nix/OCI source tracking, runtime-contract integration, static/dependency checks and future independent numerical acceptance. The 10.1 source-locked factory remains a draft candidate; **no successful patched 10.1 QKV, accepted C2 training or binary release** is claimed.
- Next decisive run: same-ABI, same-original-input WGM1-vs-WGM8 candidate enumeration (reuse Schaka's existing solution scanner), then 10.1 SGEMM-shim ON versus OFF in isolated processes; only afterward consider original dense/C2 admission. Retain historical ComfyUI, 5.7/6.4 and GPU-reset data as separate first-party observations.


## 2026-03-23

- Started the long-running old-ABI framework rebuild loop.
- Confirmed the previous smoke was invalid because the driver still inherited `/opt/rocm` latest sonames.
- Added durable planning files so the rebuild loop has canonical memory.
- Forced the rebuild driver onto only the extracted old-ABI SDK/runtime roots and reran torch smoke.
- The current run is still compiling the torch wheel; no smoke result yet.
- The prior build failed in Kineto/roctracer headers, so a fresh `FRAMEWORK_REBUILD_ROOT=artifacts/pytorch-framework-rebuild-oldabi-kinetooff` run is in progress with `USE_KINETO=0`.
- The Kineto-off lane now fails in HIP-generated CUB objects under libstdc++ 15 with `__glibcxx_assert_fail` in `std::array`; the next attempt is to undefine `_GLIBCXX_ASSERTIONS` for this lane.
- The first `_GLIBCXX_ASSERTIONS` undef was strengthened to `-U_GLIBCXX_ASSERTIONS -D_GLIBCXX_ASSERTIONS=0` in case the HIP/CUB path reintroduces the assertion macro later in the toolchain.
- The live build log showed the workaround only appeared in top-level `CXX flags`; the generated `torch_hip_generated_cub*.hip.o.cmake` files did not carry it into `HIP_CLANG_FLAGS`, so the next fix is to export it through `HIPFLAGS` and `CMAKE_HIP_FLAGS`.
- After pushing the workaround through HIP-specific flags, the failure moved again: `amdgcn-link` / bundled `lld` from the old ROCm SDK now dies because it cannot load `libxml2.so.2`.
- The rebuild driver now searches for a host `libxml2.so.2` provider and prepends its directory to `LD_LIBRARY_PATH` before the HIP toolchain runs.
- The next live run showed the `CMAKE_HIP_FLAGS` env approach was malformed: CMake saw `-DCMAKE_HIP_FLAGS=` followed by stray `-U_GLIBCXX_ASSERTIONS -D_GLIBCXX_ASSERTIONS=0` tokens.
- The rebuild driver now passes the HIP assertion workaround through `CMAKE_ARGS` as one escaped `-DCMAKE_HIP_FLAGS:STRING=...` value instead.
