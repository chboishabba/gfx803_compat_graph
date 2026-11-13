# Schaka MIOpen direct solver qualification on gfx803 (13 Nov 2026)

## Intent

Build the **original** Schaka MIOpen correctness suite against the
selected Nix ROCm 10.1 MIOpen headers/libraries, then run **all** the
13 operation sweeps plus **every** original forced convolution solver
shape list. Do not substitute PyTorch conv2d for direct MIOpen testing.

Original source pin:
`Schaka/rocm-gfx803@8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78`

Source-owned files:
`tools/correctness-suite/build.sh`,
`tools/correctness-suite/*.cpp`, `common.hpp`,
`tools/correctness-suite/shapes/*.txt`.

This runner invokes Schaka's original `build.sh`, not a reimplementation,
and compiles all 14 upstream C++ translation units (13 operation sweep
binaries + `conv_solver_sweep`). Convolution runs force each original
solver through `MIOPEN_DEBUG_FIND_ONLY_SOLVER` and supply the pinned
shape file on stdin. The compile results and original binary hashes
become a durable, immutable build receipt.

## P0: preflight selected Nix runtime and toolchain — no GPU

The tested runtime root from the previous RX 580 receipts is:

```
/nix/store/p60hh8kqz90hpwnnl9pw5az5lhgx7mb0-staged-rocm
```

The ABI receipt found MIOpen's library at:

```
/nix/store/p60hh8kqz90hpwnnl9pw5az5lhgx7mb0-staged-rocm/core-10.1/lib/libMIOpen.so
```

This **does not establish** that MIOpen headers, a matching hipcc,
or the full development closure exist under the runtime prefix.

On TrueNAS, first check:

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
ROCM=/nix/store/p60hh8kqz90hpwnnl9pw5az5lhgx7mb0-staged-rocm
PREFIX="$ROCM/core-10.1"
SCHAKA=/mnt/truenas/comet-net/upstream-sources/schaka-rocm-gfx803-8fdcf7b-clean

test -f "$PREFIX/include/miopen/miopen.h" || echo "BLOCKED: selected MIOpen headers absent"
test -f "$PREFIX/lib/libMIOpen.so" || echo "BLOCKED: selected MIOpen shared object absent"
test -f "$PREFIX/include/hip/hip_runtime.h" || echo "BLOCKED: selected HIP headers absent"
git -C "$SCHAKA" rev-parse HEAD
command -v hipcc || echo "BLOCKED: hipcc missing from current environment"
```

Use an **existing immutable Nix hipcc path** configured for this
same ROCm profile (e.g., from your selected compiler derivation).
Do **not** fall back silently to `/opt/rocm` or an unrelated ROCm 6.4
toolchain. If headers or hipcc are unavailable, qualify/build a
matching development closure first and leave the original runtime
untouched.

## P1: source-pinned build, then isolated GPU execution

```bash
# Provide ACTUAL immutable Nix compiler path; this is not auto-guessed.
HIPCC=/nix/store/ACTUAL-HIP-COMPILER-PACKAGE/bin/hipcc

OUT=/mnt/truenas/comet-net/experiments/gfx803_schaka_miopen_20261113

# Compiles against the specified Nix ROCm prefix; no intentional GPU test.
python3 scripts/gfx803_schaka_miopen_qualification.py \
  --source "$SCHAKA" --rocm-prefix "$PREFIX" --hipcc "$HIPCC" \
  --out "$OUT" --build --build-timeout 1800

# Only after build.json shows status=built and every binary SHA recorded.
# Requires a healthy idle RX 580; 4 operation/solver sweeps per batch.
python3 scripts/gfx803_schaka_miopen_qualification.py \
  --source "$SCHAKA" --rocm-prefix "$PREFIX" --hipcc "$HIPCC" \
  --out "$OUT" --resume --execute --batch-size 4 --timeout 240
```

Repeat the second command until `status=all-targets-attempted`
or `counts.unassayed=0`. After each batch, inspect
`$OUT/matrix.json` and GPU logs. A GPU fault, timeout, or
supervisor interruption is persisted and **halts** further work;
resume requires manual GPU health review and
`--recovered-after-fault` acknowledgement. Historical faults are
never automatically rerun.

A 13-operation sweep is run in its original process; a forced
solver's whole original shape file is run in its own process.
This is process-level isolation per upstream suite entrypoint, not
isolation for *each individual shape* inside a solver file.
For any solver that crashes, smaller shape-level diagnosis can follow
once GPU recovery is verified.

## P2: interpretation

`passed` requires original upstream binary return code zero, exactly
one original `SUMMARY: N cases/shapes tested, M WRONG` footer,
`N > 0`, `M=0`, and at least one non-skipped case.

`empty-results` covers no original summary or no applicable solver
shape; `failed` includes original numerical mismatches or nonzero
return; `fault` and `timeout` trigger the GPU inspection stop.

**Important:** `upstream_skip_lines` retains original solver
inapplicability; reporting a passing sweep does not mean every solver
shape ran. A future enhancement should trace actual selected solver
IDs, ensure the loaded HIP/MIOpen library maps match the selected
closure, and compare GPU results with independent references.

Any CMake/CTest test suites built from TheRock remain a **separate**
execution lane using `gfx803_rocm_ctest_qualification.py`.
The runner here targets Schaka's existing standalone MIOpen C++
suite, not TheRock's CTest tree.

## Gates still open

- Matching MIOpen/HIP **development** artifacts and successful
  source-pinned compilation on this host;
- all original operation and per-solver shape sweeps executed with
  the selected runtime and recorded results;
- explicit proof of runtime loaded-library coherence;
- MIOpen backward, MHA Find2.0, other non-swept solvers, long-run
  stability, HIP/HSA/KFD original suites;
- Schaka PR #8 rebuilt TopK A/B performance measurements.

No release or full-ROCm API qualification is implied by this script.


## P3: join original results into the ten-layer coverage atlas

Only after physically executing the MIOpen sweeps, append their
original matrix to the atlas with an independent destination:

```bash
python3 scripts/gfx803_rocm_coverage_report.py \
  --miopen-receipt "$OUT/matrix.json" \
  --schaka-receipt fp16-gemm=/mnt/truenas/comet-net/experiments/gfx803_schaka_fp16_20261113/matrix.json \
  --schaka-receipt triton-dot=/mnt/truenas/comet-net/experiments/gfx803_schaka_triton_20261113/matrix.json \
  --out /mnt/truenas/comet-net/experiments/gfx803_rocm_layers_miopen_20261113.json
```

This displays bundle-level MIOpen numerical outcomes independently
from CTest and PyTorch. It retains skipped/inapplicable solvers,
unassayed bundles and any faults. It does not claim universal MIOpen
function support or loaded-library coherence.
