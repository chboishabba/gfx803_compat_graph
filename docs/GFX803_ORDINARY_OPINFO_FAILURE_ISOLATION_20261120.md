# Ordinary OpInfo failure isolation — 20 November 2026

Use the exact historical traceback first: identify narrow() frame in
reference harness vs patched TensorTopK.cpp vs other source. The existing
120-case semantics matrix uses only 2-D tensors, so it cannot settle scalar
behavior. New scalar diagnostic tests direct native topk and backward
without reference slicing. CPU default; optional one-case GPU action only
on idle healthy recoverable host, external timeout and journal inspection.
Do not run historical large TopK shapes.

```sh
python scripts/gfx803_scalar_topk_probe.py
python scripts/gfx803_scalar_topk_probe.py --dim 0
# Only with physical execution safety conditions satisfied:
timeout 30s python scripts/gfx803_scalar_topk_probe.py --gpu
```

A direct scalar success does not prove original OpInfo passes; exact
reference harness/source and original wheel identity still required.

Sparse: hipsparseCreate error precedes sparse arithmetic. Inspect exact
library from historical loader evidence, then readelf -d and -n on its
resolved path and rocSPARSE dependency. Do not assume missing library.
New direct handle probe defaults to file identity only. Execute explicitly
in matched runtime environment on healthy idle host; it may initialize GPU.
Do not substitute an arbitrary system library. Record exit/logs separately.
```sh
python3 scripts/gfx803_hipsparse_handle_probe.py --library "$EXACT_HIPSPARSE"
# Explicit runtime test, only after verifying matching environment/device:
timeout 30s python3 scripts/gfx803_hipsparse_handle_probe.py --library "$EXACT_HIPSPARSE" --execute
```
No sparse kernel launch. Direct handle success does not close PyTorch
integration or sparse numerical API correctness. A timeout is NOT a
recovery guarantee. No automatic retry. Both scripts source-written,
not executed. Preserve 159 remaining skip recoveries and original faults.
