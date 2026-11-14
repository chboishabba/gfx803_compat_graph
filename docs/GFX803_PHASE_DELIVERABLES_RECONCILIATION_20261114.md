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

### Correction: K2.06 eliminates the MES hypothesis for reference Polaris

The apparent contradiction came from conflating `uni_mes` with
`adev->enable_mes`. Reference v7.3 only sets `enable_mes` for GC11/GC12 and
copies that field into KFD; GFX8 therefore follows the non-MES queue-unmap
path. This aligns with the retained preemption-timeout message. It does not
recover the incident-time errno or establish exact CachyOS source equivalence.
The accompanying TopK source audit identifies `mbtopk` as the large-shape
candidate but not its executed HSACO. See
`receipts/gfx803_k205_t104_source_binary_attribution_20261114.json`.


## 14 November — K2.05/T1 implementation sprint landed

Five standalone Python tools, all within this compatibility repo and
not Schaka's PR #8:

- scripts/gfx803_kfd_incident_offline_audit.py: original journal SHA
  verification, first-error chronology, separated current-vs-historic
  configuration and fail-closed state.
- scripts/gfx803_kfd_trace_boundary.py: default read-only available
  probe/symbol inventory; optional explicit root-bound temporary
  entry/return kprobes, ten-second idle capture and scoped cleanup;
  **never starts a GPU workload**.
- scripts/gfx803_topk_binary_offline_audit.py: original wheel/overlay
  source, ELF and optional code-object SHA, candidate TopK route
  markers and lower-bound [1,151936] vs [32,151936] buffer sizing.
  Static inventory is not proof of selected kernel.
- scripts/gfx803_kfd_binary_branch_audit.py: exact compressed module,
  decompressed module and Build ID comparisons before offline
  objdump call-site and conditional-branch inventory.
- scripts/gfx803_kfd_topk_evidence_join.py: SHA-bound aggregation,
  preserving incident MES/non-MES branch and TopK trigger UNKNOWN,
  K2.05/T1 OPEN and release BLOCKED.

CPU-only synthetics:
tests/test_gfx803_kfd_topk_offline_cut.py. These are **committed,
not yet executed on the RX 580 host**. Run commands and safe stop
rules are in
[the implementation runbook](GFX803_K205_T1_IMPLEMENTATION_RUNBOOK_20261114.md).

**Sprint acceptance:** code and offline tests source-written;
physical/static host run results PENDING. No destructive GPU repro,
new kernel patch, inferred historical MES dispatch, or claim of
debugger attachment. Continue exact old wheel mapping and K2.05
return discrimination only after original receipts are run and
inspected. This adds tooling without changing the existing
K2.04 contradiction or closing K2.05.


## 14 November — offline cut physically executed (`39471ee`)

Host operator reports the K2.05/T1 offline suite **12/12 passed**.
Original previous-boot journal SHA and exact postboot AMDGPU module
SHA/Build ID verified. Disassembly confirms both MES and non-MES
compiled eviction paths. TopK audit is now **scoped to
`libtorch_hip.so`** (recorded SHA-256 prefix `dd0b4030`),
avoiding unrelated NFS reads of `libtorch_cpu.so`.

Original receipts (host-local, **not** assumed uploaded/committed):
`/mnt/truenas/comet-net/experiments/gfx803_k205_t1_static_20261114/`.
Do not claim receipt contents beyond the operator's reported outcomes
without opening those original JSON files.

**Accepted now:** offline code/test execution and binary provenance.
**Still OPEN:** exact incident boot's effective `uni_mes`/
scheduling policy and selected DQM branch; actual eviction
return; initial TopK kernel/HSACO; exact CachyOS source-package match;
post-hang KFD recovery root cause and stable GUI restoration.

**Next decisive route:** (1) search exact incident-time
initramfs/bootloader/module-load/recorded state artifacts using only
read-only operations; (2) statically map cached `libtorch_hip.so`
TopK call graph, embedded HSA GPU code objects, registration symbols
and source revision; (3) if historical state cannot be recovered,
design a **non-display, recoverable-host** trace that records the
selected branch, entry/return, first GPU dispatch and ring/queue
state. Do not equate a successful idle trace with fault reproduction.
No known-wedging TopK run on the sole display GPU.


