# RX 580 / gfx803: whole-ROCm qualification max-cut (2026-11-12)

## North star and boundaries

Restore as much **original, correctly functioning HIP/ROCm compute** as
possible on old/unsupported AMD GPUs, with versioned, device-specific
receipts. Reuse upstream ROCm tests and implementations; do not invent
a parallel test universe or declare missing APIs from a PyTorch skip.

**What exists today:** source-bound 1,774-case PyTorch OpInfo discovery
(1,583 pass, 183 historic skip/non-pass, three ordinary failures,
four complex64 fault candidates, one external interruption);
Schaka's existing backend probes; a nine-asset source inventory;
a composed Nix runtime with proven RX 580 execution; candidate-level
TopK semantic evidence and native LILA/C2 training batches.

**What this implementation adds:** `qualification/rocm_layers_v1.json`
contains the ten coverage layers and their original upstream test
entrypoints; `scripts/gfx803_rocm_ctest_qualification.py` discovers
and optionally executes installed upstream CTest targets under exact
source/runtime/tool pins; `scripts/gfx803_rocm_coverage_report.py`
joins original CTest receipts into an evidence-only ten-layer report.

None of these new tools claims a GPU execution result yet.

## Upstream reusable tests and responsibilities

| Layer | Existing upstream owner / reuse | Outstanding gate |
|---|---|---|
| PyTorch OpInfo | pinned upstream `test/test_ops.py` and existing full-sweep/replay runners | finish 183 reason triage, 3 failures, 4 faults; widen dtype/grad coverage |
| rocBLAS / hipBLAS | TheRock `--blas --tests`; Schaka `verify.py` + FP16 GEMM sweep | direct L1/L2/L3/test matrices, algorithm/dtype coverage |
| MIOpen | TheRock `--miopen --tests`; Schaka MIOpen solver-boundary suite | full algorithms/solver and backward coverage |
| rocSOLVER / rocSPARSE | TheRock `--blas --solver --sparse --tests` | direct dense/sparse/factorization cases |
| rocFFT / rocRAND / rocPRIM | TheRock `--fft --rand --prim --tests` | enumerate actual tests and GPU coverage |
| HIP runtime | TheRock `--hip-tests --tests` | memory, copies, streams, graphs, events and errors |
| ROCr / HSA / KFD | TheRock `--rocrtst --kfdtest --tests` | queues, signals, KFD and page mappings |
| LLVM / HIP compiler | pinned compiler builds + Schaka coherence/negative control | wave64, atomic, barrier, optimization, ISA and codegen tests |
| Triton | Schaka `triton_dot_probe.py` and upstream Triton tests | broad generated-kernel matrix, dtype/layout/reductions |
| Composed workloads | source-owned C2/LILA and dense baseline workflows | pressure, checkpoint/reload, optimizer, long GPU stability |

Official reuse references:
- https://github.com/ROCm/TheRock/blob/main/TESTING.md
- https://github.com/ROCm/TheRock/blob/main/BUILD_TOPOLOGY.toml
- https://github.com/ROCm/TheRock/blob/main/docs/development/installing_artifacts.md
- https://rocmdocs.amd.com/projects/HIP/en/latest/install/build.html

TheRock groups math packages into BLAS/SOLVER/SPARSE, FFT, RAND, PRIM
and MIOpen artifacts, while HIP/ROCr/KFD tests have distinct artifacts.
Do NOT assume current TheRock `main` provides gfx803 test binaries;
first validate the architecture target and the ABI/compiler/runtime
match against the selected ROCm 10.1 Nix closure. Do not mix unrelated
TheRock artifacts from newer lines into the composed 10.1 candidate
and call those results qualified. If artifacts are unavailable,
record `upstream-tests-unavailable-for-selected-profile`, not pass.

## Phase P0: non-executing test discovery on actual pinned sources

TheRock supports CMake BUILD_TESTING and `ctest --test-dir ...`.
Build or restore tests using **their own upstream build recipes**,
with exact source SHA, GPU target and selected Nix ROCm closure.
Do not invent executable names or manually wrap tests as green.

Use existing installed, configured `CTestTestfile.cmake` directories
for each component. For example:

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
python3 scripts/gfx803_rocm_ctest_qualification.py \
  --layer hip-runtime \
  --source-dir /ACTUAL/PINNED/ROCM-SYSTEMS-OR-THEROCK-SOURCE \
  --source-sha ACTUAL_40_CHARACTER_SHA \
  --rocm-root /nix/store/ACTUAL-SELECTED-ROCM-CLOSURE \
  --ctest /nix/store/ACTUAL-CMAKE-PACKAGE/bin/ctest \
  --test-dir /ACTUAL/CONFIGURED/CTEST/BUILD   --out /mnt/truenas/comet-net/experiments/gfx803_hip_ctest_qual_00
