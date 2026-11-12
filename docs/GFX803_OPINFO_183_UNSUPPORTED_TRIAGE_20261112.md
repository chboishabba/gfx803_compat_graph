# The 183 OpInfo "unsupported" cases: source-bound triage

The full 1,774-node original matrix is:
`/mnt/truenas/comet-net/experiments/gfx803_opinfo_full_20261111/matrix.json`
SHA-256 `47c7ed58d7b549abfc038b534faaaa9ecaf6ee2fc18b3ba55addebeed02b7e36`.

Reported: 1,583 pass; 183 unsupported; 3 ordinary fail; 4 GPU fault;
1 interruption; 0 unassayed.

**Critical interpretation:** the original long-lived worker emitted
`outcome: "skipped"`, and the supervisor mapped every such event to
`status: "unsupported"`. The worker did not retain
`pytest_runtest_logreport(...).longrepr`, `wasxfail`, or the skip
marker reason. Therefore, 183 unsupported rows are **183 pytest
skips/non-passes**, not evidence of 183 missing GPU implementations.
A skipped case may reflect upstream test policy, ROCm exclusion,
unsupported dtype/shape, explicit xfail, optional dependency, or another
reason; the historic receipt alone cannot distinguish them.

Run the new offline audit against the original unmodified matrix:

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
python3 scripts/gfx803_opinfo_unsupported_audit.py \
  --matrix /mnt/truenas/comet-net/experiments/gfx803_opinfo_full_20261111/matrix.json \
  --out /mnt/truenas/comet-net/experiments/gfx803_opinfo_unsupported_audit_20261112.json
```

The audit requires the exact matrix SHA and 1,774/183 universe,
groups results by generated test family and dtype, and retains
every original node ID. It makes no GPU calls or modifications to
the original evidence, and cannot claim a kernel is unsupported
without an actual reason. The generated audit is candidate-only.

**Next diagnostic cut:** inspect source skip/xfail markers for the
largest families, then collect actual reasons in a separate targeted
diagnostic run with the revised journal plugin. Do not automatically
force upstream skips to execute: a skip can guard an unsafe ROCm
kernel, an unsupported dtype, or an unavailable backend. Distinguish
`policy-disabled`, `kernel-absent`, `dtype/shape-excluded`,
`optional-dependency`, `expected-failure`, `fixture/setup`,
and `unresolved` only after reading the original reason.

New discovery journaling retains `skip_reason` and `wasxfail`
where pytest supplies them; the supervisor carries those fields into
future matrix receipts. Historic rows remain without a reason. No
claim of additional OpInfo passes, repaired functionality or
release admission follows from this classification.