## 14 November — T1.05 compiled mbtopk offline investigation implemented

The executable maximum cut now targets the exact candidate
`libtorch_hip.so` from the retained `7e0d5dd` attribution
receipt. Tools added:

- `scripts/gfx803_mbtopk_elf_attribution.py`: fail-closed
  original binary SHA and Build ID check, `readelf` TopK
  symbol/section inventory, optional bounded
  `.hip_fatbin` extraction, original source SHA/marker inventory,
  1-row/32-row arithmetic resource bounds.
- `scripts/gfx803_mbtopk_fatbin_scan.py`: ELF64 AMDGPU
  candidate detection with section/program-header extent validation
  and optional bounded extraction. Candidate inclusion **is not**
  incident-time execution or even necessarily a gfx803 target.
- `tests/test_gfx803_mbtopk_offline_attribution.py`: CPU-only
  synthetic SHA-mismatch, ELF parse, embedded candidate and
  source/link-negative tests.
- Extended `scripts/gfx803_kfd_topk_evidence_join.py`:
  evidence-bound K2.06 non-MES reference conclusion,
  T1.04 source candidate, T1.05 verified ELF inclusion,
  explicit T1.06 build link and T1.07 selected dispatch still OPEN.

See [the runnable runbook](GFX803_T105_K206_MBTopK_BINARY_MAXCUT_20261114.md)
for a single CPU-only command sequence. All scripts and tests are
**committed, not yet executed on the TrueNAS host**. Results,
actual HSACO metadata, original build provenance, dispatch and
KFD incident return are pending. No GPU/HIP workload or kernel
patch has been performed.


## 14 November — T1.09–T1.12 / K2.07–K2.08 complete offline implementation

**Source has landed; this new suite has NOT been executed on the
RX580 host yet.** Start with the one-command no-GPU runbook:

[GFX803_T109_K207_FULL_OFFLINE_HANDOFF_20261114.md](GFX803_T109_K207_FULL_OFFLINE_HANDOFF_20261114.md)

New code:

1. gfx803_mbtopk_hsaco_metadata.py — strict unbundled HSACO
   SHA, size, ELF e_machine; readelf/LLVM note/section/symbol
   and kernel metadata extraction.
2. gfx803_amdgpu_msgpack_notes.py — bounded pure-Python ELF PT_NOTE
   AMDGPU MessagePack metadata parser and kernel resource fields.
3. gfx803_mbtopk_retained_source_audit.py — exact original
   TensorTopK.hip SHA gate, source launch/heuristic excerpts and
   explicitly supplied original build-log hints.
4. gfx803_mbtopk_kernel_disasm.py — optional exact metadata-symbol
   bounded llvm-objdump and static instruction classification.
5. gfx803_kfd_nonmes_source_audit.py — targeted source-only
   non-MES fence/preemption diagnostic evidence, with no inferred errno.
6. gfx803_kfd_safehost_trace_plan.py — inert return-probe source
   and six-way dedicated host eligibility checklist. No probes attached.
7. gfx803_t109_k207_final_join.py — SHA-bound source/ELF/fatbin/HSACO
   evidence chain with T1.06/T1.07/K2.05 still OPEN and release blocked.
8. run_gfx803_t109_k207_offline.sh — one-command CPU-only host pipeline.

CPU-only tests cover note parsing, identity refusals, messagepack
bounds, source hashes, kernel symbol validation, safe-host default
denial and evidence-join error rejection. **No test pass count is
claimed for these newly committed tests until the operator runs them.**

### Gating

T1.08 CCOB/gfx803 inclusion ACCEPTED from a45ad49 (33/33 earlier
tests). T1.09/T1.10/T1.11/T1.12 offline metadata/ISA acceptance
PENDING. T1.06 original build-to-benchmark-loader provenance OPEN;
T1.07 selected first stalled kernel/HSACO OPEN. K2.06 source
non-MES fence alignment exists; K2.05 historical internal return
OPEN, K2.07 exact source match/return OPEN. Do not substitute a
future trace for missing historical Nov 14 capture. K2.08 safe
dedicated-host tracing gated and NOT started.

