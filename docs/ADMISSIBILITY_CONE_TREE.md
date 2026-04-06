# Admissibility Cone And Tree

## Purpose

This repo needs a stricter boundary between:

- raw execution evidence
- candidate interpretations
- accepted compatibility claims
- public guidance and release projections

The nearby `ITIR-suite` and `dashi_agda` repos already contain the missing
patterns:

- `ITIR-suite` provides the admissibility-lattice doctrine: source/observation
  first, promotion as the only path to truth-bearing records, and projections
  as downstream artifacts rather than replacement truth.
- `dashi_agda` provides the canonical-vs-alternative-vs-validation discipline,
  plus an execution-admissibility bridge where a structural cone stays fixed
  while witness classes and boundary failures are made explicit.
- `zkperf` fits here as receipt-bearing execution material and compare/report
  infrastructure, not as the authority that decides truth in this repo.
- for GPU RCA, admissibility can sit below the app-stage level:
  - app stage (`transcribe`, `align`, `decode`)
  - exposure point (D2H copy, host wait, final sync, compositor fallout)
  - GPU execution path (pinned pages, HSA queue, VM mapping, DMA/copy path, kernel family, ring/reset path)
  - compositor interaction as a separate correlated surface, not automatically the root cause

## Core theorem

For `gfx803_compat_graph`, a run result becomes truth-bearing only through an
explicit promotion step. Raw traces, metrics, crash captures, and benchmark
rows are non-authoritative until they satisfy the repo's admissibility gates.

## Record lattice

```text
artifact root / source anchor
  < execution observation
  < candidate diagnosis or candidate compatibility claim
  < promoted compatibility record
  < user-facing projection / release guidance
```

This ordering is monotone:

- a trace bundle or benchmark row is evidence, not truth
- a ranking or heuristic is a candidate, not an accepted conclusion
- user-facing guidance must point back to promoted records and their evidence

## Canonical source anchors

Every admissibility decision should point back to a concrete source anchor such
as:

- artifact lane id
- runtime/lib bundle manifest
- exact script entrypoint
- workload identifier
- commit or extracted artifact revision
- environment tuple: host, kernel, GPU, ROCm lane, math/runtime lane

These are the substrate. They are not yet compatibility claims.

## Observation layer

This is where `zkperf` belongs.

Observation records may include:

- structured metrics
- stage timings
- compare-to-baseline deltas
- trace refs
- proof refs
- `amdgpu` reset and `devcoredump` refs
- host CPU hotspot refs
- output artifact refs

Observation records are admissible as evidence only. They are not allowed to
directly mutate the accepted compatibility map.

## Candidate layer

Candidate records should encode interpretations such as:

- `import_ok`
- `gpu_visible`
- `kernel_stable`
- `numerically_stable`
- `same_process_drift_present`
- `layout_sensitive_bug`
- `cpu_only_trustworthy`
- `negative_control`
- `exposure_point_copy_wait`
- `root_cause_class_queue_progress_loss`
- `root_cause_class_gpu_vm_or_pinned_page_failure`
- `root_cause_class_dma_or_copy_path_stall`

This layer is where heuristic ranking and graph mining belong.

## Promoted layer

A promoted record is the smallest truth-bearing statement the repo is willing
to stand behind, for example:

- `lane X imports torch on Polaris`
- `lane Y enumerates GPU but fails correctness gate for workload Z`
- `workaround W stabilizes probe tensor P but not end-to-end logits`
- `CPU is the only trustworthy output path for workload family F as of date D`
- `WhisperX can launch and use the GPU on lane X, but host-stable completion is not yet promoted because KFD/reset instability remains in play`

Promoted records must be immutable except by explicit supersession.

## Projection layer

Downstream projections include:

- README guidance
- user guide instructions
- ranked experiment plans
- release manifests
- community bundle summaries

These must never outrun the promoted layer.

## Admissibility cone

The cone is the ordered set of constraints that a claim must satisfy before it
can move upward. For this repo the useful first-pass cone is:

1. Provenance cone
   exact lane, exact workload, exact command, exact artifact refs exist
2. Reproducibility cone
   run can be repeated under the same anchor tuple
3. Isolation cone
   result survives negative controls or alternate formulations
4. Stability cone
   crash/reset behavior is classified, not conflated with correctness
5. Semantics cone
   the claimed meaning matches the measured surface
6. Promotion cone
   a bounded statement is safe to expose as accepted guidance

