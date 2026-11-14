# K2.05 / T1 integrated offline implementation runbook

14 November 2026. The scripts are source-written; neither local TrueNAS execution nor a new GPU result is claimed.

## One-run CPU-only preflight

Run from the existing checkout on the RX 580 host:

~~~bash
set -euo pipefail
cd /mnt/truenas/comet-net/gfx803_compat_graph
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_gfx803_kfd_topk_offline_cut.py' -v
OUT=/mnt/truenas/comet-net/experiments/gfx803_k205_t1_static_20261114
mkdir -p "$OUT"
J=docs/receipts/gfx803_topk_pr8_review_safe_20261114/kernel-previous-boot.log
H=docs/receipts/gfx803_kfd_kernel_source_handoff_20261114.json
python3 scripts/gfx803_kfd_incident_offline_audit.py --journal "$J" --handoff "$H" --out "$OUT/incident_static.json"
python3 scripts/gfx803_kfd_trace_boundary.py --out "$OUT/kprobe_inventory.json"
~~~

These tools do not execute HIP or trigger a kernel reset. The incident audit verifies the journal SHA against the committed handoff and fails closed on mismatch. The output separates current-boot parameters from incident-time unknowns, preserving all first logged events. If the incident boot is still available in journald, supply its *verified* boot ID with --historical-boot; do not guess -1.

## Original cached TopK wheel/overlay static inspection

~~~bash
# Select the original cached wheel or a directory containing torch/lib/*.so.
OLD_TORCH=/ABSOLUTE/EXISTING/PATH/TO/OLD-TORCH-WHEEL.whl
python3 scripts/gfx803_topk_binary_offline_audit.py --torch "$OLD_TORCH" --out "$OUT/topk_static.json"
~~~

Previously observed candidate overlay (must confirm it is actually the benchmark-loaded torch):

~~~bash
OLD_TORCH=/mnt/truenas/comet-net/.gfx803-schaka-101-work/out/pytorch-topk-gfx803-20261109/python-overlay-r2
python3 scripts/gfx803_topk_binary_offline_audit.py --torch "$OLD_TORCH" --out "$OUT/topk_static.json"
~~~

Optional --source /EXACT/TensorTopK.cpp and repeatable --code-object /EXISTING/HASCO/ELF give additional source/binary hashes and string inventory. String presence does NOT prove which GPU kernel was dispatched. The audit records minimum allocation sizes for passing [1,151936] and hanging [32,151936] shapes, omitting unknown workspaces and hardware registers/LDS.

The output paths deliberately refuse overwriting existing evidence. Use a new output directory when rerunning.

## Probe readiness and explicitly bounded optional tracing

The default kprobe inventory is CPU-only/read-only. It checks actual kernel kallsyms and source-level entry/return names for: evict_process_queues_cpsch, unmap_queues_cpsch, remove_queue_mes_on_reset_option (including compiler-suffixed symbol) and reset_queues_mes. Ambiguous or missing symbols are rejected.

Only if the operator accepts temporary tracefs writes (not a destructive GPU workload):

~~~bash
sudo python3 scripts/gfx803_kfd_trace_boundary.py \
  --out "$OUT/kprobe_idle_10s.json" \
  --seconds 10 --arm --ack-tracefs-writes
~~~

This arms scoped entry and return kprobes, waits 10 seconds, captures records with the gfx803k2 prefix and removes its own probes in a finally block. **It does not initiate any GPU workload.** Root privileges, tracefs availability and precise probe symbols are required. Unexpected termination may leave stale probes; use:

~~~bash
sudo python3 scripts/gfx803_kfd_trace_boundary.py --out "$OUT/kprobe_cleanup.json" --cleanup
~~~

Do not combine the tracer with the known crashing TopK input on the display GPU. Zero events during idle do not show either branch is impossible. A post-reboot event also does not prove historical incident-time invocation.

## Interpret only grounded outcomes

| Evidence | Allowed conclusion |
| --- | --- |
| Postboot uni_mes=1 | v7.3 reference chooses MES under those settings, not incident-time proof |
| Historical unsuccessful queues preemption message | Favors v7.3 non-MES fence timeout branch; remains conditional until exact source/state |
| Both compiled call targets | Branch availability, not which one ran |
| Successful original journal SHA | Integrity of retained journal, not completeness of GPU trace |
| Postboot trace records MES or non-MES | Actual branch at *time of trace*, not historical incident |
| Wheel/shared-object SHA + case byte bounds | Static provenance and lower-bound resource scaling, not selected HSACO |
| No matching symbols or historical state | Unknown. Do not patch on speculation |

## Deliverables and acceptance

- incident_static.json: original journal integrity and first-error chronology
- kprobe_inventory.json: observable entry/return probe inventory
- topk_static.json: original torch source/wheel/ELF and resource evidence
- optional kprobe_idle_10s.json: bounded postboot observational trace with scope limitations

**K2.05 remains OPEN** until actual incident-time branch/return is evidenced, or a properly scoped safe-host reproduction captures the equivalent failure. **T1 remains OPEN** until actual crashing TopK kernel/code object is identified. Exact CachyOS source-package matching, reviewed-wheel paired benchmarks and KFD recovery safety remain separate gates.

Next max-cut after running all offline receipts: map exact branch predicate to incident-time state; determine actual TopK HSACO and kernel selection; design a *recoverable non-display host* repro if archived evidence cannot answer; patch only proven causes.

These scripts and reports belong in gfx803_compat_graph. They must not be introduced into Schaka PR #8, per maintainer instructions.


## Phase D: one-command evidence join (CPU only)

After the three offline receipts exist, validate provenance and export
explicit open/blocked acceptance gates:

~~~bash
python3 scripts/gfx803_kfd_topk_evidence_join.py \
  --incident "$OUT/incident_static.json" \
  --trace "$OUT/kprobe_inventory.json" \
  --topk "$OUT/topk_static.json" \
  --handoff "$H" \
  --out "$OUT/join.json"
~~~

It rejects mismatched original journal SHA, incorrect data modes and
overwriting. It never infers historical MES/non-MES selection from
postboot arguments, or initial TopK kernel from static ELF strings.
It preserves K2.05 and T1 OPEN and release BLOCKED until additional
actual evidence is obtained. Review all original receipts, not just
the joined verdict.

**Known limitations requiring later work:** no CPU vmcore or retained
GPU coredump was available from the rebooted incident; no exact
CachyOS source-package/DWARF match; the tracefs probe script does
not recover 14 November incident-time registers; static source/
ELF search is not HSACO dispatch attribution; tracefs instrumentation
can perturb timing and must never be combined with the known
display-wedging TopK input on this host.

These are independent artifacts, not a GPU validation or source
patch. Do not post local scripts to Schaka PR #8.