```

Without `--execute`, this only runs CTest inventory discovery.
It refuses missing/empty suites, wrong pinned source revisions,
a modified source worktree, non-Nix ROCm closure, non-Nix CTest,
duplicate test IDs and preexisting evidence destinations. The
discovered suite is recorded in `matrix.json` with all tests
`unassayed`, `release_admitted=false`,
`runtime_coherence_verified=false`.

## Phase P1: bounded on-card component execution

Once the host and GPU are healthy and no C2/LILA training or TopK
benchmark is active:

```bash
python3 scripts/gfx803_rocm_ctest_qualification.py \
  --layer hip-runtime \
  --source-dir /ACTUAL/PINNED/ROCM-SYSTEMS-OR-THEROCK-SOURCE \
  --source-sha ACTUAL_40_CHARACTER_SHA \
  --rocm-root /nix/store/ACTUAL-SELECTED-ROCM-CLOSURE \
  --ctest /nix/store/ACTUAL-CMAKE-PACKAGE/bin/ctest \
  --test-dir /ACTUAL/CONFIGURED/CTEST/BUILD \
  --out /mnt/truenas/comet-net/experiments/gfx803_hip_ctest_qual_00 \
  --resume --execute --batch-size 16 --timeout 180
```

Resume against the same `--out` directory. Cases are run through
`ctest -R '^escaped-original-test-name$'` and require a literal
`1`-test executed/passed summary; an empty CTest match cannot pass.
Individual stdout/stderr SHA-256, exact selected tests, source SHA,
CTest binary SHA, CTest discovery fingerprint and ROCm store identity
are retained.

Faults and timeouts halt for explicit KFD/GPU inspection/recovery.
Only after recovery use `--recovered-after-fault` to acknowledge
the existing hazardous nodes; faulting cases are not automatically
retried or promoted. Individual CTest pass is labeled
`ctest-pass`, **not numerical CPU/GPU parity, validated runtime
coherence or all-API compatibility**.

## Phase P2: cross-layer coverage atlas

```bash
python3 scripts/gfx803_rocm_coverage_report.py \
  --receipt hip-runtime=/mnt/truenas/comet-net/experiments/gfx803_hip_ctest_qual_00/matrix.json \
  --out /mnt/truenas/comet-net/experiments/gfx803_rocm_layers_qual_00.json
```

Add one `--receipt layer-id=/exact/original/matrix.json` for each
actually tested component. The report retains unknown layers and
distinct ROCm roots; never merges two incompatible runtimes into one
qualified platform. Source inventory and existing PyTorch summary
are retained independently from physical CTest results.

## P3: decisive physical and release gates still open

1. Exact TheRock/gfx803 build or artifact restore for **matching**
   HIP/ROCr/KFD and BLAS/FFT/RAND/PRIM/MIOpen/solver/sparse tests.
2. All physically discovered and safely executable tests plus explicit
   API/shape/dtype/forward/backward coverage inventory; record
   absent/unbuilt tests and excluded functions.
3. PyTorch 183 skip reasons (16 reviewed to date), three ordinary
   OpInfo failures, four complex64 VM fault candidates.
4. Schaka PR #8: rebuild reviewed helper/verified-driver TopK wheel,
   paired benchmark patched/unpatched, and narrower dispatch decision
   only if real hardware evidence warrants it.
5. Independently selected compiler/Triton/higher-level workload probes,
   source-identical runs, fault recovery and sustained GPU stress.
6. Clean-client Cachix restore and whole-closure ABI coherence, followed
   by per-card profiles (RX 470, 480, 580, 590 etc.) independently.

Do not mark any of these closed based solely on a source listing,
test collection, one-card result, or an upstream project's documented
support for a different GPU family.

**No CI dependency; no Docker requirement for qualification; use
pinned Nix closures, original source tests and local hardware receipts.**


## P1a: Run two original Schaka direct suites without TheRock artifacts

`scripts/gfx803_schaka_reuse_assay.py` reuses the literal, original
Schaka `fp16_gemm_sweep.py` (all **27** cases) and
`triton_dot_probe.py` (**bf16/fp16/fp32/i8**), extracted from pinned
source AST declarations. No test implementations are copied.

Both suites require the original source at SHA
`8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78`, the selected
**Nix** Python wrapper, and the selected ROCm store; the tool rejects
source changes and refuses to overwrite receipts. Because the probes
are actual GPU executables, first plan without `--execute` and
ensure no conflicting C2/LILA, OpInfo or benchmark tenant is active.

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
SCHAKA=/ACTUAL/PINNED/SCHAKA-SOURCE
PY=/nix/store/ACTUAL-TORCH-PYTHON-WRAPPER
ROCM=/nix/store/ACTUAL-SELECTED-ROCM-ROOT
FP=/mnt/truenas/comet-net/experiments/gfx803_schaka_fp16_20261112
TR=/mnt/truenas/comet-net/experiments/gfx803_schaka_triton_20261112

python3 scripts/gfx803_schaka_reuse_assay.py \
  --suite fp16-gemm --schaka-source "$SCHAKA" \
  --python-wrapper "$PY" --rocm-root "$ROCM" --out "$FP"
python3 scripts/gfx803_schaka_reuse_assay.py \
  --suite fp16-gemm --schaka-source "$SCHAKA" \
  --python-wrapper "$PY" --rocm-root "$ROCM" --out "$FP" \
  --resume --execute --batch-size 4 --timeout 120

python3 scripts/gfx803_schaka_reuse_assay.py \
  --suite triton-dot --schaka-source "$SCHAKA" \
  --python-wrapper "$PY" --rocm-root "$ROCM" --out "$TR"
python3 scripts/gfx803_schaka_reuse_assay.py \
  --suite triton-dot --schaka-source "$SCHAKA" \
  --python-wrapper "$PY" --rocm-root "$ROCM" --out "$TR" \
  --resume --execute --batch-size 1 --timeout 120
```

