# Failure Classification Surface

This repo keeps failure-class signals separate from claims so evidence can be remapped without changing control flow.

`schemas/execution_path_claim.schema.json` now includes a minimal optional
`failure_class` enum for bounded runtime/parity/tooling triage:

- `AUTHORITY` – authoritative runtime/platform fault surface (e.g., HSA/ROCm runtime ownership)
- `CONTRACT` – lane-contract boundary check failure
- `PARITY` – parity, mismatch, or reproducibility divergence signal
- `TOOL` – probe/tooling/runner failure rather than runtime workload failure
- `EVIDENCE` – missing, incomplete, or non-actionable evidence posture

The lane owner can map the same incident into this fixed set before promotion:

- runtime failures: `AUTHORITY`
- parity failures: `PARITY`
- tool failures: `TOOL`

Examples are in:

- `artifacts/execution_path_claims/examples/runtime-authority-rocminfo-failure.json`
- `artifacts/execution_path_claims/examples/parity-repro-divergence.json`
- `artifacts/execution_path_claims/examples/tool-runner-failure.json`

This is a non-breaking, schema-only extension and is intentionally not wired into
runtime control logic yet.