For lower-level GPU execution paths, "stability" should be read literally:

- no VM fault / ring-timeout / reset evidence: stronger admissibility
- VM fault or `init_user_pages` failure observed: reset-correlated but not stable
- reset plus VRAM loss: hard negative stability signal
- compositor fallout after reset: collateral display evidence unless a tighter causal path is proven

For GPU reset RCA, admissibility must also keep exposure point separate from
root-cause class:

- exposure point:
  - where the first externally visible stall or corruption appears
  - for example `hipMemcpyWithStream(... DeviceToHost ...)` followed by host wait
- sentinel:
  - earliest retained pre-crash marker that reliably precedes the hard failure
  - for the current WhisperX lane, `Host active wait ... for -1 ns`
- root-cause class:
  - the lower-level mechanism most likely responsible
  - for example queue-progress loss, GPU VM failure, pinned-page failure, or DMA/copy-path stall
- ownership hypothesis:
  - which subsystem or support boundary most likely owns the failing path
  - for example ROCm/amdgpu behavior on a weak-support architecture such as
    `gfx803` / Polaris

The repo may safely promote an exposure point before it can safely promote the
root-cause class. It must not silently collapse the two.
It may also promote a sentinel as a bounded operational marker before the
underlying mechanism is fully resolved.
If kernel evidence directly names a timeout class such as `ring gfx timeout`,
that failure class should outrank looser mechanism guesses.

For remediation planning, keep a patch-shape layer separate from both the
root-cause class and the individual knob level:

- patch-shape:
  - the intervention family that should move the current sentinels if the
    trigger model is correct
  - for example:
    - VM / mapping-pressure reduction
    - queue visibility / drain points
    - DMA / D2H completion-path relief
    - backend / kernel-path substitution
    - display-path isolation
- knob:
  - the concrete app, harness, env, or driver change used to instantiate a
    patch shape
  - for example:
    - chunked input
    - allocation reuse
    - `HIP_LAUNCH_BLOCKING=1`
    - explicit sync points
    - memory-copy trace off
    - alternate compute type

The repo may safely promote a patch shape as the current best intervention
family before it promotes any single knob as an accepted fix.

The key rule from `dashi_agda` is useful here: keep the structural cone fixed
when possible, and localize failures to the witness or boundary class rather
than redefining the whole geometry every time a test fails.

That principle now maps to a repo-local execution-path registry too:

- schema:
  - `schemas/execution_path_claim.schema.json`
- example records:
  - `artifacts/execution_path_claims/examples/`
- userspace-debug RCA and GPU-reset RCA remain separate fields inside each
  record rather than one blended crash verdict

For the current WhisperX lane, the layered object is now:

- confirmed failure class:
  - queue / ring forward-progress loss
- promoted exposure point:
  - D2H copy plus host wait
- promoted sentinel:
  - first `Host active wait ... for -1 ns`
- candidate trigger classes:
  - GPU VM / pinned-page / mapping failure
  - DMA / copy-path completion stall
- candidate ownership hypothesis:
  - ROCm/amdgpu instability on `gfx803` / Polaris
- candidate patch shapes:
  - reduce mapping pressure and allocation churn
  - add queue visibility / drain points
  - reduce or stage D2H contention
  - swap backend / precision / kernel mix
  - isolate display/compositor pressure as a secondary aggravator check
- implementation lanes:
  - baseline crash lane
  - queue/visibility lane
  - pressure-control lane
  - DMA-light lane
  - backend/compute lane

## Tree shape

The tree should separate structural decomposition from proof/evidence
decomposition.

### Logic tree

Use a deterministic logic tree for the claim structure:

```text
claim
  -> environment
  -> workload
  -> expected property
  -> admissibility gates
  -> promotion outcome
```

Example:

```text
Claim: "old-ABI lane is acceptable for torch bring-up"
  DEPENDS_ON environment: Polaris RX580 + old-ABI SDK root
  DEPENDS_ON workload: torch import smoke
  DEPENDS_ON property: imports without leaking latest /opt/rocm
  DEPENDS_ON gate: GPU visibility
  DEPENDS_ON gate: no mixed-soname resolution
  DEPENDS_ON gate: repeatability
```

Lower-level WhisperX example:

