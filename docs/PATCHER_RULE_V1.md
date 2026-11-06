# PATCHER_RULE_V1

This document captures the first practical patcher rule that is justified by the
current retained RCA set and the bounded boundary probes.

The goal is not to prove the smallest possible old-ABI island yet. The goal is
to encode the smallest rule that is already operationally defensible on this
repo's `gfx803` / Polaris host path.

Scope: this rule resolves `RCA_TRACK_1` (runtime-boundary) only. It does not
guarantee correctness (`RCA_TRACK_2`) or stability under load
(`RCA_TRACK_3`).

## Rule

```text
PATCHER_RULE_V1
OLD_CORE = full lib-compat/
SAFE_NEW = none by default
ENV_RULES = use host-docker-python.sh with the extracted control runtime island
VALIDATION = rocminfo pass + torch.cuda.is_available() == True
```

## Why this is the current rule

The current evidence does not support a tiny shim-style patch.

What the retained and newly probed surfaces now show:

- the extracted control `6.4` island in `lib-compat/` + `docker-venv/` is the
  only runtime boundary currently proven to satisfy both:
  - host-side `rocminfo`
  - host-side torch GPU visibility
- latest HSA alone can preserve `rocminfo`, while torch still loses GPU
  visibility
- old HSA + old HIP is not enough when newer HIP-dependent `.7` consumers still
  leak in
- widening the old subset to include the first core HIP-dependent math stack
  still allowed newer HIP `.7` consumers to bind against old ROCR/HSA and fail
  at import time

That means the problem is currently best modeled as a coherent runtime-island
constraint, not a one-library or two-library shim.

Archive-backed clarification:

- the older `ROCm RX580 noise issue` conversation preserved in the local chat
  archive reinforced the same direction from the workload side:
  - ComfyUI noise was dominated by stateful drift, solver flapping, and
    first-corrupted-tensor investigation
  - `bf16` / `bfloat16` appeared only as minor side leads
- `PATCHER_RULE_V1` should therefore be read as the practical answer to the
  runtime-boundary problem, not as a conclusion that `bf16` support was the
  central unresolved blocker

## Current interpretation

For `gfx803`:

- use the full extracted control runtime island by default
- do not mix in newer HIP-dependent ROCm userspace libraries unless a boundary
  probe explicitly validates them
- treat `rocminfo pass` as necessary but not sufficient
- require `torch.cuda.is_available() == True` for a patcher success claim

This rule answers the runtime-boundary question only. It does not by itself
resolve the older workload-correctness RCA around ComfyUI noise, stateful
drift, solver flapping, or other cumulative precision/correctness failures.

## Validation contract

The patcher rule is valid only if both checks pass:

1. `rocminfo` succeeds under the staged runtime island
2. torch reports GPU visibility through the host wrapper

Example torch validation shape:

```bash
bash scripts/host-docker-python.sh -c \
  'import torch; print(torch.cuda.is_available(), torch.cuda.device_count())'
```

Expected shape:

```text
True <n>
```

## Script entrypoint

The repo now carries a first patcher helper:

```bash
scripts/apply-gfx803-patcher-v1.sh
```

What it does:

- stages a runtime root from the repo's `lib-compat/` and `docker-venv/`
- validates the staged root with:
  - `rocminfo`
  - torch GPU visibility
- optionally executes a target command through
  `scripts/host-docker-python.sh` with that staged runtime root

Useful forms:

```bash
scripts/apply-gfx803-patcher-v1.sh --validate-only
scripts/apply-gfx803-patcher-v1.sh -- -c 'import torch; print(torch.cuda.device_count())'
scripts/apply-gfx803-patcher-v1.sh -- -m whisperx /path/to/audio --model small --compute_type int8 --language en
```

## Scope boundary

This is a `v1` rule, not a final minimality proof.

Later work can still try to shrink `OLD_CORE`, but that should happen through
explicit boundary probes, not by changing the default patcher rule first.

For now, the right operational default is:

> preserve the full extracted `6.4` control island unless a narrower boundary is
> explicitly proven.
