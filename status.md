# gfx803 status — 14 November 2026

- **Overall:** reproducible Schaka ROCm 10.1 gfx803 candidate with measured
  native RX 580 functional GPU execution; **not accepted/released**.
- **Factory:** Phase A partially physically staged; Phase B accepted
  clean-client Cachix closure OPEN; Phase C full native Nix component
  build DAG OPEN; D lifecycle OPEN; E upstream contributions parallel.
- **Qualification:** ten-layer catalogue and evidence join exist.
  Original PyTorch OpInfo 1,583/1,774 passes with original skips,
  failures and fault candidates retained. Schaka FP16 suite 27/27
  passed; Triton four dtypes executed (numeric acceptance still
  separate); original direct MIOpen 23 entries: 18 pass, two
  inapplicable, historical pooling fault, activation OOM, groupnorm
  expected-boundary rejections conservatively classified failed.
- **Pooling:** individual 42/42 and shared-process prefixes 10/10 pass;
  historical original-binary VM fault remains unreproduced/cause open.
- **Reliability:** existing March 2026 WhisperX D2H/copy-wait
  → `ring gfx timeout` → reset/VRAM-loss investigation is a
  *cross-workload stability/queue assay* in RCA_TRACK_3, plus
  direct HIP/ROCr/HSA/KFD component qualification targets. Historic
  gfx7/8 KFD doorbell callback regression has independent
  kernel-build provenance gate. Do not conflate with MIOpen VM fault.
- **TopK:** source fix, 120-case focused semantic result and upstream
  PR #8 evidence exist; reviewed-wheel rebuild/paired large-input
  performance and upstream acceptance remain OPEN.
- **Next cuts:** original pooled binary A/B plus loader/KFD journals;
  direct HIP/ROCr/KFD tests; activation OOM and groupnorm negative
  controls; remaining OpInfo replay; scoped stability/release
  admission. No automatic promotion.

Full phase/deliverables reconciliation:
`docs/GFX803_PHASE_DELIVERABLES_RECONCILIATION_20261114.md`.

This is a dated evidence snapshot. Retained source-specific receipts
and original test logs take precedence over status prose.

- **14 Nov new critical regression:** pre-review patched TopK float32
  `[32,151936]`, k=50 hung GPU; KFD queue restore/resume then
  failed and the single display GPU wedged Plasma Wayland. Reboot
  required; stop running that cached wheel on this shape.
  Incident debugger max-cut:
  `docs/GFX803_TOPK_KFD_RESET_FORENSICS_20261114.md`.


## Active parallel source investigation — 14 November

- **K1/K2 operator:** matching incident-boot CachyOS GFX8
  amdgpu/KFD module, symbols, callback/queue source, then first
  KIQ `-110`, KCQ disable and KFD quiesce/restore/resume error.
  OPEN; no presumed successful source/binary match.
- **T1 integration:** old cached-wheel TopK dispatch, HSACO,
  shape/grid/resource and first-failure attribution. OPEN.
- **J1 evidence join:** compare independent T1/T2 call traces
  against immutable raw incident journal/CSV; OPEN.
- **Safety:** no known-wedging TopK rerun on the only
  display GPU; no release promotion from partial reset success.
- **Handoff and phases:**
  `docs/GFX803_TOPK_KFD_PARALLEL_WORKBOARD_20261114.md`.


## K1/K2 handoff received — 14 November (`07a52c7`)

- Kernel/module SHA + Build ID recorded; gfx8 SDMA doorbell callback
  found in running module, registered in upstream v7.3 reference for
  Polaris. First retained KFD failure is `Failed to quiesce KFD`;
  subsequent queue restore/resume, KIQ `-110`, KCQ errors retained.
- Exact CachyOS source package / DWARF **OPEN**; callback invocation
  during incident **UNKNOWN**; exact first internal KFD failing branch
  **OPEN**, as is original TopK kernel attribution. No GPU rerun.
