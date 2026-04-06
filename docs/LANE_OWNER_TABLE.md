# Lane Owner Table

## Purpose

This table makes runtime and diagnostic ownership explicit so:

- one lane can be delegated to one agent
- claims do not drift across lanes
- repo-facing guidance can be promoted from bounded lane claims only

This document works with:

- [ADMISSIBILITY_CONE_TREE.md](/home/c/Documents/code/__OTHER/gfx803_compat_graph/docs/ADMISSIBILITY_CONE_TREE.md)
- `schemas/execution_observation.schema.json`
- `schemas/compatibility_claim.schema.json`

## Lane Registry

| lane_id | witness_label | owner_scope | strongest safe claim today | main blocker | next action |
| --- | --- | --- | --- | --- | --- |
| `control-6.4` | `canonical` | Extracted `ROCm 6.4` host baseline for torch import, ComfyUI, and general userspace bring-up | Baseline host path is admissible for torch import / GPU visibility and broader userspace availability claims on this machine | WhisperX can use the GPU but can still hit KFD / reset instability at an unknown point, so it is not yet part of the promoted stable baseline | Materialize one promoted baseline claim that explicitly excludes WhisperX host-stability, Ollama host safety, and Leech correctness |
| `upgrade-oldabi` | `experimental` | `6.4`-derived old-ABI upgrade and framework rebuild lane | Old-ABI lane is the main promotion candidate for a newer reproducible stack | GPU visibility and framework rebuild gates are not yet promoted | Materialize one lane claim for old-ABI runtime purity and torch smoke gating |
| `diag-5.7` | `validation` | Extracted `ROCm 5.7` comparison and correctness investigation lane | `5.7` is admissible for comparison and upstream debugging, not for trustworthy inference output | Leech output remains nondeterministic / not trustworthy | Materialize one lane claim that classifies `5.7` as diagnostic-only for Leech correctness work |
| `diag-latest-hybrid` | `negative_control` | Pure latest-class and HSA-hybrid ABI seam investigation lane | These lanes are useful for ABI/device-gating diagnosis only | HIP/HSA ABI seam still blocks a promoted usable stack | Materialize one lane claim that pins diagnostic-only status and separates `rocminfo` restoration from torch usability |
| `ollama-ref` | `experimental` | Extracted host-port of the Robert `6.4.3_0.11.5` Ollama lineage | Reference bundle exists and is provenance-bearing, but is not a safe host daily-driver recommendation | Host reset/system instability remains unresolved | Materialize one lane claim that preserves container fallback as the only safe GPU-Ollama recommendation |

## Promotion Rule

Each lane may promote repo-facing guidance only through a
`CompatibilityClaim` record that:

- points to at least one `ExecutionObservation`
- carries bounded scope
- names one witness label
- records one explicit blocker when not promoted

## Lane Ownership Contract

One lane owner must report only on:

1. the lane's current admissibility status
2. the strongest safe claim
3. the main blocker
4. exactly one next action

Lane owners must not:

- widen claims into adjacent lanes
- merge crash, correctness, and visibility into one verdict
- promote prose alone without an observation/claim artifact
