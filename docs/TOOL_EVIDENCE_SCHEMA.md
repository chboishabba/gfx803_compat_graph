# ToolEvidence Schema Contract

## Purpose

`ToolEvidence` records are passive inputs from MCPs, probes, and test tools.
They are admissibility-facing evidence only and must not be used to alter control flow.

## Canonical Schema

`schemas/tool_evidence.schema.json`

## Required fields

- `source`: object identity for the originating tool
  - `name` (required): stable name for the tool/collector
  - `type` (required): one of `mcp`, `script`, `probe`, `manual`
  - `endpoint` and `schema_version` are optional metadata
- `timestamp`: ISO-8601 `date-time` capture time
- `payload`: free-form evidence body from the tool, consumed only as data
- `confidence`: numeric score in `[0, 1]`

## Boundary rules for this lane

1. ToolEvidence is input-only evidence and must never mutate decision state.
2. ToolEvidence cannot change or edit any `DecisionPacket`.
3. ToolEvidence cannot trigger routing, approvals, or branch selection.
4. ToolEvidence may only feed downstream summarization or scoring.
5. ToolEvidence does not create controls and does not define fallback/kill actions.

## Notes

- The schema is intentionally minimal and permissive in `payload` to preserve collector compatibility.
- Consumers should enforce stricter interpretation when mapping to higher-level claims.
- `ContextPackage` extension is optional and only through a distinct higher-level envelope; this contract itself only defines raw tool evidence.
