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