**Do not** run the destructive 32×151936 TopK on the display RX580.
Do not upstream these forensic scripts via Schaka PR #8.


## 14 November — T1.13/14 multi-CCOB member maximum cut

Commit 11223f6 physically ran 61/61 CPU-only contracts and
committed four original T1.09/K2.07 receipts under
docs/receipts/gfx803_t109_k207_host_20261114/.
The SHA-verified gfx803 HSACO was decoded as **336 kernels,
zero readable TopK-name matches**; LLVM's specific metadata
option was unavailable, while the pure-Python AMDGPU MessagePack
decoder succeeded. Original retained TensorTopK.hip SHA
acb592c2… verified (6 source spans, 226 selected lines).
The existing join correctly leaves T1.06/T1.07/K2.05 open.

The next cut is the **219-member offload format**, not another
generic device reset experiment:
- scripts/gfx803_ccob_member_index.py: SHA-verified CCOB v2/v3
  indexing, authoritative member-size boundaries, bounded
  inter-member padding inspection (never search inside compressed
  bytes for CCOB magic).
- scripts/gfx803_ccob_all_members_topk.py: offline per-member
  clang-offload-bundler invocation, SHA and AMDGPU MessagePack
  metadata, each member's readable TopK kernels, checkpointed
  bounded JSON receipts.
- tests/test_gfx803_ccob_member_index.py and
  tests/test_gfx803_ccob_all_members.py: collision, padding,
  bad identity, partial-scan and CPU-only batch tests.
- Runbook:
  [GFX803_T113_T114_CCOB_ALL_MEMBERS_20261114.md](GFX803_T113_T114_CCOB_ALL_MEMBERS_20261114.md).

**New code committed, host acceptance PENDING.** The 61/61
pass count pertains to 11223f6, *not* these new tests.

Even 219/219 fully decoded members would only establish code-object
inclusion and metadata, not original incident-time selected kernel,
benchmark-loaded wheel linkage or KFD's missing internal fence
return. T1.06/T1.07/K2.05/J1/F1/release stay OPEN/BLOCKED
according to original receipts. No new GPU work or KFD patch.

---

## 14 November — GFX8 persistent GPU wedge: authoritative recovery roadmap (R0–R6)

**Authority:** this section is the current *hardware recovery* critical path. Keep historical factory Phase 0/A/B/C/D/E, P0–P3 layer qualifications, and previous Track 1/2/3 intact. This is a recovery-specific dependency chain, **not** a replacement for those systems. Detailed source receipts: [cross-incident RCA](GFX803_CROSS_INCIDENT_QUEUE_RECOVERY_RCA_20261114.md), [C/D source audit](GFX803_CROSS_VERSION_RECOVERY_C_D_AUDIT_20261114.md), [C1b mock and patch audit](GFX803_KFD_C1B_MOCK_AND_START_CPSCH_AUDIT_20261114.md).

### The engineering problem that determines the exit condition

The user's Arch-era experience and March/November RX580 incidents show **kernel and emergency TTY remain available while the GPU stays unusable even after a manual driver reset and Wayland restart**. November's original journal shows: **12:39:28** gfx timeout and failed KFD preemption -> **12:39:29** KIQ ring-test `-110` and KCQ disable failure -> GFX8 soft reset and subsequent **BACO** -> VRAM loss -> further gfx/compute timeouts. At **12:40:55**, a `GPU reset(62) succeeded!` message occurs without demonstrated restoration of graphical function. The first KIQ failure *precedes* that BACO, therefore **BACO exit alone cannot explain the initial hang**. The kernel/TTY remaining alive is not evidence that CP/MEC, KIQ/KCQ, SDMA or GPUVM recovered. A driver-reload and compositor restart are not proof of a physical power cycle.

The **goal is durable GPU execution recovery**, not prettier logs, KFD reopening alone, forced deletion of active DMA resources, or simply preventing an unsafe benchmark. Incident triggers (TopK, WhisperX, Ollama, Wayland) and recovery defects are separate until a physical join proves otherwise.

### Phase and deliverable ledger

