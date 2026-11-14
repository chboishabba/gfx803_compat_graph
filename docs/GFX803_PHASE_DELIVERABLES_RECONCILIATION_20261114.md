# gfx803 / RX 580 — qualification, reliability and release phase reconciliation

**Snapshot:** 14 November 2026. **Claim level:** candidate hardware evidence,
not universal HIP/ROCm compatibility or accepted release. Maintains the older
factory phases 0/A/B/C/D/E, the ten compatibility layers P0–P3, and the
pre-existing RCA_TRACK_1/2/3 rather than renaming or replacing them.

## 1. Three independent acceptance axes

| Axis | Scope | Passing evidence means | Does not imply |
| --- | --- | --- | --- |
| **Capability / semantic conformance** | Selected HIP/runtime/library/compiler API, dtype, shape, kernel and CPU reference | Exact function ran and met that assay's numerical contract | Long-run queue/recovery safety, all signatures or full API support |
| **Operational reliability** | Repeated operation, queue/ring progress, SDMA/D2H/H2D, pinned host pages, memory pressure, cache, concurrent tenants, device resets | Workload survives the specified *duration and environment* without faults, hangs, reset or numeric drift | Other API families work or kernel bug ownership is proven |
| **Reproducible delivery** | Source tree, compiler/ABI, runtime closure, pristine build, clean client, Cachix and rollback | Exact runtime and artifact can be independently restored with admission evidence | All hardware/card generations or all workloads are reliable |

A scoped release can qualify a subset, but may never claim **stable general
compute** if representative sustained-workload and KFD/ROCr queue gates are
open. A failed long WhisperX lane must not retroactively erase a correctly
qualified short GEMM test.

## 2. Binary-factory phases (from NIX_GFX803_BINARY_FACTORY_ROADMAP.md)

| Factory phase | 14 Nov reconciliation | Deliverable required to close |
| --- | --- | --- |
| **0 controls** | Preserved historical 5.7/6.4 numerical, load and reset controls; separate from 10.1 candidates | Immutable original receipts and explicit scope |
| **A pinned import/bootstrap** | Partially physically realized: staged Nix ROCm 10.1 closure, usable compiler/MIOpen library path and GPU runs; original document's *source-written only* status is obsolete. Exact immutable upstream image digest/source label and all-source-component verification still must be inspected independently | Audited source/build/import provenance, ELF/loader/ABI closure lock; don't infer full OCI lineage from Nix store paths |
| **B first accepted binary** | Candidate functional receipts exist, **not** an accepted clean-client release | Exact binaries rebuilt/assembled from admitted source, numeric and stability receipts, manifest, Cachix publish + clean-client substitute |
| **C native modular builds** | Matched selected hipcc/MIOpen C++ probes built; **not evidence that entire ROCm is natively built via modular Nix derivations** | Clean Nix source builds for HIP/ROCr, compiler, rocBLAS, MIOpen, solver/sparse/FFT/RAND/PRIM, frameworks + dependent closure |
| **D upgrade automation** | Versioned factories/checkers exist; accepted candidate→stable upgrade/rollback has not been demonstrated | Component DAG incremental rebuild, independent physical gate, rollback and clean-client comparison |
| **E upstream contributions** | Schaka PR #8 TopK repair/qualification handoff on fork; shared source attribution; independent of factory release | Maintainer review and source-specific upstream test/performance evidence |

Do not claim Phase B simply because a composition can execute an
on-device workload. The original binary-factory roadmap has stronger
Cachix/clean-client and source/digest admission gates.

## 3. Ten compatibility qualification layers: measured vs planned

