# Status

- Phase: old-ABI framework rebuild bring-up
- Milestone: 1 in progress
- Control lane: preserved and untouched
- Upgrade lane: materialized
- SDK root: extracted
- Current blocker: the previous `CMAKE_HIP_FLAGS` injection was malformed at the CMake command line; the workaround is now being passed via `CMAKE_ARGS` as a single HIP flag value before the next rerun