| Phase / gate | Position on 14 Nov 2026 | Exact deliverable | Closure / acceptance test |
| --- | --- | --- | --- |
| **R0 — Cross-incident baseline** | **SOURCE/EVIDENCE COMPLETE**, causality OPEN | Immutable March Ollama/Wayland/WhisperX and Nov TopK time-ordered first-fault/recovery matrix; exact source/provenance and known missing first return | Every incident separated into pre-fault, first timeout, attempted soft reset, BACO/PCI, ring retest, post-reset outcome; mark unknown rather than infer |
| **R1 — Hardware reset route** | **OPEN; highest priority** | Source-mapped Polaris10 `gfx_v8_0` soft reset, `vi_asic_reset` BACO and possible PCI fallback, CP/MEC microcode reload, KIQ/KCQ ring init/test, GPUVM/GART, and reset return/error dependency graph; record actual log ordering | Identify earliest failed post-reset ring/command and which reset stage claims success. Differentiate CPU/TTY availability from actual graphics/compute work. No dangerous on-display repro |
| **R2 — Cross-kernel source differences** | **PARTIAL** | Linux v6.13/v6.19/v7.3 and exact 7.3.0-2 source crosswalk, historic Arch kernel provenance, upstream patch accept/NAK ledger, tested source locations | Confirm source-level invariants and changed pathways, review Polaris applicability. GFX8 KIQ quantum exemption already in 7.3 yet KIQ still failed; NAK'd reset-lock reorder must not be deployed |
| **R3 — KFD recovery integrity / containment** | **SOURCE DEFECTS IDENTIFIED; patch DRAFT** | `kgd2kfd_post_reset` error/lock accounting, `amdgpu_amdkfd_post_reset` unchecked result, `start_cpsch` reset-aware `execute_queues_cpsch`, `sched_running` rollback and DRM scheduler start/unwind proof; mocked C/patch test receipt | Propagate failure without false `GPU reset succeeded` *end-to-end* qualification, leaked lock, scheduler double start or premature GPU work; ensure errors during reset-domain write lock are not misclassified. **This does not close R1** |
| **R4 — Actual hardware/firmware recovery correction** | **OPEN / not implemented** | A minimal GFX8-applicable kernel correction targeting the real R1 failure (or a documented fail-closed wedge policy if hardware cannot recover), source patch and kernel build with reviewer-approved resource lifetime | Correct ring/VM/firmware state, not just error reporting. Confirm proper reset/power-domain behavior without release of still-DMA-visible memory |
| **R5 — Physical qualification** | **BLOCKED: independent recoverable hardware not supplied** | Source and module Build IDs/hashes, safe-host manifest and externally persisted trace, bounded matched A/B (original vs corrected), direct post-reset KIQ/KCQ/SDMA/KFD/GFX and new graphics-context check | Same fault-class recovered **without host reboot**: new `/dev/kfd` open, fresh KFD queue makes progress, gfx/KIQ/KCQ ring tests and fresh DRM/Wayland client render; no recurrent timeout/reset loop. If hardware irrecoverable, *only* fail-closed containment can pass its separate safety gate; not a recovery pass |
| **R6 — Release / upstream / rollup** | **BLOCKED on R4/R5** | Reviewed upstream contribution, regression tests, mainline/distro applicability table, reproducible Nix/kernel build, package/source SHA, rollback and accepted long-workload gate | Maintainer acceptance plus repeated physical recovery and clean-client release. Original binary factory Phase B and general stability promotion stay blocked while R5 fails |

### Minimum exact implementation cuts (A/B/C priority)

