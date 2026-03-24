# Compactified context

## 2026-03-22

### Current decision

- The maintainable target is a reproducible Nix-owned `gfx803` stack, not permanent dependence on the historical Docker rebuilds.
- The first build boundary is PyTorch, not Ollama.
- The control lane must stay untouched:
  - frozen extracted `6.4` Python/framework layer
  - known-working selected runtime/math layer
- The upgrade lane must initially keep that same frozen Python/framework layer and vary only the ROCm/runtime side underneath it.

### What the recent ROCm-upgrade mapping established

- A fully synced latest-class userspace is not the first practical upgrade shell for Polaris:
  - pure extracted latest imports `torch 2.10.0+rocm7.2.0.gitb6ee5fde`
  - `torch.cuda.is_available()` is still `False`
  - a fully synced `6.4`-upgrade lane reaches the same GPU-gated state
- The first meaningful upgrade boundary with the frozen framework is smaller:
  - upgraded `libamd_comgr`
  - upgraded `librocm-core`
  - upgraded `libelf`
  - upgraded `libnuma`
  - upgraded `libdrm`
  - upgraded `libdrm_amdgpu`
  - upgraded `libdrm_radeon`
- That `safe-support` set preserves:
  - frozen extracted torch import
  - `torch.cuda.is_available() == True`
- The real ABI boundary is the HIP/HSA jump:
  - upgrading `libamdhip64`, `libhsa-runtime64`, `libhiprtc`, or libs that pull them in tends to either hide the GPU or break import on the frozen framework
- The newer framework rebuild work has now separated packaging bugs from runtime bugs:
  - the rebuilt torch wheel imports with the correct wheel-local `libtorch_*` libraries once the rebuild driver keeps `torch/lib` ahead of system `/usr/lib`
  - missing-library churn was a rebuild-driver/runtime-path problem and is now mostly automated away
  - the active blocker is now raw Polaris runtime compatibility under the latest-class ROCm line, not generic `.so` discovery

### Active migration shape

- `gfx803-pytorch-stack`:
  - control shell
  - frozen framework
  - control libs
- `gfx803-pytorch-stack-upgrade`:
  - first accepted upgrade shell
  - frozen framework
  - safe-support upgraded libs only
- Full latest-class userspace remains a separate experiment lane, not the default upgrade shell.
- The primary short-term upgrade lane is now `artifacts/rocm64-upgrade-oldabi/`, which preserves the old HSA/HIP ABI and upgrades only selected low-risk support libs around it.

### Next technical target

- The first full old-HIP/newer-math import sweep is now complete on top of the safe-support base.
- The coarse-pass `green` profiles turned out not to be real newer-math wins:
  - `rocblas_only`
  - `hipblas_only`
  - `hipblaslt_only`
  - `hipsparse_only`
  - `hipsolver_only`
  - `rocblas_bundle`
- Loader-resolution and hash checks showed why:
  - the frozen framework still requests the old sonames:
    - `librocblas.so.4`
    - `libhipblas.so.2`
    - `libhipblaslt.so.0`
    - `libhipsparse.so.1`
    - `libhipsolver.so.0`
  - the extracted latest lane provides newer sonames instead:
    - `librocblas.so.5`
    - `libhipblas.so.3`
    - `libhipblaslt.so.1`
    - `libhipsparse.so.4`
    - `libhipsolver.so.1`
  - so the coarse-pass profiles kept binding the control `6.4` math binaries, not newer ones
- The current real newer-lib overlays that were actually exercised are the ones with compatible sonames:
  - `miopen_only` used the newer `libMIOpen.so.1` payload and failed at the newer HIP ABI seam
  - `rocsolver_only` used the newer `librocsolver.so.0` payload and failed at the newer HIP ABI seam
  - `rocsparse_only` likewise fails at that seam
- The runtime bring-up work under the rebuilt framework lane established a sharper split:
  - full latest-class userspace causes `rocminfo` to fail with `HSA_STATUS_ERROR`
  - swapping only latest `libhsa-runtime64` onto the working base is enough to trigger that failure
  - swapping only latest HIP userspace is not enough to trigger that failure
  - restoring an old HSA-side cluster on top of the latest userspace can make `rocminfo` enumerate `gfx803` again
  - but rebuilt torch still fails there because latest `libamdhip64.so.7` expects newer ROCR/HSA symbols (`hsa_amd_memory_get_preferred_copy_engine@ROCR_1`)
- The active seam is therefore:
  - latest HSA breaks Polaris enumeration
  - old HSA restores enumeration
  - latest HIP requires newer HSA symbols
- The current reproducible hybrid runtime probes are:
  - `oldhsa_oldaql`
  - `oldhsa_oldprof`
  - `oldhsa_fullcluster`
- Those hybrid lanes are diagnostic only:
  - `rocminfo` works there
  - rebuilt latest-class torch does not
- The old-ABI preserved lane is now the primary short-term build target for the flake upgrade shell and the framework rebuild driver.
- The first old-ABI-targeted framework smoke was still not trustworthy because the rebuild toolchain/runtime leaked `/opt/rocm` latest sonames:
  - `torch.cuda.is_available() == False`
  - `ldd` showed `libamdhip64.so.7`, `librocblas.so.5`, and related latest-class libs resolving from `/opt/rocm/lib`
  - so the next concrete fix is a coherent extracted old-ABI ROCm SDK root plus a rebuild-driver guard that rejects that leakage
- The rebuild driver now starts from a clean `LD_LIBRARY_PATH` built from the intended old-ABI roots only, so the next smoke should no longer inherit `/opt/rocm` from the caller environment.
- The next build failure on the old-ABI lane came from Kineto / `roctracer` headers, so the rebuild driver should disable `USE_KINETO` for this lane rather than trying to compile profiling support from the extracted SDK.
- After disabling Kineto, the next old-ABI lane failure moved into HIP-generated CUB objects under libstdc++ 15:
  - `torch_hip_generated_cub.hip.o`
  - `torch_hip_generated_cub-RadixSortPairs.hip.o`
  - the failure is `std::array` hitting `__glibcxx_assert_fail` in `__host__ __device__` code
  - the first `_GLIBCXX_ASSERTIONS` workaround only reached top-level `CXX flags`
  - the generated HIP compile commands did not carry it into `HIP_CLANG_FLAGS`
  - the workaround is now injected through `HIPFLAGS` and CMake configuration arguments
  - the next failure moved to the ROCm LLVM toolchain itself: bundled `lld` cannot load `libxml2.so.2`
  - the rebuild driver now prepends a host `libxml2` provider before rerunning
  - a later live run showed the first `CMAKE_HIP_FLAGS` env injection was malformed at the cmake command line, so the driver now passes it through `CMAKE_ARGS` as a single escaped value
- The next practical migration target is no longer `latest HIP on gfx803`. It is:
  - preserve the old HSA/HIP ABI while upgrading around it where possible, or
  - patch the newer HSA/HIP line itself before expecting a latest-class framework lane to work

### User goal driving this

- Reach a state soon where the machine can be left to churn on the next meaningful long-running work, ideally recompiles or larger compatibility probes, without risking the known-working control lane.