| Layer | Recorded qualifying observation | Still open |
| --- | --- | --- |
| **PyTorch OpInfo** | 1,774 original generated tests: 1,583 pass; 183 original skip/nonpass; 3 ordinary fails; 4 complex64 GPU fault candidates; 1 interruption. First 16 body replays: 14 upstream skips, 2 expected failures. | Finish 167 skip replays, all real failures/faults, wider dtype/grad/shape and backend coverage |
| **rocBLAS / hipBLAS** | Schaka 27/27 source-verified FP16 GEMM/batched-GEMM/convolution suite; native forward/backward/C2 tests exist | Full BLAS L1/L2/L3, dtype/algorithm/shape and native hardware CTest matrices |
| **MIOpen** | 23 original entries: 18 pass, 2 zero-applicable solver lists, 1 pool VM fault, 1 activation OOM, 1 groupnorm expected-rejection classification issue. Pool isolated 42/42 pass; ten shared-process prefix runs including 42 pass. | Original-binary A/B fault investigation; activation OOM; groupnorm negative-control weld; full solver/backward/MHA coverage; runtime load mapping |
| **rocSOLVER / rocSPARSE** | Shared objects inventoried; reusable CTest entrypoints identified | Actual source-owned test build and GPU receipts |
| **rocFFT / rocRAND / rocPRIM** | Libraries / ELF exports where present; upstream test reuse plan | FFT/RNG/PRIM/CUB/Thrust direct GPU and header/template test matrix |
| **HIP runtime** | Real allocations, copies, kernels and synchronization exercised transitively via PyTorch/MIOpen; library present | Direct HIP memory/streams/events/graphs, pinned/H2D/D2H, SDMA and stress tests |
| **ROCr / HSA / KFD** | Prior first-party runtime boundary and WhisperX/Ollama reset RCA; native 10.1 baseline dispatch | Direct ROCRTST/KFDTest, queue/VM/signal/doorbell/SDMA and recovery assay; host kernel patch/build provenance |
| **LLVM / HIP compiler** | Actual hipcc compiled MIOpen sources; selected compiler/shim tests | Full ISA, wave64, barriers, atomics, negative-controls, compiler flags |
| **Triton** | Schaka four-dot dtype canary executed: BF16 4.77e-7, FP16 9.02e-7, FP32 1.57e-6, INT8 0 error | Independent numeric tolerance, dot/reduction/layout/backward/dtype matrix |
| **Composed workloads** | Bounded C2/LILA 20-step AdamW/forward/backward; historical WhisperX/ComfyUI/Ollama incident evidence | Long-session/real input replay, checkpoint/reload, concurrent-client/memory pressure, kernel resilience, full training admission |

Source-bound direct hardware receipts described by user:
`/mnt/truenas/comet-net/experiments/gfx803_schaka_fp16_20261113/matrix.json`,
`gfx803_schaka_triton_20261113/matrix.json`,
`gfx803_schaka_miopen_20261113/matrix.json`,
`gfx803_pool_isolation_20261113_v3/matrix.json` and
`gfx803_pool_prefix_20261113/matrix.json`.
The first isolated receipt was inspected directly (42 `pass`, no faults,
with overall status `batch-checkpointed`). The rest of this row
is operator-reported hardware evidence, not independently rerun here.

### Measurement ≠ API enumeration

The `gfx803_rocm_abi_20261113_v2` receipt inventories ten expected
shared-library *families*. It is availability evidence, not ten
distinct public API signatures and not ten qualified component suites.
`qualification/rocm_layers_v1.json` is a reuse-first catalogue,
not the authoritative current physical test verdict.

## 4. Where WhisperX, KFD, doorbells and pooling belong

The existing repository already has **RCA_TRACK_1 = runtime/ABI**,
**RCA_TRACK_2 = numerical/workload correctness**, and
**RCA_TRACK_3 = load/stability**:

