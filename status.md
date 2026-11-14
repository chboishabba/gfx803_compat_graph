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
