# OpInfo Fast Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the remaining pinned OpInfo corpus without paying PyTorch/HIP process startup for every individual node, while retaining fault attribution.

**Architecture:** Keep the existing per-node runner as the forensic lane. Add a long-lived discovery worker that fsyncs a start/result journal for every ordered node. On a hard fault the worker ends; the current durable node is recorded as a candidate and a fresh worker starts at the following unassayed node after health inspection. Replay candidates later in isolation.

**Tech Stack:** Python 3, pytest/JUnit XML, existing immutable Nix Python wrapper, ROCm gfx803 runtime.

**Spec:** User instruction, 2026-11-12: amortize Torch setup; use fresh-process bisection only after a fault.

## Global Constraints

- Preserve all 1,774 source-bound node identities and existing matrix receipts.
- Do not create a venv, Docker environment, or alter the immutable Nix runtime.
- Never treat a batched pass as release admission; retain `gpu_validated=false` and `release_admitted=false`.
- A new GPU fault must stop before continuing until the health probe succeeds and its exact node set is acknowledged.

## Review Focus

- A JUnit record that does not map uniquely to an input node must remain unassayed, not passed.
- A crashed batch may contain completed nodes; preserve only XML-backed outcomes and leave unknown nodes unassayed.
- A later fault must not inherit acknowledgement for an earlier fault.
- Batch command argument limits must cap chunk size deterministically.
- Existing per-node resume behavior must remain unchanged by default.

### Task 1: Batch evidence parser and range model

**Files:**
- Modify: `scripts/gfx803_opinfo_full_sweep.py`
- Test: `tests/test_gfx803_opinfo_full_sweep.py`

**Interfaces:**
- Produces `run_batch(nodes, ...) -> BatchResult` with per-node XML-backed outcomes and an unresolved ordered suffix.

- [ ] Write tests for complete JUnit pass/skip parsing, unmapped records, and a partial crash result.
- [ ] Implement bounded command construction, JUnit parsing, and durable batch evidence files.
- [ ] Verify focused contracts pass.
- [ ] Commit the parser.

### Task 2: Fast sweep and forensic split control flow

**Files:**
- Modify: `scripts/gfx803_opinfo_full_sweep.py`
- Modify: `tests/test_gfx803_opinfo_full_sweep.py`
- Modify: `docs/GFX803_OPINFO_FULL_SWEEP_20261111.md`

**Interfaces:**
- Adds `--worker-size` (default `1`) and `--forensic-worker-size 1` behavior.

- [ ] Write tests proving clean batches mark only reported nodes, and non-clean batches retain unresolved nodes for fresh replay.
- [ ] Implement batch execution with the existing per-node lane as the fallback/forensic lane.
- [ ] Update the runbook with the receipt distinction between batched and isolated evidence.
- [ ] Run the full offline suite and commit.

### Task 3: Hardware resumption

**Files:**
- Create: a new NAS experiment receipt directory; do not rewrite the existing matrix.

- [ ] Run the post-fault GPU health probe and retain kernel-log evidence.
- [ ] Start the remaining corpus with `--worker-size 64` under the existing user-service supervisor.
- [ ] On a non-clean chunk, preserve its receipt and perform fresh-worker split/replay before continuing.
- [ ] Report counts by evidence lane and do not promote the runtime.