- Handoff: `docs/receipts/gfx803_kfd_kernel_source_handoff_20261114.json`.
  Next cut: `docs/GFX803_TOPK_KFD_PARALLEL_WORKBOARD_20261114.md`.


## K2.03 source branch mapped — `43e70ef`

- Upstream-reference `amdgpu_amdkfd_gpuvm.c:2535` →
  `kgd2kfd_quiesce_mm` → `kfd_process_evict_queues` →
  `dqm->ops.evict_process_queues` → qualifying nonzero return
  → first logged `Failed to quiesce KFD`. Static call mapping
  complete; **incident-time return value OPEN**.
- **K2.04:** select real Polaris DQM eviction function and enumerate
  source-level failure/error returns. **K2.05:** dynamically confirm
  actual first failed operation if evidence becomes available.
- Later KIQ `-110`/KCQ errors must not be mislabelled the
  quiescence return. Exact CachyOS source match and first TopK
  kernel still OPEN. No GPU rerun or kernel patch.


## K2.04 mapped — `635b40c`

- Post-reboot Polaris `80003` with `sched_policy=0`, `uni_mes=1`
  selects `evict_process_queues_cpsch` → `remove_queue_mes` →
  `adev->mes.funcs->remove_hw_queue` in the v7.3 reference source. Its
  failure escalation can reach `reset_queues_mes` and `kfd_hws_hang`.
- **K2.04 is conditional, not incident-selected:** the retained
  unsuccessful-preemption diagnostic is emitted only by the non-MES branch in
  that reference source. Resolve incident-time MES state/source divergence
  before treating `remove_hw_queue` as causal. No callback invocation or
  incident return value was observed.
- No GPU rerun or speculative patch. TopK kernel T1,
  exact CachyOS source package, and KFD causal join J1 OPEN.


## K2.05/T1 offline tooling — 14 November

- Five implemented source tools (incident SHA/event audit, tracefs
  inventory/explicit scoped tracing, original TopK wheel resource
  inventory, exact hashed module disassembly, evidence join) and
  focused CPU-only tests are committed. **Host execution pending**.
- Runbook: docs/GFX803_K205_T1_IMPLEMENTATION_RUNBOOK_20261114.md.
- K2.04 MES/non-MES contradiction remains; K2.05 actual incident
  branch/return OPEN, T1 actual TopK GPU kernel OPEN, release BLOCKED.
- No GPU jobs or new kernel patch were performed by this sprint.


## Offline evidence acceptance — `39471ee`

- Operator executed K2.05/T1 offline suite **12/12 PASS**;
  incident SHA and exact postboot AMDGPU module SHA/Build ID verified.
- Both MES and non-MES eviction branches compiled; actual incident
  branch and return unknown. Original TopK `libtorch_hip.so`
  SHA prefix `dd0b4030` recorded; **selected HSACO unknown**.
- Host receipts: `/mnt/truenas/comet-net/experiments/gfx803_k205_t1_static_20261114/`
  (not presumed uploaded). No GPU/HIP execution.

## K2.06/T1.04 source-and-binary attribution — 14 November

- **Correction:** `uni_mes=1` does not by itself select the KFD MES path on
  Polaris. In the v7.3 reference, KFD receives `adev->enable_mes`; that field
  is set only for GC11/GC12 MES IP blocks, not GFX8. The reference Polaris
  route is therefore non-MES `execute_queues_cpsch` →
  `unmap_queues_cpsch`, consistent with the preserved preemption-timeout log.
- This replaces the prior conditional MES/remove-queue hypothesis as a
  reference-source explanation. Exact CachyOS source equivalence and the
  incident-time internal errno remain OPEN.
- The retained pre-review TopK source routes both large vocabulary cases to
  **mbtopk**, not warptopk or sbtopk. `libtorch_hip.so` build ID
  `392fee76f7a23e82b345dae1b40d02bd0ea32cd5` and SHA-256
  `dd0b4030…` are recorded, but selected HSACO/kernel remains OPEN.