| Cut | Specific code or measurement target | Priority and rule |
| --- | --- | --- |
| **A1 — Soft-reset/BACO handoff** | `gfx_v8_0_hw_fini`, `gfx_v8_0_cp_resume`, `gfx_v8_0_cp_test_all_rings`, `vi_asic_reset_method`, `vi_asic_reset`, `amdgpu_device_asic_reset` | **Highest-alpha** — source-order and error-propagation crosswalk for first reset wave and repeated BACO waves; no inference from late `-ETIME` to first failed queue |
| **A2 — Ring forward progress** | `gfx_v8_0_kiq_kcq_enable/disable`, KIQ scratch-ring test, per-engine firmware/doorbell/IB, GART/VM rebind and PCI/ASIC reset selection | Determine exact step first unable to complete a fence *after* each reset stage |
| **A3 — Historical joint evidence** | March Arch/kernel build, later CachyOS build, first VM faults, KIQ `-110`, queue preemption and fault record | Separate shared upstream signature from unresolved initiating command or board-specific hardware state |
| **B1 — Return and state** | `start_cpsch`: `execute_queues_cpsch` may return `-EIO` because reset writer owns semaphore; `sched_running` late-error unwind | **Draft RFC only**, must not compile/install on desktop without upstream-quality memory-lifetime/partial node review |
| **B2 — Recovery caller** | `kgd2kfd_post_reset` / `amdgpu_amdkfd_post_reset` / `amdgpu_device_gpu_resume`, DRM scheduler admission | CPU/mocked failed-start contract, retain fail-closed state; propagate status and release reset lock; don't assert kernel hardware fix |
| **B3 — Interrupt and memory** | Polaris `tonga_ih` (not `cik_ih`), KFD interrupt FIFO and restore workers; safe DMA buffer teardown; distinguish MI300X accepted BO-fence patch from GFX8 | Source audit only until concrete stale-event/BO-lifetime evidence |
| **C1 — Controlled comparative reset** | Non-display independently recoverable gfx803 with external logging; exact selected TopK/WhisperX control; firmware clocks and power-mode attribution | Physical probe gated; do not trigger known-hang shapes on the single display RX580 |
| **C2 — Durable acceptance** | New GFX/KIQ/KCQ fence, SDMA, KFD queue dispatch, new DRM acceleration and Wayland rendering without reboot | Hardware recovery proof; **failure to restore ≠ test pass**, even if driver prints success |

### Existing artifacts, PRs and nonclaims