```text
Claim: "current long-file WhisperX crash boundary is copy/wait-adjacent"
  DEPENDS_ON environment: Polaris RX580 + extracted host runtime
  DEPENDS_ON workload: long-file WhisperX repro
  DEPENDS_ON property: final retained userspace operation is D2H copy followed by host wait
  DEPENDS_ON sentinel: first `Host active wait ... for -1 ns`
  DEPENDS_ON failure class: `ring gfx timeout`
  DEPENDS_ON gate: previous-boot kernel reset evidence
  DEPENDS_ON gate: no conflicting later retained userspace operation
  DOES_NOT_IMPLY root cause: copy overflow
```

### Proof tree

Use a proof tree for satisfied evidence only:

```text
promoted claim
  -> supporting observation
  -> supporting comparison
  -> supporting negative control
  -> supporting crash classification
```

Unsatisfied branches remain visible in the candidate layer, but they do not
enter the promoted proof tree.

## Witness classes

Borrow the `dashi_agda` labeling discipline:

- `canonical`: the current best-supported path for a claim
- `validation`: independent cross-check of the same claim
- `alternative`: different route that may still be admissible
- `experimental`: exploratory path not yet allowed to support repo-facing claims
- `negative_control`: intentionally failing or mismatch case

Applied here:

- canonical: current accepted smoke or benchmark route
- validation: alternate harness or same claim checked on another lane
- alternative: different workaround with comparable evidence
- experimental: exploratory runtime stacks and half-pinned rebuild attempts
- negative_control: known-bad latest-class or mismatch cases

## zkperf contract here

`zkperf` should provide a bounded observation contract, not the promotion
policy.

Minimum useful shape:

```json
{
  "observation_id": "string",
  "lane_id": "string",
  "workload_id": "string",
  "metrics": {},
  "trace_refs": [],
  "proof_refs": [],
  "related_artifact_refs": [],
  "verdicts": {
    "import_ok": false,
    "gpu_visible": false,
    "crash_free": false,
    "numerically_stable": false
  }
}
```

Rules:

- require `metrics`
- require at least one of `trace_refs` or `proof_refs`
- allow artifact refs only via stable ids
- forbid direct publication of repo-facing truth from this record alone

## Promotion gates for this repo

Before promoting a compatibility claim, require:

1. Anchor completeness
   lane/workload/command/artifact refs are present
2. Observation completeness
   metrics plus trace or proof refs exist
3. Boundary clarity
   crash, import, visibility, and correctness are not collapsed into one verdict
4. Control evidence
   at least one alternate or negative-control comparison exists for nontrivial claims
5. Exposure/root-cause separation
   if the evidence only identifies where the fault becomes visible, promote the
   exposure point only and keep lower-level cause as a candidate class
6. Sentinel clarity
   if a repeated pre-crash marker exists, record it explicitly as an operational
   boundary without overstating it as the root cause
7. Failure-class priority
   if the kernel or runtime directly reports a timeout or eviction class, keep
   that as the leading observed failure class and rank trigger hypotheses below it
8. Scope discipline
   claim is bounded to the tested workload family and lane

## Immediate use against current blockers

This would make the current struggles legible:

- ABI seam work becomes an admissibility problem about import, soname purity,
  and GPU visibility rather than a generic "upgrade failed" bucket.
- Leech nondeterminism becomes a tree with stable vs unstable tensor-path
  witnesses and a clear boundary between probe stabilization and end-to-end
  correctness.
- WhisperX RCA keeps its ROCm-specific capture stack while still exporting
  `zkperf`-like receipts for stage comparison and retention decisions.
- WhisperX crash RCA can now be stated as:
  - confirmed failure class: `ring gfx timeout` / queue forward-progress loss
  - promoted exposure point: copy/wait-adjacent crash boundary
  - promoted sentinel: first `Host active wait ... for -1 ns`
  - candidate trigger classes: GPU VM/pinned-page failure or DMA/copy-path stall
  - candidate ownership hypothesis: ROCm/amdgpu path on `gfx803` / Polaris
- README/user-guide claims can be generated only from promoted records instead
  of directly from benchmark rows or partial notes.

## First implementation slice

The smallest next step is:

1. define a machine-readable `ExecutionObservation` schema
2. define a `CompatibilityClaim` schema with promotion status
3. add witness labels: `canonical`, `validation`, `alternative`,
   `experimental`, `negative_control`
4. generate one logic tree and one proof tree for the old-ABI torch smoke lane
5. keep `zkperf` strictly as the receipt/comparison substrate below promotion

That is enough to turn this repo from "benchmark archive plus notes" into a
governed compatibility atlas.