| RCA evidence or subsystem | Qualification lane | Acceptance gate / deliverable |
| --- | --- | --- |
| `rocminfo` latest-HSA `hsa_init()=4096` | **Track 1 / P0 runtime ABI** | Source-matched ROCR/CLR/HIP symbols + agent enumeration under selected closure; not GPU hang |
| GFX7/8 KFD SDMA `hqd_sdma_get_doorbell` 2025 fix and queue validation | **Track 1 + Track 3 / kernel/runtime driver** | Running-kernel source→binary provenance and direct KFD queues/SDMA reset tests; old patch existence ≠ current active kernel admission |
| WhisperX March 2026 D2H→host wait→H2D→host wait, `ring gfx timeout` → BACO/VRAM loss | **Track 3 / composed-workload & HIP/HSA reliability** | Stable same-runtime long-file execution, queue forward-progress counters, copy/host-pinned-memory and fault-free reset evidence; profiler on/off is a confounder control |
| Ollama/Wayland KFD resets and Leech/ComfyUI drift | **Tracks 2–3 / cross-workload negative controls** | Bounded numerical comparisons and sustained GPU stability with original source and workloads |
| MIOpen 42/42 individual and 10/10 prefix pass, historical original pool GPU page fault | **P1 MIOpen function + Track 3 runtime reliability** | Original binary controlled A/B + loader/queue/kernel journal matched to prior incident, or classify nonreproduced |
| MIOpen activation OOM | **Track 3 memory-pressure / MIOpen** | Original input and allocation/VRAM pressure diagnostics; distinguish ordinary OOM, allocator fragmentation and VM fault |
| MIOpen groupnorm expected invalid shape rejection | **P1 semantics negative control** | Exact expected invalid shapes/status documented, outcome accepted *as rejected*, not as successful normalized output |

**Key placement:** WhisperX is a *first-party stability integration
assay* and a generator of test cases for **direct HIP-runtime,
ROCr/HSA/KFD component conformance** (D2H/H2D, signals, completion,
pinned pages, queue fault/recovery). A passing WhisperX run is not
an enumeration of HIP functions, nor a substitute for original
rocrtst/KFDTest tests. Those direct tests and WhisperX together
form a stronger multi-layer assurance argument.

The current Schaka 10.1 MIOpen pooling incident is **not demonstrated
to be the same defect** as the old WhisperX ring timeout or the
June 2025 SDMA doorbell callback regression. Use independent
failure taxonomy, host driver/build and exact log correlation.

Canonical preexisting sources (already in repository):
`docs/RETAINED_RCA_SET.md`,
`docs/FAILURE_CASE_INDEX.md`,
`docs/ADMISSIBILITY_CONE_TREE.md`,
`docs/INCIDENT_2026-03-27_WHISPERX_TRANSCRIBE_RESET.md`,
`docs/INCIDENT_2026-03-30_WHISPERX_ALIGN_GPU_HANG_AND_ROCPROFV3_SUCCESS.md`,
`scripts/run-whisperx-rca-matrix.sh`,
`scripts/trace-whisperx-rocprof.sh`,
`POLARIS_STABILITY_BLUEPRINT.md`.
New original-binary and driver audit controls:
`scripts/gfx803_pool_original_runtime_matrix.py`,
`scripts/gfx803_kfd_doorbell_audit.py`,
`scripts/gfx803_pool_forward_only_control.py`.

## 5. Highest-information next cuts and concrete deliverables

| Priority | Implement/execute | Artifact | Exit rule |
| --- | --- | --- | --- |
| **R1 — original pooling failure** | Run original `pool_sweep` binary and controlled HIP/HSA environment arms on an idle RX 580, with kernel journal + loader provenance, one arm per healthy process | Original-binary A/B matrix + kernel logs | Either reproducible distinct failure signature with causal target, or bounded `not reproduced`; **never mark historical fault repaired without evidence** |
| **R2 — direct HIP/HSA reliability** | Reuse source-matched HIP memory/copy/stream/event/graph tests, ROCRTST + KFDTest; include pinned-host D2H/H2D, SDMA enabled/disabled and queue reset negative controls | GPU-qualified direct runtime receipt | Runtime, kernel, toolchain, device and fault-free queue/signal evidence; isolate any destructive tests |
| **R3 — WhisperX stability regression** | Reuse existing script/harness with same long audio/model/checkpoint; run no-profiler baseline then blocked/serialized and DMA-light controls only if GPU recovered | Exact original WhisperX transcript/status + queue/journal/profiler evidence | Sustained, repeated completion without ring timeout/VM fault/reset/VRAM loss, not just launch or summary-only process exit |
| **P1 — MIOpen semantics** | Pool original baseline, groupnorm expected-fail acceptance and activation OOM diagnosis | Amended per-case status **without changing original source receipt** | Every suite entry exactly categorized as pass/negative-control/inapplicable/fault/OOM |
| **P2 — backend breadth** | Restore source-compatible TheRock or component-local upstream tests for BLAS/SOLVER/SPARSE/FFT/RAND/PRIM/Triton and OpInfo 167 replays | Versioned per-component test atlas | Original test universe, built/available flags, all measured outcomes and uncovered public API surface |
| **B/C — release** | Review TopK PR #8 large-input benchmark, complete hardware admission, whole Nix closure and clean-client Cachix restore | Accepted closure + manifest and rollback receipt | Hardware, numeric, queue stability and packaging all independently admitted |