- [#6](https://github.com/chboishabba/gfx803_compat_graph/pull/6) **merged**: incident RCA, benchmark safety, exact-source audit and CPU-only context; no physical hardware fix.
- [#7](https://github.com/chboishabba/gfx803_compat_graph/pull/7) **draft/open**: `patches/linux/gfx803-c1b-cpsch-startup-rfc.patch`, C1b mock, fixture apply tests and reset-aware failure scope. A source-context comparison matched Linux v7.3. **No actual kernel build, patch installation or physical acceptance**. This is the active *one PR* for recovery work; avoid a new branch/PR for each audit.
- [Schaka TopK #8](https://github.com/Schaka/rocm-gfx803/pull/8): independent **trigger mitigation**, not a GFX8 hardware-recovery fix. Previously safe bounded 120-case/20-step receipts do not qualify dangerous large-input/hang behavior or solve reset.
- **Caution:** The attempted pre-reset-before-lock AMD patch was NAK'd. The October accepted BO-lifetime correction concerns MI300X and does not establish a Polaris fix. The already-present GFX8 SDMA callback and quantum exemption are negative controls.
- **No performed physical recovery test** in the current patch series. Do not count source and mock acceptance as R4/R5.

### Next actual max-cut

**Work R1/A1+A2 before promoting R3/B1+B2.** Trace the verified kernel's soft-reset → KIQ/KCQ → BACO/PCI → IP reinit → post-reset ring-test logic and isolate the earliest stage failing to make forward progress. Build a specific *hardware restoration* correction from that, rather than spending another round on reporting, cleanup or benchmark policy. In parallel, keep #7's RFC as a draft and complete safe mock/error semantics. After the hardware path is understood, run bounded physical tests on a recoverable device and promote factory Phase B only with new graphics AND compute functionality.



### R1/A1–A2 source trace landed — 14 Nov 2026

**New evidence:** [GFX803_R1_SOFTRESET_BACO_POSTRESET_VM_RCA_20261114.md](GFX803_R1_SOFTRESET_BACO_POSTRESET_VM_RCA_20261114.md) and the read-only `gfx803_reset_wave_chronology.py` tool/tests.

The first November KIQ `-110` and `KCQ disable failed` occur **before** BACO. `gfx_v8_0_hw_fini` **discards** the KCQ-disable return; GFX8 soft reset can report success despite failed queue quiescence. After BACO, the source's normal IP-resume phase2 includes gfx/KIQ/compute ring tests, and the observed `GPU reset(2) succeeded!` follows the full-reinit path. **Within two seconds**, however, `kwin_wayland` encounters a gfx timeout and **VM fault (vmid 7, pasid 7)**. This is the strongest current post-BACO discriminator: a transient basic ring-test success need not imply durable shader/VM/graphics progress.

**R1 is now SOURCE-TRACED / CAUSAL FAULT UNKNOWN**, not physically closed. The repair priority shifts to comparing the first post-reset *actual graphics GPUVM fault* against the GART/VM page-table, VRAM-loss and compositor-context recreation invariants, as well as verifying that CP/MEC/KIQ registers/firmware genuinely survive into normal workloads. Do not assert the KIQ stayed dead continuously after BACO or that a GPUVM fault proves broken kernel mappings rather than stale userspace state. The original journal cannot distinguish those cases.

**Exact remaining A2 gates:**
- **A2a** trace the GFX8 VM fault source and post-reset page-table/BO repair, including distinguishable newly-created versus pre-reset contexts
- **A2b** produce a source-level instrumentation/diagnostic patch proving which full-reset substep and fresh ring/VM command first fails
- **A2c** test controlled new-graphics/new-KFD execution *only* on independently recoverable hardware
- **R4** correct the causally identified restore mechanism and reproduce recovery without reboot

Existing C1b startup RFC remains **R3 containment**, not hardware recovery. The new offline analyzer tests are committed, not yet validated by CI/TrueNAS.


### 14 November — R1/A2a exact VM generation and fault-code verification

See [GFX803_R1_A2A_VRAM_CONTEXT_GUARDS_AND_FAULT_DECODE_20261114.md](GFX803_R1_A2A_VRAM_CONTEXT_GUARDS_AND_FAULT_DECODE_20261114.md), plus the CPU-only GFX8 fault decoder and tests.

**Priority hierarchy correction:** sustained compute-associated queue/ring nonprogress remains the leading *initiating* investigation (T1), and post-failure hardware reset integrity is R1. The 12:39:32 KWin VMID7 fault is a post-reset discriminator, not sufficient to identify the original TopK/WhisperX hang cause.

**V1 source completed, incident closure OPEN:** v7.3 `amdgpu_vm_generation` includes `vram_lost_counter`; context creation saves the token; `amdgpu_cs.c` rejects stale contexts with `-ECANCELED` and `amdgpu_job.c` also rejects stale jobs at final scheduling. `amdgpu_ctx_query2` reports VRAMLOST, while `amdgpu_vm_validate` and CS VM handling recreate and update BO/page table state. **Do not claim the kernel lacks VRAM-loss gating** or that the incident proves an existing context bypassed it.

**V2 source decode complete, PTE attribution OPEN:** `VM_CONTEXT1_PROTECTION_FAULT_STATUS=0x0E0C4001` includes protection bitfield `0x01`, VMID 7 and a read, with separate `TC3` memory client. `0x01` is not by itself a unique page-not-present diagnosis. Need contemporaneous actual PTE/PDE/BO evidence to choose between invalid mapping, stale context and hardware-side translation failure.

**Proposed module parameter correction:** `vm_fault_stop=1` is documented as *print first*, not a reliable halt-before-cascade. `vm_update_mode=3` performs CPU-side graphics and compute VM updates, a possible controlled comparison but not unique evidence of PT transport cause. Both require safe non-display testing before fault induction.

**External evidence classification:** [RPCS3 #16844](https://github.com/RPCS3/rpcs3/issues/16844) contains authentic 2025 GFX8 KIQ/KCQ/BACO and post-reset compute ring test failure (strong shared recovery-failure signature, not same initiating instruction). [Pop!_OS #4132](https://github.com/pop-os/pop/issues/4132) is **Navi 10**, not Polaris, and is only a generic AMDGPU-compositor failure analogy.

Next cut remains T1 pre-reset stalled workload/queue and R1 post-BACO per-ring actual work, then V1/V2 first-post-reset graphics generation/VM mapping evidence; none warrants a claim of physical kernel repair. New unit tests are committed but await a confirmed run.
