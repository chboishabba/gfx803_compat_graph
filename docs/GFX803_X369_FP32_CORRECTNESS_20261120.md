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
Physical CPU and GPU execution now maintainer-reported; see appended receipt. Full unary branch, captured original
failing operands, matched explicit reduction order, FP64 optimizer oracle
and rigorous floating error enclosure remain OPEN.

Exact-real first step with equal initial parameters: eta*2*delta/(delta+2*eps)
is the tight worst-case bound, eta=1e-4 eps=1e-8, about 9.64e-5 for
delta=1.86e-8. Not a native rounding certificate or proof of cause.


## Physical differential receipt — 20 November 2026

Maintainer-reported execution of 7dd26547 on pinned Schaka 10.1,
Torch 2.14.0+gitd70fd61, HIP 7.16.26385, RX580 gfx803.
Raw cpu.json and gfx803.json are reported at
/mnt/truenas/comet-net/gfx803_compat_graph; not attached or independently inspected.

| Scale | CPU FP32 original/fused max | GPU FP32 original/fused max | Reported FP64 reference max |
|---|---:|---:|---:|
| 1 | 3.8147e-6 | 3.8147e-6 | 5.33e-15 |
| 1e-4 | 2.3283e-10 | 2.3283e-10 | 4.34e-19 |
| 1e-8 | 2.1316e-14 | 2.8422e-14 | 2.65e-23 |

| Scale | CPU/GPU parameter max | First moment max | Second moment max | GPU parameter repeat max |
|---|---:|---:|---:|---:|
| 1 | 2.3283e-10 | 4.1723e-7 | 1.6689e-6 | 0 |
| 1e-4 | 4.6566e-10 | 3.2742e-11 | 1.5987e-14 | 0 |
| 1e-8 | 4.6566e-10 | 4.4409e-15 | 1.3235e-22 | 0 |

Reported GPU scalar/foreach parameter difference zero. The current script
does not directly emit cross-mode differences; retain that claim as
maintainer-reported, pending raw receipt verification. Maximum equality
is not elementwise equality. CPU counterexample rejects necessity of
gfx803 for this synthetic discrepancy; reassociation is strongly supported
but not uniquely proven. Identical-byte optimizer corruption not reproduced
on this suite; no formal rounding budget or universal optimizer claim.
Original full-head failing operands and native arithmetic certification open.
Strict original FP32 matched training remains FAIL. No other gates promoted.

## Exact reference extension

The revised assay independently contracts the stored finite FP32 x/H/q operands using Python Fraction, per directed triad channel. Emits exact rational error at maximum-error coordinate for each original/fused path, in addition to FP64 reference. Direct scalar/foreach comparison now includes parameters and both moments at each step. This is an exact reference for the synthetic directed gradient, not an enclosure of the native full head or optimizer. New CPU unit tests source-written; rerun only as needed for new receipt fields. Original failing operands remain absent.