**Not the next cut:** rerun the March 2026 crashing WhisperX file
unnecessarily, patch pooling workgroup tile math without a reproduced
source cause, or declare full ROCm support based on PyTorch OpInfo.

## 6. Roadmap governance / source of truth

- This file: **dated synthesis** of observed phase/deliverable state.
- `docs/NIX_GFX803_BINARY_FACTORY_ROADMAP.md`: **factory exit criteria**;
  earlier status lines are historical snapshots, not current acceptance.
- `docs/GFX803_ROCM_WHOLE_STACK_QUALIFICATION_20261112.md`:
  **test implementation/runbook** and upstream sources.
- `qualification/rocm_layers_v1.json`: **ten-layer scope catalogue**;
  not an automatically refreshed measurement registry.
- `docs/RETAINED_RCA_SET.md` and `docs/FAILURE_CASE_INDEX.md`:
  **historical crash case preservation**.
- `scripts/gfx803_rocm_coverage_report.py`: **source-bound evidence
  aggregator**, never universal acceptance.
- `scripts/gfx803_release.py` + `scripts/publish-gfx803-accepted.sh`:
  **release gates**; do not bypass for a successful isolated assay.

This document is a reconciliation of code, docs and reported receipts,
**not** a new GPU execution result or automatic release promotion.


## 14 November execution sprint — direct HIP/ROCr/HSA/KFD (phase R0/R1)

**Highest-information priority confirmed:** direct runtime/driver
conformance **in parallel with** original-binary pooling A/B.
The historical WhisperX incident is the pre-existing load/stability
negative control, not a new standalone release phase or an excuse
to run destructive workloads prematurely.

| Gate | New source deliverable | Current disposition | Physical exit |
| --- | --- | --- | --- |
| **R0.01 native HIP** | `qualification/native/gfx803_hip_runtime_smoke.hip.cpp`; 4 direct H2D/D2H, stream/event, kernel and pinned-host cases | Implemented, physical run pending | Original Nix hipcc build, four independently process-isolated passes, no relevant GPU fault/reset in observable logs |
| **R0.02 native ROCR/HSA** | `qualification/native/gfx803_hsa_runtime_smoke.cpp`; agent init, signal store/wait, GPU queue create/destroy | Implemented, physical run pending | Original matched HSA headers/libs, three process-isolated passes; no claim of queue dispatch/doorbell recovery |
| **R0.03 exact receipts** | `scripts/gfx803_hip_hsa_direct_assay.py` and offline contracts | Source-written | Source/compiler/runtime/binary SHA; exact tested marker and host journal visibility; faults stop further runs |
| **R1.01 original HIP tests** | Existing `scripts/gfx803_rocm_ctest_qualification.py` and `--hip-tests --tests` acquisition path | Test adapter implemented; vendor test binaries unavailable/unmeasured | Fully enumerated original HIP upstream suite and direct real-hardware receipts |
| **R1.02 original ROCRTST** | Existing upstream CTest adapter | Upstream build/test inventory open | Original ROCr signal/queue/agent/memory-pool/direct-copy test suite on selected closure |
| **R1.03 original KFDTest** | Existing upstream CTest adapter | Upstream build/test inventory open | Original KFD/SDMA/doorbell/queue test suite, destructive tests safely segregated |
| **R1.04 distinct suite fan-in** | `scripts/gfx803_rocm_coverage_report.py` now permits multiple original CTest receipts in `rocr-hsa-kfd` and limited seven-case native smoke results | Source-written; regression tests committed | Preserve separate original ROCRTST and KFDTest physical provenance; no false API-level promotion |
| **R2.01 mixed copy/queue stress** | Existing WhisperX `trace-whisperx-rocprof.sh` and `run-whisperx-rca-matrix.sh` + KFD journal/fault taxonomy | Historical failure evidence retained; 10.1 same-runtime stability not admitted | Sustained D2H/H2D, queue progress, host-pinned-memory and memory-pressure stress without ring timeout/VM fault/BACO reset |
| **P1.04 original MIOpen pool A/B** | `scripts/gfx803_pool_original_runtime_matrix.py`, `gfx803_pool_forward_only_control.py`, KFD audit | 42/42 isolated and 10/10 prefix passes; **original pool fault cause open** | Exact original 42-case binary/loader and journal A/B; either reproduce and attribute or record bounded non-reproduction |
| **B/C release cross-gate** | `gfx803_release.py`, Cachix factory, clean-client acceptance | OPEN | Stable scoped HIP/HSA and math-workload conformance, complete source-verified binary closure, clean-client restore |