Repeat `--resume --execute` in safe batches; stop on a GPU fault.
The FP16 sweep uses Schaka's own numerical pass predicate and
reports `source-verified-pass` where that predicate is satisfied.
The Triton probe's `ok` flag only means execution returned; although
it prints `max_err`, it does **not** threshold that error. Therefore
the adapter reports `numeric-unqualified` on an apparently successful
Triton run, NOT a numerical pass.

To aggregate existing direct-suite physical receipts with CTest:

```bash
python3 scripts/gfx803_rocm_coverage_report.py \
  --schaka-receipt fp16-gemm="$FP/matrix.json" \
  --schaka-receipt triton-dot="$TR/matrix.json" \
  --out /mnt/truenas/comet-net/experiments/gfx803_rocm_layers_direct_20261112.json
```

This adds only the exact tested cases to their original layer; it
does not mark untested BLAS signatures, compiler options, Triton
programs or ROCm APIs as supported. Direct-suite and CTest receipts
can later be joined without changing any original matrix.


## P0b: static ROCm library ABI inventory (no GPU calls)

`scripts/gfx803_rocm_abi_inventory.py` inventories actual shared-object
candidates inside the selected Nix ROCm closure. It detects missing
libraries, ambiguous ABI revisions and the set of exported ELF
symbols using an immutable Nix `llvm-nm`/GNU `nm` executable. Unlike
OpInfo or CTest, this is an **availability surface**, not correctness
validation. Exported dynamic symbols include private implementation
details and do **not** enumerate every public API declaration.
Header-only rocPRIM/hipCUB/rocThrust, compiler-generated kernels,
Triton JIT and Python interfaces require other inventories.

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
python3 scripts/gfx803_rocm_abi_inventory.py \
  --rocm-root /nix/store/ACTUAL-SELECTED-ROCM-CLOSURE \
  --nm /nix/store/ACTUAL-BINUTILS-PACKAGE/bin/nm \
  --out /mnt/truenas/comet-net/experiments/gfx803_rocm_abi_20261112 \
  --symbols
```

Each library receives a candidate list and, if unambiguous,
symbol inventory file, binary SHA-256 and inventory SHA-256.
No GPU operations are executed. A missing shared object, symbol
or library is a hypothesis about closure contents, **not** a
measured device functionality failure. API header inventory and
symbol→test traceability remain additional open gates.

## CTest build-to-source binding

The CTest adapter also requires a `CTestTestfile.cmake` and nearby
`CMakeCache.txt` with `CMAKE_HOME_DIRECTORY:INTERNAL` matching the
exact pinned source checkout. It records SHA-256 for both metadata
files and rejects mismatched CMake homes. That still does not prove
the process loaded the selected runtime libraries during GPU
execution: a separate mapped-library/loader receipt is required.
