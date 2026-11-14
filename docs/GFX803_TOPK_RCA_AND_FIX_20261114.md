# TopK November incident — actionable RCA, repair and benchmark safeguard

**Scope:** RX 580/gfx803, 14 November 2026. This document distinguishes source-level root-cause attribution, observed runtime evidence, the actual TopK routing fix, and a separate KFD recovery issue. It must not claim a new GPU test.

## Causal hypothesis supported by original evidence

1. The original cached **pre-review** wheel ran 10 warmups + 50 timed iterations per case. Float32 `[1,151936], k=50` passed (median 0.4008 ms); `[32,151936], k=50` then returned a GPU Hang. The GPU stayed wedged through reported reset successes. Original: `docs/receipts/gfx803_topk_pr8_review_safe_20261114/INCIDENT_20261114_GPU_HANG.md` and `patched-pre-review-wheel.csv`.
2. The SHA-verified retained `TensorTopK.hip` for that **different** wheel disables `warptopk` but leaves the multi-block heuristic active. Both shapes select **`mbtopk` at source level**; neither selects `sbtopk` under that source path. Receipt: `docs/receipts/gfx803_k205_t104_source_binary_attribution_20261114.json`.
3. `mbtopk` is therefore the **leading trigger candidate**, not a demonstrated runtime-selected kernel. Offline inspection of all 219/219 CCOB members found no specifically TopK-named decoded kernels; missing readable names do not disprove compiled/mangled/inlined code. There is no incident-time loader map, dispatch trace or physical kernel identity.
4. The journal shows a gfx timeout and failed KFD queue quiesce/restore/resume, with non-MES `unmap_queues_cpsch -> amdkfd_fence_wait_timeout` matching exact verified CachyOS release source. **The GPU trigger and failed recovery are two separate mechanisms.** The fence return was not retained, and the KFD fault is not proof of the initial computational error.
5. The older gfx7/8 zero-return SDMA doorbell callback and half-AQL queue-validation fixes are present in the release source and loaded module. Do **not** revert or reapply them.

## Actual source fix: Schaka PR #8

[Schaka/rocm-gfx803 PR #8](https://github.com/Schaka/rocm-gfx803/pull/8) adds the gfx803 branch to PyTorch `TensorTopK.cpp::should_use_sort`, after the Boolean exception and before the ordinary size heuristic:

```cpp
if (at::detail::getCUDAHooks().isGPUArch({"gfx803"})) {
  return true;
}
```

On non-Boolean gfx803 inputs, the `topk_out_cuda` call reaches `topk_out_with_sort` rather than `launch_gather_topk_kernel`. This **bypasses `warptopk`, `sbtopk`, and `mbtopk`** for that code path. It uses the existing GPU sort-backed TopK implementation, rather than attempting a speculative KFD patch.

**Critical identity distinction:** the November hang was in an older, cached, manually patched **pre-review** wheel. It cannot be used as a failure verdict on the reviewed `isGPUArch` + fail-closed driver-script patch. Conversely, passing small-shape 120-case semantics and bounded C2 controls on a candidate wheel is not a benchmark or sustained-stability receipt for a newly rebuilt reviewed-source wheel.

## Fix execution order

**A — Immediate stop / mitigation (no destructive tests)**

- Quarantine the incident wheel hash and never invoke its known-fault `[32,151936], k=50` shape on the sole Wayland display RX 580.
- Keep the known-working C2 model-level `torch.sort` selector as a controlled workaround, not a claim that native `torch.topk` has been repaired.
- Build the *reviewed* PR #8 source with the expected PyTorch pin, architecture helper, fail-closed driver script and `TENSOR_TOPK_OPT_LEVEL=-O0`. Record exact rebuilt wheel SHA, selected `libtorch_hip.so` SHA/Build ID, patch SHA and mapped libraries. Do not reuse the pre-review cached wheel under the reviewed label.

**B — Non-destructive CPU-only check**

- Verify source contains the architecture branch *above* the normal size heuristic; check all references to the old candidate patch are classified as superseded.
- Verify the candidate wheels are distinguished by actual byte hashes.
- Execute `python3 -m unittest discover -s tests -p 'test_gfx803_topk_pr8_benchmark.py' -v`. That suite does **not** initialize HIP.

**C — Decisive hardware acceptance on an independently recoverable machine**

- Run source-pinned, single-case semantic and performance checks for the reviewed wheel and retain actual kernel/HSACO attribution and HSA library maps.
- First test safe, bounded input; then the specific old-fault shape only with a **non-display GPU, out-of-band management, remote durable logs and independent power recovery**.
- Capture KFD fence return and queue state if the fault repeats. If reviewed sort-backed TopK passes, credit a successful targeted TopK workaround for the measured scope; do not require resolution of unrelated KFD hardware reset behavior to explain the old source-route difference.
- If reviewed sort-backed TopK also hangs, compare its dispatch identity and fault chronology with the old route before changing the driver or blaming `mbtopk`.
- Benchmark against the documented control with exact shape/dtype, timing, correctness and hash receipts. Do not count known-fault skips as passes.

## Benchmark safety fix implemented in this branch

`scripts/gfx803_topk_pr8_benchmark.py` now **withholds cases 0, 1 and 4 by default**. These are historical fault cases across the unpatched and pre-review wheels. The prior default order included case 4 immediately after case 3; process separation did not isolate the GPU, and the subsequent Wayland compositor failed.

Automatic post-fault HIP health-check/retry is disabled. A timed-out or crashed child terminates the suite without further GPU work. Skipped cases make the suite incomplete/nonzero, rather than a successful full benchmark.

For a **qualified, independently recoverable** host only, the runner accepts `--enable-known-fault-cases --safe-host-receipt PATH`. This is an explicit *operator attestation*, not hardware verification. The JSON must have all four values true:

```json
{
  "schema": 1,
  "non_display_gpu": true,
  "out_of_band_management": true,
  "durable_external_logging": true,
  "independent_power_recovery": true
}
```

**Any GPU benchmark invocation now requires the same eligible-host receipt**, including cases not previously known to fault. The known-fault cases additionally require `--enable-known-fault-cases`. The attestation is not a physical test of host recoverability.\n\nThe normal RX 580 display desktop does **not** meet this safety contract. Do not create a fictitious receipt to bypass the guard. Direct `--case 0/1/4` is guarded too.

## Remaining proof obligations, not blockers to beginning the fix

- **T1.06/T1.07:** exact old process binary/HSACO and dispatch never captured; a *future* trace proves future-run behavior, not historical identity.
- **K2.05:** exact non-MES fence return not captured; KFD recovery may need its own demonstrated correction.
- **Reviewed PR #8:** source rebuild + per-shape correctness, performance, multi-run reliability on genuinely recoverable hardware.
- **Release:** whole-stack stability and independently restored Nix/Cachix closure.

**Disposition:** `mbtopk` is a supported source-level suspect; **force sort-backed TopK via reviewed PR #8** is the concrete candidate fix. **KFD reset failure is independently observed**, and an already-present callback fix is not an appropriate speculative target. Attribution and release gates remain open until measured.
