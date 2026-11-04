# Out-of-tree gfx803 target registration for ROCm/TheRock.
#
# Current TheRock explicitly includes this file when present:
#   cmake/therock_custom_amdgpu_targets.cmake
#
# Keep target registration separate from runtime restoration patches so build
# support, device enumeration, execution correctness, and release promotion stay
# independently testable.

therock_add_amdgpu_target(gfx803 "Polaris / RX 460-590" FAMILY dgpu-all gfx803-dgpu
  EXCLUDE_TARGET_PROJECTS
    hipBLASLt
    hipSPARSELt
    composable_kernel
    rocWMMA
    rocprofiler-compute
    MIOpen
)