**Source locations and runnable commands:**
`docs/GFX803_HIP_HSA_KFD_DIRECT_QUALIFICATION_20261114.md`.

The seven native smoke cases are a small deliberate bridge from
the historical WhisperX load-time signature to the original
vendor component suites. No case tests a KFD callback fix
by itself. The Schaka TopK PR's source review, reviewed-wheel
benchmark and patch scope remain independent.

**Schaka PR communication:** PR #8 branch
`chboishabba/rocm-gfx803:fix/gfx803-topk-sort-fallback` contains
the updated qualification handoff (14 November). Direct PR
conversation comment was blocked by GitHub integration 403.
This does not mean the upstream maintainer has acknowledged
the expanded programme.


## 14 November blocker: TopK long-row hang and failed KFD reset

A **new hardware incident** supersedes any simple claim that the
cached pre-review patched TopK wheel is stable: the `[32,151936]`
float32 k=50 benchmark hung, AMDGPU reported compute/GFX ring
timeouts/device coredump, KFD queue quiesce/restore/resume failed,
and the sole display GPU remained wedged until reboot.
The original unpatched safe cases passed; three known crashing
unpatched cases were skipped. The smaller patched `[1,151936]`
k=50 case passed. Neither is a successful paired review benchmark.

This opens **two separate mandatory repair gates**:
(T1) trace first nonprogressing TopK GPU dispatch and safely
benchmark correct `mbtopk` vs full sort, and (T2) trace first
failing KFD reset queue/doorbell return with matching kernel source
and symbols. The 2025 gfx7/8 SDMA callback patch does not prove
T2 is already corrected. An additional broad HIP/HSA smoke success
cannot override a demonstrated kernel/queue reset or compositor failure.

Read-only event capture, debugger use (GDB/ROCgdb/Ghidra), source
provenance and T1/T2 exit criteria are in
`docs/GFX803_TOPK_KFD_RESET_FORENSICS_20261114.md`.
**No intentional reproduction of the wedging case on the sole
display GPU** before isolation/recovery support.


## 14 November — parallel operator handoff (current planning cut)

The immediate owner split is now tracked in
[TopK/KFD parallel workboard](GFX803_TOPK_KFD_PARALLEL_WORKBOARD_20261114.md).

**Host/operator, in parallel:** K1.01–K1.03 recover exact incident-boot
CachyOS module/source/debug-symbol provenance and audit gfx7/8 SDMA
doorbell/queue-validation implementation. K2.01–K2.02 map the **first**
KIQ `-110`/KCQ disable/reset/KFD quiesce/restore/resume errors to
matching source and observed return propagation. This is not
equivalent to proving the callback was invoked.

