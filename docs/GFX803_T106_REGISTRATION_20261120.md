# T1.06 next offline registration cut (2026-11-20)

Use original SHA/Build-ID-bound libtorch_hip.so from T1.05. No torch import,
no HIP dispatch, no replay of known wedging test. T1.13/T1.14 complete.

Inventory exact host symbols, relocation references and registration entry
points with the new script; its output is candidate linkage, not proof of
source build or historical loader identity. Preserve source build manifest,
compiler invocation and incident loader records independently.

```sh
BASE=/mnt/truenas/comet-net/.gfx803-schaka-101-work/out/pytorch-topk-gfx803-20261109
python3 scripts/gfx803_topk_registration_inventory.py \
 --elf "$BASE/python-overlay-r2/torch/lib/libtorch_hip.so" \
 --receipt docs/receipts/gfx803_k205_t104_source_binary_attribution_20261114.json \
 --out /mnt/truenas/comet-net/experiments/gfx803_t106_registration_20261120.json
```

A relocation may refer to a registration routine without identifying a
specific registered kernel. A local static call can be resolved without a
dynamic relocation. Zero matches is not absence of registration.
Next disassemble bounded symbol ranges identified in the receipt, then
join actual registration function arguments to associated code-object
content where possible. Never treat registration as execution evidence.

Lane B: retain original 183-node audit and skip-reason runbook; remaining
167 reported nonpasses need reason recovery, separate from three ordinary
failures and four complex64 fault candidates. No forced upstream skips and
no replay of known GPU faults on sole display GPU.