- Evidence: `docs/receipts/gfx803_k205_t104_source_binary_attribution_20261114.json`.
- K2.05/T1 and stable KFD reset recovery **OPEN**; prioritize
  historical boot state and offline TopK code-object mapping,
  then only a recoverable non-display-host trace.


## T1.05 offline ELF/code-object tooling — 14 November

- Exact candidate HIP SHA/Build ID gate, TopK ELF symbol/fatbin
  inventory, optional AMDGPU ELF candidate extraction, regression
  tests and extended KFD/TopK join committed, **host run pending**.
- K2.06 GFX8 non-MES reference path, T1.04 mbtopk source candidate
  established by 7e0d5dd; T1.06 source→binary build linkage and
  T1.07 actually selected kernel/HSACO **OPEN**. K2.05 actual KFD
  return and KFD durable recovery remain OPEN.
- Runbook: docs/GFX803_T105_K206_MBTopK_BINARY_MAXCUT_20261114.md.
- No new GPU runs, kernel fixes or Schaka PR changes.

## T1.05 host audit executed — 14 November

- CPU-only audit completed after its output guard was corrected: 25/25
  focused offline tests passed.  The guard now streams TopK-matching symbol
  lines from the large ELF and records the complete matching count separately
  from the 300-entry display cap; ordinary `.rodata` is no longer mislabeled
  as an offload payload.
- The exact candidate `libtorch_hip.so` identity was reconfirmed: SHA-256
  `dd0b4030c4034fdab10daa48dd260397f4de2348ad1cec7ef95474ebd05fa0d2`,
  Build ID `392fee76f7a23e82b345dae1b40d02bd0ea32cd5`.  It has one
  `.hip_fatbin` payload (42,919,798 bytes; SHA-256
  `35733398518e0a82aadbf64a7f9e80874069f4da40e401b4bf772cab37623de3`).
- The bounded scanner found no directly embedded AMDGPU ELF in that payload.
  This is **inconclusive**, consistent with a wrapped or compressed code-object
  format; it does not eliminate `mbtopk`, identify a gfx803 HSACO, or identify
  the incident dispatch.
- Host-local superseding receipt directory:
  `/mnt/truenas/comet-net/experiments/gfx803_t105_k206_20261114_r2/`.
  The first directory is retained as a superseded tool-output attempt, not
  evidence.  No HIP initialization, GPU workload, trace attachment or kernel
  modification occurred.


## T1.08 fatbin container investigation — `052889b` handoff

- Operator: 25/25 offline tests PASS; exact `libtorch_hip.so`
  SHA/Build ID reconfirmed, 42.9 MB HIP fatbin extracted,
  6,045 TopK-matching host symbols, no directly embedded
  AMDGPU ELF found (inconclusive).
- Added `gfx803_mbtopk_offload_container_audit.py`:
  offline CCOB/Clang header parser, SHA, optional
  `clang-offload-bundler --list`, exact advertised gfx803
  target extraction with fail-closed bounds.
- CPU-only tests: `test_gfx803_mbtopk_offload_container.py`.
  **Committed; host execution pending**.
- See `docs/GFX803_T105_K206_MBTopK_BINARY_MAXCUT_20261114.md`
  for one-run commands and the preferred small JSON data handoff.
- K2.05 incident fence return and T1.07 actual executing HSACO
  remain OPEN; no GPU run.

## T1.08 CCOB/container audit executed — 14 November

- The fatbin is a CCOB v3 compressed container.  Its first header describes
  an internal member, not the full concatenated payload; the declared-size
  mismatch is therefore not classified as corruption.
- The matching staged ROCm 10.1 `clang-offload-bundler` lists one unique
  target, `hip-amdgcn-amd-amdhsa--gfx803`, repeated **219** times alongside
  219 host bundles.  The target parser was corrected to accept the normal
  `hip-` spelling and record unique IDs plus occurrence counts.
