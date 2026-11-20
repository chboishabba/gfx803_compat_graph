# Correctness-only X369 receipt and FP32 differential assay (2026-11-20)

Source: [LeechTransformer PR 5](https://github.com/chboishabba/LeechTransformer/pull/5), receipt commit 116e36dff7e09f61dd3f440968cfa91043d70aac, tested 8cafe0aa. Maintainer-reported physical RX580 gfx803, Schaka 10.1, HIP 7.16.26385, Torch 2.14.0+gitd70fd61; raw host logs not attached.

| Gate | Evidence |
|---|---|
| Native strict routing and recurrence | scoped PASS, Nat [0,2,9,0] and [0,9] |
| FP64 original/fused GPU vs GPU training | 20/20 at 1e-10 tolerance; not CPU vs GPU |
| FP32 component forward/activation/history gradients | reported zero discrepancy |
| FP32 residual head gradient | max 1.86e-8 |
| FP32 parameter difference | step 1 3.26e-5; step 20 1.58e-4 |
| Strict FP32 training | FAIL; cause OPEN |

Do not reopen existing C2 CPU/GPU or bounded TopK acceptance absent regression.
No implication for large mbtopk hang, KFD recovery, OpInfo or other layers.

## Diagnostic

Run from repository root with existing pinned Torch:
```sh
python scripts/gfx803_fp32_adamw_differential.py --cpu-only > cpu.json
python scripts/gfx803_fp32_adamw_differential.py > gfx803.json
```

Small fixed synthetic operands, directed half of source residual head only,
fixed cotangents, CPU-generated FP32 bytes cast to FP64 for reference.
Compare original feature/linear and fused bmm gradient on CPU and GPU.
Identical gradient bytes feed 20 AdamW steps with scalar and foreach modes;
record parameter, first and second moments against corresponding CPU run
and same-device repeat. No large TopK or model training, no GPU fallback.
CPU FP64 is a numerical reference, not a certified oracle. No thresholds
invented: receipt is MEASURED_NOT_CERTIFIED; nonfinite values rejected.
Source-written, execution pending. Full unary branch, captured original
failing operands, matched explicit reduction order, FP64 optimizer oracle
and rigorous floating error enclosure remain OPEN.

Exact-real first step with equal initial parameters: eta*2*delta/(delta+2*eps)
is the tight worst-case bound, eta=1e-4 eps=1e-8, about 9.64e-5 for
delta=1.86e-8. Not a native rounding certificate or proof of cause.