**Compatibility/source lane, in parallel:** T1.01–T1.02 statically
attribute cached pre-review TopK `[32,151936]` dispatch and code
object/resource requirements, prepare the original incident ↔
first-recovery-error J1 evidence join and future source-level
regression gates. T1.03 dynamic fault reproduction is **blocked
on a demonstrably recoverable non-display test host**.

**Concrete next handoff:** `kernel_source_handoff.json` using the
workboard's schema, with exact source SHA/build IDs and source
callsite/return evidence. Unknown claims remain null. The
incident-boot module must not be silently replaced with the
post-reboot module merely because their `uname -r` matches.

**Acceptance:** original journal and CSVs remain unchanged; first
faulting GPU dispatch (T1) and first failing KFD recovery operation
(T2) are separate, grounded claims. The driver/doorbell fix, TopK
patch, benchmark and release remain OPEN until those respective
gates have actual evidence. No new GPU run is claimed here.


## 14 November — verified K1/K2 handoff advancement

The operator committed `07a52c7` with the kernel/module identity,
Polaris gfx8 callback/module-symbol evidence, first retained KWin GFX
timeout, first logged KFD quiesce failure, and subsequent restoration,
KIQ `-110` and KCQ disable events. The reference source is upstream
v7.3, **not** a proven exact CachyOS patchset; matching DWARF is
unavailable. No new GPU run occurred.

**K1.01 module fingerprints: DONE (recorded); K1.03 callback present:
DONE for module symbol/reference registration. K1.02 exact DWARF and
CachyOS source-package match: OPEN. K2.01 first logged recovery error:
DONE. K2.03 first failing internal function/branch: OPEN. T1 original
TopK GPU dispatch: OPEN.** The old missing gfx8 doorbell callback
is not a justified patch target based on this evidence, and whether
it executed during the incident is unknown.

Authoritative exact identifiers, correction of unknown callback
invocation and next callsite-level cut:
[parallel workboard](GFX803_TOPK_KFD_PARALLEL_WORKBOARD_20261114.md).


## K2.03 advancement — first KFD quiescence error path

Commit `43e70ef` maps the upstream v7.3 reporting branch:
`amdgpu_amdkfd_gpuvm.c:2535` →
`kgd2kfd_quiesce_mm()` → `kfd_process_evict_queues()` →
`dqm->ops.evict_process_queues()` → nonzero return
(other than the source's `-EIO` exclusion) →
`Failed to quiesce KFD`.

**K2.03 source path CLOSED; K2.04 DQM dispatch and error branch
OPEN; K2.05 incident-time error return OPEN.** Source-package
exact matching, callback invocation and T1 TopK first kernel remain
open. Subsequent KIQ/KCQ events are downstream in the recorded
journal timeline, not automatically the quiescence return.

Deliverable/acceptance and no-destructive-rerun constraints:
[parallel workboard](GFX803_TOPK_KFD_PARALLEL_WORKBOARD_20261114.md).


## K2.04 conditional MES queue-removal hypothesis (14 November)

Commit `635b40c` recorded post-reboot Polaris
`gfx_target_version=80003`, `sched_policy=0`, `uni_mes=1`
and mapped the reference-source MES branch to
`evict_process_queues_cpsch` → `remove_queue_mes` →
`adev->mes.funcs->remove_hw_queue`; failed MES removal may
escalate to `reset_queues_mes` and `kfd_hws_hang`.

**K2.04 dispatch mapping: CONDITIONAL; K2.05 incident-time return and first
failing hardware/firmware operation: OPEN.** The same reference source emits
the retained unsuccessful-preemption diagnostic only from its non-MES branch.
Resolve incident-time MES state/source divergence before treating a MES return
as causal. The later KIQ `-110` and KCQ disable observations are not either
missing return. Callback invocation, exact CachyOS source match and TopK first
kernel remain OPEN. No GPU execution or kernel patch occurred.

Next target: resolve the MES/non-MES contradiction from exact artifacts or a
safe-host trace, then constrain the applicable return on safely recoverable
hardware only. For exact gates see
[parallel workboard](GFX803_TOPK_KFD_PARALLEL_WORKBOARD_20261114.md).