- Offline unbundling of that explicit target produced a 5,246,152-byte
  AMDGPU ELF with `gfx803` flags (SHA-256
  `3aacb81a0c571c10d842922935db1f248a59602746d0497f5aa383fad101a0c8`).
  It remains local; neither it nor the 42.9 MB fatbin is committed.
- Static symbols and metadata contain no readable `mbtopk`, `topk`, or
  `gather` label.  That does not refute the source candidate and is not proof
  of incident dispatch; T1.07 remains OPEN.  No GPU/HIP work occurred.


## Integrated T1.09–T1.12 / K2.07–K2.08 host run prepared

- a45ad49 original gfx803 HSACO receipt remains accepted:
  5,246,152-byte extracted object, SHA 3aacb81a0c57…,
  one gfx803 bundle class present 219 times, no named mbtopk
  symbol in initial scan. Historical execution still unproven.
- Implemented: exact SHA and machine-gated ELF metadata,
  bounded AMDGPU MessagePack PT_NOTE kernel fields,
  original TensorTopK source hash/launch terms, optional
  metadata-scoped ISA disassembly, targeted non-MES source audit,
  inert dedicated-host KFD trace proposal, full fail-closed join.
- Single CPU-only runner:
  scripts/run_gfx803_t109_k207_offline.sh.
  Runbook: docs/GFX803_T109_K207_FULL_OFFLINE_HANDOFF_20261114.md.
- **New host tests have NOT yet run.** No GPU, tracefs or
  kernel operation; no release, patch or causal admission.
- T1.06 original binary/loader linkage, T1.07 actual
  incident kernel, K2.05 internal KFD error, K2.07 exact
  CachyOS match, and stable recovery remain OPEN.


## T1.13–T1.14 full CCOB membership audit implementation

- **11223f6:** operator accepted 61/61 CPU-only contracts and
  committed four HSACO/source/evidence-join receipts.
- Pure Python AMDGPU note decoder: 336 kernels in prior 5.25 MB
  gfx803 object; zero *readable* TopK-name matches (not a
  negative result against mbtopk).
- New SHA-verified, header-length-bounded CCOB member index and
  offline per-member gfx803 unbundle/metadata/TopK-name
  inventory implemented. Unit tests committed but **not yet
  host-run**.
- Runbook:
  docs/GFX803_T113_T114_CCOB_ALL_MEMBERS_20261114.md.
- T1.06 original build/loader proof, T1.07 actual incident
  dispatch, K2.05 internal fence return and release all OPEN.

## K1.03/K2.01 exact CachyOS source and callback audit — 14 November

- The published `cachyos-7.3.0-2.tar.gz` source release was retrieved to
  TrueNAS and SHA-256 verified as
  `cb70a96c13f491230366596d72698f5192f907e6c457ef25b03d28eacc99a23a`.
  Only the relevant AMDGPU/KFD files were extracted.
- Four central KFD source files and `kfd_queue.c` are byte-identical to the
  Linux v7.3 reference used by the earlier static analysis. The exact
  CachyOS release source therefore confirms the non-MES
  `unmap_queues_cpsch -> amdkfd_fence_wait_timeout` log site, the KIQ ring
  test helper, and the KCQ-disable error site.
- The 2025 gfx7/8 doorbell fix is **present**, not missing: both gfx7 and
  gfx8 bridge tables register intentional zero-return
  `kgd_hqd_sdma_get_doorbell` stubs. Read-only postboot-module disassembly
  found both compiled stubs returning zero. The distinct gfx7/8 AQL
  half-queue-size validation is also present.
- These facts do not establish historical callback invocation, the incident
  fence return, or a source-to-rebuilt-module identity. The TopK dispatch and
  KFD recovery remain separate causal gates. Receipt:
  `docs/receipts/gfx803_kfd_exact_release_doorbell_queue_20261114.json`.

## Cross-incident reset-order audit executed — 14 November

