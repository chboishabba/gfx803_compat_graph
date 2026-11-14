# gfx803 direct HIP / ROCr-HSA / KFD qualification — 14 November 2026

## Why this lane exists

The existing March 2026 WhisperX RCA on RX 580 documented a
D2H copy → `Host active wait ... for -1 ns` → H2D copy setup →
another wait → GPU hang / `ring gfx timeout` → BACO / VRAM loss
signature. The later MIOpen original pooling page fault remains
unreproduced across 42 individual and ten shared-process prefix
runs. These are **operational reliability** negative controls,
not missing mathematical API results.

This lane turns that evidence into direct, small HIP/HSA qualification
before broader original vendor suites. Do not claim these 7 small
cases reproduce long WhisperX failures, test HSA SDMA copies directly
or establish the old gfx7/8 KFD doorbell callback's presence.

## R0 — Direct source-owned smoke implemented

- `qualification/native/gfx803_hip_runtime_smoke.hip.cpp`:
  `h2d-d2h` (synchronous), `stream-event-copy` (async copies,
  nonblocking stream and event completion), `kernel-dispatch`
  (HIP launch and stream wait) and `pinned-host-copy` (HIP pinned
  allocation + asynchronous H2D/D2H roundtrip).
- `qualification/native/gfx803_hsa_runtime_smoke.cpp`:
  `agent-enumeration` (HSA init/agent discover), `signal-wait`
  (HSA signal store/wait) and `queue-create-destroy`
  (64-slot GPU multi-producer queue create/destroy, no dispatch).
- `scripts/gfx803_hip_hsa_direct_assay.py`: source checksum,
  original staged MIOpen build provenance, exact Nix compiler
  and ROCm libraries/headers, two binary build receipts, one
  process per case, hard timeout, journal, stdout/stderr hashes
  and fail-closed continuation. A short pass means only that
  the exact call sequence succeeded **this once**.

The native files are small smoke/triage reproducer source. Broad
qualification should **reuse** HIP/ROCr/KFD vendor tests, not
promote this ad hoc test set into the primary compatibility atlas.

## R0a — CPU-only preflight and compile

Use the actual existing successful Schaka MIOpen build receipt,
which owns the exact selected ROCm dev prefix and `hipcc`
configuration. No modification of original sources or Nix store:

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_gfx803_hip_hsa_direct_assay.py' -v

OLD=/mnt/truenas/comet-net/experiments/gfx803_schaka_miopen_20261113
OUT=/mnt/truenas/comet-net/experiments/gfx803_hip_hsa_direct_20261114

python3 scripts/gfx803_hip_hsa_direct_assay.py \
  --miopen-build-receipt "$OLD/build.json" \
  --out "$OUT" --build --build-timeout 900
```

If `libhsa-runtime64.so`, `libamdhip64.so`, `hsa/hsa.h`
or `hip/hip_runtime.h` is absent, **stop** and use the matched
development closure (do not silently compile against `/opt/rocm`).
If a compile fails, read `$OUT/hip.build.stderr` or
`$OUT/hsa.build.stderr` and preserve this first failed attempt.
No physical GPU pass is claimed here.

## R0b — Execute on a verified healthy and idle GPU

Only after any previous VM fault or reset has been independently
cleared, with C2/TopK/MIOpen/WhisperX not sharing the device:

```bash
python3 scripts/gfx803_hip_hsa_direct_assay.py \
  --miopen-build-receipt "$OLD/build.json" \
  --out "$OUT" --resume --execute --batch-size 2 --timeout 60
```

Repeat the same command after inspecting each result in
`$OUT/matrix.json`. A non-passing outcome halts immediately.
The process never resets the GPU, retries a faulting test or
promotes hardware/release compatibility.

The intended execution order is HIP H2D/D2H, stream/event,
kernel, pinned host copy, then HSA agent/signal/queue. The
HSA queue case is **create/destroy only**; it is not a kernel
dispatch or SDMA doorbell reset test. Kernel journal access
is advisory; unavailable log access never means fault-free.

## R1 — Original upstream HIP, ROCr and KFD tests

TheRock and component-local upstream tests are the primary test
owners. Reuse
`scripts/gfx803_rocm_ctest_qualification.py` to collect and
run an **actual configured upstream CTest tree** for each:

| Layer | Upstream family | Acceptance focus |
| --- | --- | --- |
| `hip-runtime` | Original HIP tests / `--hip-tests --tests` | Allocation, pinned/mapped memory, H2D/D2H, streams, events, sync, IPC, graphs, negative error contracts |
| `rocr-hsa-kfd` | `rocrtst` / `--rocrtst --tests` | Signals, queues, memory pools, async copies and agent/dispatch behavior |
| `rocr-hsa-kfd` | KFDTest / `--kfdtest --tests` | KFD queues, memory mapping, SDMA, doorbells and reset-adjacent fault behavior |

The existing ten-layer catalogue combines ROCr and KFD under one
layer, but the physical test suites must have **distinct immutable
CTest receipts**, and their result join must retain distinct source,
build path, selected binaries and coverage. Do NOT overwrite one
`rocr-hsa-kfd` receipt with another under the same output.
The current aggregator accepts only one CTest receipt per layer;
that fan-in is a **genuine implementation gap** until added.

Required original CTest provenance:
- Exact source SHA, unchanged source, matching CMake home and
  configured `CTestTestfile.cmake`;
- immutable selected Nix ROCm store and immutable CTest binary;
- discovery lists all original source-owned test names;
- each test separately executed with timeout, raw logs and SHA-256;
- record absent/unbuilt targets explicitly, not `passed`;
- isolate queue/reset/destructive cases from the non-destructive
  smoke. Do not run destructive KFD kernel reset tests on the
  display-attached card without a proven recovery plan.

## R2 — Cross-workload reliability and claim admission

Compare direct HIP/HSA/KFD results to the preserved
`docs/INCIDENT_2026-03-30_WHISPERX_ALIGN_GPU_HANG_AND_ROCPROFV3_SUCCESS.md`
and `docs/RETAINED_RCA_SET.md`:

- Original WhisperX input/model/profile on **same exact**
  runtime/kernel and driver, compared with profiler-off and
  profiler-on only when safe;
- copy completion and queue forward progress, independent
  kernel journal and device-reset evidence;
- state-stress tests such as repeated allocations, multiple
  concurrent streams, transfer contention, VRAM pressure, KFD
  signal/queue lifetime and GPU-compute/memory interleaving;
- independent historical SDMA callback and GFX7/8 queue
  validation *running-kernel source/binary* provenance.

A passing 7-case direct smoke does **not** establish sustained
WhisperX stability or a general ROCm runtime release. Exact
acceptance requires scoped representative mixed-traffic and
long-duration safety evidence.

## Exact unresolved integration gates

- **R0:** matched native smoke compilation and hardware receipts;
- **R1:** actual available upstream CTest build trees plus
  executable HIP/ROCr/KFD test universes;
- **R1a:** multi-suite receipt fan-in under a shared layer,
  preserving `rocrtst` and `kfdtest` as different sources;
- **R2:** queue/SDMA/reset coverage and controlled stress/recovery,
  tied to the March WhisperX failure class;
- **P1:** original MIOpen pool exact binary A/B and activation OOM
  classification, GroupNorm expected negative controls;
- **B/C:** complete-source, full-loader Nix/Cachix release and
  clean-client installation.

Source owner: `chboishabba/gfx803_compat_graph`.
Original component tests and patches remain owned by
Schaka/ROCm/TheRock. This is a developer-ready, *not yet executed*
test cut and does not modify the Schaka TopK patch scope.
