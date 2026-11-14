# T1 — incident-time dispatch, allocation and memory provenance

**14 November 2026; PR #7 single rollup.** This document is a committed, bounded first-failure join, **not a claim that code-object inclusion proves a kernel executed**. Machine-readable original-input source receipt: [`docs/receipts/gfx803_t1_t2_gate_matrix.json`](receipts/gfx803_t1_t2_gate_matrix.json). Canonical [60-source ledger](GFX803_EXTERNAL_REFERENCE_LEDGER_20261114.md).

## A1: allocator/copy provenance by affected workload

| Workload | Raw / first-party retained evidence | Closest verified kernel path | Actual incident-time SVM/userptr registration? | Causal status |
| --- | --- | --- | --- | --- |
| 20 March Ollama `mistral` | Kernel messages quoted in original incident note: `init_user_pages: Failed to get user pages: -1`, first cited timeout `comp_1.3.1`; visible pink/green checkerboard after successful response | `amdgpu_amdkfd_gpuvm.c::init_user_pages` `userptr` path calling `amdgpu_ttm_tt_get_user_pages` | **Userptr path evidenced** by original message. KFD SVM range and overlapping notifier **not captured** | A1-userptr source callsite matched; underlying `-1` cause unknown |
| 27 March WhisperX | `transcribe` started; no stage completion; later GPU reset/coredump note | ROCm/HIP inference pipeline (actual stage call trace not retained here) | **Unknown**; do not infer from model name | Failure stage bounded only |
| 30 March WhisperX | Profiler/non-profiler differential; D2H/H2D transfers and active `-1 ns` host waits adjacent to later hangs; one run had page-not-present/privilege GPU fault | HIP/HSA copy, signal-wait and KFD queue path; **pageable copy may register SVM**, pinned userptr and ordinary DMA also possible | **Unknown**; no original per-buffer flags, HSA lock-return trace or notifier timeline attached to this commit | Bounded copy/wait exposure, not copy-race proof |
| 14 November TopK | Cached wheel: f32 `[1,151936]` success, f32 `[32,151936]` hang. Source route selected `mbtopk`; libtorch_hip ELF SHA `dd0b4030...`, Build ID `392fee76...`; 219 CCOB members and extracted HSACO metadata previously enumerated | PyTorch HIP device allocation and source-selected multiblock TopK; KFD/GFX non-MES reset path | **Unknown**; no original allocation trace or MMU event tracing | Original first HSACO / PASID / dispatch **OPEN** |
| KWin/Plasma/browser | User-confirmed graphics corruption immediately before GPU crash; KWin first *recorded* gfx timeout 12:39:28. Browsers sometimes disappear | Graphics CS/TTM/BO/GPUVM and compositor DMA-BUF pathways, depending actual build | **No browser process death mechanism proven**; need process exit/coredump/oom ID | May be victim of shared failure, not proven initiating submitter |

### Cross-workload controls already measured

- The retained **unpatched-safe** TopK CSV has `32x151936 f32` marked `known-fault-skip`, **not a success or a reproduced fault in that arm**. `1x151936 f32` passes in that arm at median **0.429 ms**, while the *separate cached-pre-review wheel* records median **0.4008 ms** prior to hanging at the larger shape. These numbers come from different arms and cannot be merged.
- The `32x151936 f16` unpatched-safe control passed with median **3.7567 ms**, as did `1e6 f32 k10`, `1e6 f32 k1000`, `16e6 f32 k100` and `2048x128 f16 k8`. **Size alone does not produce the same fault for every dtype/shape/algorithm**.
- The March 30 `HIP_LAUNCH_BLOCKING=1` control is a **summary-only** success (`exit_code=0`, `kept_bundle=0`); profiler use also changes timing/outcome. Neither proves a specific race, but both motivate queuing/timing-sensitive negative controls when a safe independent GPU becomes available.

## A2: first stalled job and source→binary→execution proof chain

```text
retained TensorTopK.hip SHA-256 acb592c...                SOURCE accepted
        │
        ├─ selects mbtopk on f32 1×151936 and 32×151936 SOURCE-CANDIDATE
        │
        ▼
libtorch_hip.so SHA-256 dd0b403... / Build ID 392fee76...  BINARY accepted
        │
        ├─ offload CCOB includes gfx803, extracted HSACO source context
        │   but no original compiler/build manifest/loaded-maps receipt
        ▼
actual benchmark-loaded ELF + runtime-selected HSACO      NOT CAPTURED
        │
        ▼
dispatch kernel name, grid, queue/doorbell/PASID/fence     NOT CAPTURED
        │
        ▼
first GPU dispatch not completing, first FENCE            NOT CAPTURED
```