- The cross-incident RCA is accepted as a **shared recovery-failure class**,
  not a claim that Ollama, WhisperX, Wayland and TopK share one initiating
  kernel bug. The first retained November timeout is a KWin gfx timeout; the
  historic TopK process remains a temporal trigger rather than proven first
  non-progressing kernel.
- Six CPU-only audit contracts passed against the SHA-verified CachyOS
  `7.3.0-2` extraction. Its source retains: reset-lock-before-KFD-preempt in
  normal and PCI recovery, scheduler-resume-before-GPU/KFD-post-reset, and no
  restore-during-reset `-EAGAIN` guard. The GFX8 KIQ quantum exemption is
  already present.
- The later 12:40:55 `qcm fence wait loop timeout expired` message maps to
  the exact source branch returning `-ETIME`; it does **not** supply the
  unknown internal return for the first 12:39:28 quiesce failure.
- Receipt: `docs/receipts/gfx803_gfx8_reset_order_audit_20261114.json`.
  No GPU/HIP execution, module replacement, dynamic trace or recovery claim
  occurred. A causal patch still requires a non-display, independently
  recoverable host.

## 14 November — persistent Polaris GPU wedge: recovery critical path

- **Problem definition:** RX580 GFX8 becomes unusable after a workload-triggered ring/queue stall. The host's emergency terminal remains usable; manual driver reset and Wayland restart have not restored GPU function. In November, first KFD queue-preemption failure and KIQ `-110` preceded BACO, which was followed by repeated resets (up to reported reset 62), VRAM loss, and no durable accelerated desktop.
- **R0 evidence:** historical March and November traces + source error paths established; initiating instruction or universal single culprit **not proven**.
- **R1 hardware reset:** OPEN and **highest priority** — source-trace GFX8 CP/MEC, KIQ/KCQ, soft-reset, BACO, GPUVM/GART and firmware reinitialization; determine earliest failed *post-reset* fence.
- **R2 upstream applicability:** PARTIAL — v6.13/6.19/7.3 reset ordering and verified 7.3.0-2 source, existing GFX8 KIQ quantum exemption and fixed doorbell callbacks. NAK'd reset-lock reorder is not a deployable fix. Earlier Arch-era exact kernel metadata may still be missing.
- **R3 recovery integrity:** DRAFT in [PR #7](https://github.com/chboishabba/gfx803_compat_graph/pull/7). Reset-aware `start_cpsch` RFC, CPU-only C model and patch context tests. `kgd2kfd_post_reset` failure may be ignored by AMDGPU caller and leave KFD locked; **none of this proves physical GPU recovery**.
- **R4 actual hardware correction:** OPEN; not written, not kernel-built or reviewed. Avoid installing R3 RFC on the display GPU.
- **R5 physical validation:** BLOCKED without an independent recoverable gfx803 host. Acceptance requires fresh KIQ/KCQ/GFX/SDMA progress, fresh `/dev/kfd` and KFD dispatch, and new accelerated DRM/Wayland rendering **without reboot**.
- **R6 stable factory release/upstream:** BLOCKED until R4/R5; historical 120-case TopK and bounded C2 passes are scoped trigger/semantic controls, not recovery acceptance.
- **Current source of truth:** [docs/GFX803_PHASE_DELIVERABLES_RECONCILIATION_20261114.md](docs/GFX803_PHASE_DELIVERABLES_RECONCILIATION_20261114.md), section *GFX8 persistent GPU wedge: authoritative recovery roadmap (R0–R6)*. Track work under the existing draft PR #7.

## R1/A1–A2 source-traced post-BACO failure — 14 November

- **New source audit:** [docs/GFX803_R1_SOFTRESET_BACO_POSTRESET_VM_RCA_20261114.md](docs/GFX803_R1_SOFTRESET_BACO_POSTRESET_VM_RCA_20261114.md). `gfx_v8_0_hw_fini` ignores `gfx_v8_0_kcq_disable` failure; first `KIQ -110` before BACO does not establish post-BACO KIQ nonprogress. Normal full-resume phase2 includes gfx/KIQ/compute scratch ring tests; `GPU reset(2) succeeded!` suggests they may have completed **transiently**, not that KWin's subsequent VMID7 graphics memory access was valid.
- **Original measured counts:** [docs/receipts/gfx803_r1_nov14_reset_recovery_counts_20261114.json](docs/receipts/gfx803_r1_nov14_reset_recovery_counts_20261114.json): 1,308 lines, 88 soft-reset starts and 88 reported soft-reset successes; two full-reset-success log entries, counters 2 and 62. Both have a fresh gfx timeout 2 seconds later. First post-BACO VM fault is KWin VMID7/PASID7 from TC3.
- **GART-vs-user-VM distinction:** `gmc_v8_0_gart_enable` establishes MC/GART setup and VMID0 flush, **not** KWin VMID7 post-VRAM-loss BO/page-table restoration. Normal KWin CS updates PDEs/BOs separately.
- **New CPU-only tooling:** `scripts/gfx803_reset_wave_chronology.py` with `tests/test_gfx803_reset_wave_chronology.py`; host/CI execution not yet asserted. No GPU, kernel patch, driver reset or graphics execution in this step.
- **Gate result:** R1 source state machine substantially mapped; actual H1 residual CP versus H2 graphics GPUVM stale mapping versus H3 firmware/ASIC under load **OPEN**. Next A2a trace post-reset BO/VMID/context revalidation, then design specific R4 correction. Keep PR #7 as existing recovery rollup.


## 14 November — T1/T2 initiating-failure cut (pre-timeout corruption + reviewed SVM race)

- **T1 incident join source-complete, physical initiating dispatch OPEN:** March 20 Ollama pink/green checkerboard then first cited `comp_1.3.1` timeout; March 25 and Nov 14 first recorded gfx/KWin timeouts; WhisperX long-file transcribe/align failures vary and profiling changes outcomes. User has confirmed visible corruption immediately before GPU crash. This does **not** identify the first device instruction.
- **T2 ordinary TTM/graphics VM sync source-mapped:** BO move DMA fence, TTM cleanup, KFD/BO reservation synchronization, VM PT/PDE updates and CS job dependencies exist in v7.3; do not assert an absent fence without a specific broken producer→consumer edge.
- **T2 SVM high-alpha:** Linux v7.3 `kfd_svm.c::svm_range_evict` lets a second XNACK-off MMU invalidator return before the first `kgd2kfd_quiesce_mm` finishes. AMD independently proposed a process `evict_lock` on Nov 9, Reviewed-by Felix Kuehling. **Source race established, incident association unknown.**
- **RFC backport staged:** [v7.3 SVM patch](patches/linux/gfx803-t1-svm-concurrent-eviction-v73-rfc.patch), direct original-source four-hunk check completed, CPU-only interleaving and git-apply tests committed. Executed [35/25-state ordering receipt](docs/receipts/gfx803_t2_svm_two_notifier_exhaustive_model_20261114.json) confirms original unsafe early return and successful-quiesce mutex negative control. Kernel compile and full committed Python test run **not** verified.
- **Evidence and gates:** [T1/T2 source and falsification matrix](docs/GFX803_T1_T2_PREHANG_MAXCUT_SOURCE_AND_SVM_RACE_20261114.md). Before declaring the SVM patch to fix RX580: prove an actual SVM mapping, overlapping MMU invalidations and queue-preemption interval in the failing workload. DPM/VRAM physical instability and actual first TopK dispatch remain open.
- **External-control correction:** July SDMA multi-GPU drain and Sept gfx12 DCC workarounds are not direct single-GFX8 fixes; #4919 is RX6800 XT, #6386 gfx1103, CachyOS #930 RX590 PRT, Bazzite #3383 genuine RX580 artifact report. `reset_method=1` is **mode0**, not legacy.
- All patches remain **draft under PR #7**; no module loaded, no deliberate known-hang workload on single display RX580.
