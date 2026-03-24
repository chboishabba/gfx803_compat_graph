# Devlog

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