**Observed kernel boundary** at 12:39:28: `ring gfx timeout, signaled seq=131707128, emitted seq=131707130`; process `kwin_wayland` PID 1877, thread PID 2273. This is first **reported timed-out gfx job**, not the earliest compute instruction. At 12:39:28 KFD preemption fails, at 12:39:29 KIQ test returns `-110`, then BACO/reset. The original November journal retained 1,308 lines and **no original binary devcoredump after reboot**, although it logs creation. The **first KFD internal error** (`-EIO`, `-ETIME` or other) is not printed in the first failure window. A later `qcm fence wait loop timeout expired` establishes the later `-ETIME` site, **not** the first return.

**Source/binary identity limit:** 219 CCOB member inventory and source-selected `mbtopk` cannot establish runtime dispatch, despite original ELF/target checks. See [T1.05/K2.06 original runbook](GFX803_T105_K206_MBTopK_BINARY_MAXCUT_20261114.md) and [original attribution receipt](receipts/gfx803_k205_t104_source_binary_attribution_20261114.json). Fresh recompilation cannot reconstruct the historical executed GPU packet.

## A3: MMU and HMM evidence classification

- **Ollama:** real `userptr` page-acquisition path reported; original `-1` is an errno from `amdgpu_ttm_tt_get_user_pages`, not an independently identified permissions failure or SVM MMU notifier event. Actual userptr flags/VA/PASID unretained.
- **WhisperX:** real D2H and H2D calls, with host waits and failures; HSA `hsa_amd_memory_lock` / SVM registration may be reached by pageable copies, but **not captured** in these incident documents.
- **TopK:** **zero named SVM/userptr events in the kernel journal**; historical trace instrumentation for those was not enabled/retained, so absence is **not a negative control**.
- **Browser:** no retained browser PID signal/exit/OOM/coredump join in cited artifacts. The reported spontaneous closures might be device-loss, process failure or OOM; cannot equate them to generation guard behavior.

## A4: bounded cross-incident result

**Common observed failure class:** sustained or mixed compute activity, visible corruption in reported incidents, GPU forward-progress failure and unreliable recovery with GFX/KFD ring timeouts. **Different first recorded rings:** `comp_1.3.1` Ollama vs `gfx` November/WhisperX. **Different evidence:** Ollama userptr page get `-1`; WhisperX async copy/host wait and timing/profiler confounder; November multiblock TopK source route and KWin first recorded gfx fence. No original first stalled kernel identified.

## Deliverables, command and acceptance

[Offline parser](../scripts/gfx803_incident_join.py) and [regressions](../tests/test_gfx803_incident_join.py) consume already retained local source files. **No GPU initialization, tracing writes or driver reset.** Example for a checkout of this PR:

```bash
python3 -m unittest discover -s tests -p 'test_gfx803_incident_join.py' -v
python3 scripts/gfx803_incident_join.py \
  --input topk docs/receipts/gfx803_topk_pr8_review_safe_20261114/kernel-previous-boot.log \
  --input topk docs/receipts/gfx803_topk_pr8_review_safe_20261114/unpatched.csv \
  --input ollama docs/INCIDENT_2026-03-20_OLLAMA_MISTRAL_KFD_RESET.md \
  --input whisper27 docs/INCIDENT_2026-03-27_WHISPERX_TRANSCRIBE_RESET.md \
  --input whisper30 docs/INCIDENT_2026-03-30_WHISPERX_ALIGN_GPU_HANG_AND_ROCPROFV3_SUCCESS.md \
  --out /tmp/gfx803_t1_t2_incident_join_new.json
```

The newly committed script tests are **not** reported kernel-built, CI-verified or device-tested. [The separately executed eight-input source receipt](receipts/gfx803_t1_t2_gate_matrix.json) is the current grounded output, including missing fields. Avoid overwriting or rebranding absent raw records as direct measurements.

**Next exact gate:** retrieve any *existing* saved host-side HSA/ROCprof/devcoredump/loader mapping receipt with relevant kernel execution / SVM registration. If none exists, A2/A3 remain “unobserved historically” and future attribution requires independent recoverable hardware, instrumented without rerunning the display-card wedging shape.
