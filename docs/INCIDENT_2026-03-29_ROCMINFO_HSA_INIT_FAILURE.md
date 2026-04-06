# Incident: 2026-03-29 `rocminfo` Fails at `hsa_init` Under Latest HSA

This note captures the first debugger-backed `rocminfo` failure on the
latest-class HSA lane.

## Why this matters

The repo had already narrowed the `rocminfo` breakage to the HSA side:

- latest `libhsa-runtime64` breaks `rocminfo` on Polaris
- latest HIP alone does not
- old-HSA hybrid lanes can restore `rocminfo`

This incident strengthens that claim. It shows the failure is already present at
`hsa_init()`, before agent enumeration starts.

## Reproducing command

Failing latest-HSA surface:

```bash
env \
  LD_LIBRARY_PATH="$PWD/artifacts/rocm-latest/lib-compat" \
  HSA_OVERRIDE_GFX_VERSION=8.0.3 \
  ROC_ENABLE_PRE_VEGA=1 \
  rocminfo
```

Control surface:

```bash
env \
  LD_LIBRARY_PATH="$PWD/lib-compat" \
  HSA_OVERRIDE_GFX_VERSION=8.0.3 \
  ROC_ENABLE_PRE_VEGA=1 \
  rocminfo
```

## Saved artifacts

- debugger log:
  - `out/rocminfo-gdb/2026-03-29T21-59-30/gdb-hsa-flow.txt`
- initial debugger log with the same failure shape:
  - `out/rocminfo-gdb/2026-03-29T21-57-51/gdb-hsa-flow.txt`

## Narrowest safe reading

Under the failing latest-HSA environment:

- `rocminfo` resolves `libhsa-runtime64.so.1` from:
  - `artifacts/rocm-latest/lib-compat/libhsa-runtime64.so.1`
- `gdb` hits the first pending breakpoint at `hsa_init`
- `finish` returns from `hsa_init` with:
  - `hsa_init_return=4096`
- the process then reports:
  - `hsa api call failure ... rocminfo.cc:1329`
  - `HSA_STATUS_ERROR`
- the later enumeration breakpoints are not reached:
  - `hsa_iterate_agents`
  - `hsa_agent_get_info`

That supports one bounded conclusion:

- the latest-HSA `rocminfo` failure on this host is already present at HSA
  runtime initialization, not only later at agent iteration

## What this does not prove

This note does **not** yet prove:

- the internal ROCR/HSA reason inside `hsa_init`
- that torch usability is restored by fixing this one failure
- anything about GPU reset causality under WhisperX or Ollama

Those remain separate RCA lanes.

## Consequence for repo claims

The stronger current claim is:

- `rocminfo restored` and `torch usable` remain separate claims
- latest HSA breaks Polaris enumeration at or before `hsa_init`
- debugger-backed userspace RCA should stay separate from GPU reset / profiler
  RCA

## Next action

If deeper HSA internals are needed, extend the debugger lane further:

- keep the same failing latest-HSA surface
- capture more internal HSA call frames or symbolized library details inside
  `hsa_init`
- do not conflate that work with the `rocprofv3` reset-attribution lane
