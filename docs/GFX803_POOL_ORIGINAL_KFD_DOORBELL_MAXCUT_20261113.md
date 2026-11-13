# gfx803 MIOpen historical pooling page fault — maximum-cut diagnostic

## Evidence state (13 Nov 2026)

- Original Schaka MIOpen sweep, 23 entries: 18 pass; two no
  applicable solver shapes; `pool_sweep` GPU page-not-present;
  `activ_sweep` OOM; groupnorm two intentionally rejected
  negative-control shapes conservatively recorded failed.
- Original pooling shape/mode source: 42 cases from Schaka pin
  `8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78`.
- Fresh per-case derived processes: 42/42 numerical passes, no
  page fault. Prefixes 1,2,4,8,14,16,21,28,35,42 all pass,
  including one process with all original 42 calls.
- This **refutes a deterministic single-case or simple prefix-length
  failure in the tested circumstances**; it does NOT refute an
  intermittent fault, preceding-GPU-tenant interaction or a
  changed binary/loader environment.

## Historical kernel diagnosis that must be retained

June 25 2025 Alex Deucher authored
`drm/amdkfd: add hqd_sdma_get_doorbell callbacks for gfx7/8`,
commit `34659c1a1f4fd4c148ab13e13b11fd64df01ffcd`.
Reported by the RX 580 investigator following KFD/SDMA reset
regressions. The callback fix prevented a missing gfx7/8 callback
under unconditional per-SDMA queue-reset handling.

A separate gfx7/8 validation fix, commit
`542c3bb836733a1325874310d54d25b4907ed10e`, handles
older GFX7/8 AQL ring buffers that are backed by half-sized BOs and
mapped in two pieces. **Neither patch proves the present
host kernel includes it**, nor that the historical pooling fault
arose from the same defect.

A kernel NULL callback/Oops during queue reset and a GPU VM
page-not-present caused by userspace work are different mechanisms.
Correlate raw kernel logs before attributing either.

Primary sources:
- https://www.mail-archive.com/amd-gfx@lists.freedesktop.org/msg125108.html
- https://git.zx2c4.com/linux-rng/commit/?id=542c3bb836733a1325874310d54d25b4907ed10e
- https://rocm.docs.amd.com/en/docs-10.1.0/reference/environment-variables/index.html
- https://rocm.docs.amd.com/projects/MIOpen/en/latest/doxygen/html/group__pooling.html

## P0: original-binary provenance; no GPU

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
git pull --ff-only
python3 -m unittest discover -s tests -p test_gfx803_pool_original_runtime_matrix.py -v

OLD=/mnt/truenas/comet-net/experiments/gfx803_schaka_miopen_20261113
OUT=/mnt/truenas/comet-net/experiments/gfx803_pool_original_runtime_20261113

python3 scripts/gfx803_pool_original_runtime_matrix.py \
  --build-receipt "$OLD/build.json" --out "$OUT"
```

The tool requires the original source SHA, original built
`pool_sweep` binary SHA-256 and selected staged ROCm prefix.
**Unlike the prefix derivative, this runs the actual originally
compiled 42-case binary**. No rebuild, source mutation or driver
changes. `--execute` is required to initiate GPU work.

Run independent read-only KFD historical audit:

```bash
python3 scripts/gfx803_kfd_doorbell_audit.py \
  --out /mnt/truenas/comet-net/experiments/gfx803_kfd_doorbell_20261113 \
  --since '2026-11-13 00:00:00'
```

This inventories current kernel release/vermagic, observed KFD,
SDMA, doorbell, queue reset and VM fault messages. It *cannot*
establish whether an arbitrary distro kernel backported the
historical callback. If the exact running-kernel source tree is
available, provide `--kernel-source /SOURCE/TREE` for a read-only
source callback check, but independently verify build provenance.
Do not equate `journalctl` permission failure with zero faults.

## P1: sequential experiments, one GPU child each

Ensure a healthy, idle RX 580, no conflicting OpInfo/TopK/C2
training tenant. After the original historical fault, inspect
`journalctl -k` and verify /dev/kfd queue progress before
running new tests; a fresh Python process alone does not reset
KFD hardware state.

```bash
python3 scripts/gfx803_pool_original_runtime_matrix.py \
  --build-receipt "$OLD/build.json" --out "$OUT" \
  --resume --execute --batch-size 1 --timeout 180
```

Repeat if each stage passes. The runner executes, in order:

1. `baseline`: exact unmodified binary in ordinary HIP/HSA settings.
2. `serialize`: `AMD_SERIALIZE_KERNEL=3`, `AMD_SERIALIZE_COPY=3`;
   tests synchronization/async scheduling sensitivity.
3. `fragment-off`: `HSA_DISABLE_FRAGMENT_ALLOCATOR=1`;
   tests fragment caching sensitivity.
4. `sdma-off`: `HSA_ENABLE_SDMA=0`; tests involvement of
   SDMA copy-path activity. **Not a callback/doorbell fix**.
5. `irq-poll`: `HSA_ENABLE_INTERRUPT=0`; tests signal polling
   versus interrupt-driven completion, not kernel patch presence.
6. `logging`: `AMD_LOG_LEVEL=4`, MIOpen logging; gathers
   extra runtime trace at potential performance/timing cost.

Every child gets fresh process identity, same original binary,
LD_PRELOAD cleared, selected ROCm library path preferred, and
an explicit control-variable override. The raw inherited
LD_LIBRARY_PATH is recorded as a confounder. The runner captures
stdout/stderr SHA-256, periodic accessible `/proc/PID/maps` snapshots
and kernel journal messages from immediately before the run.

The executable is considered a pass ONLY if return code is 0
and one **exact 42-case zero-WRONG summary** is present. All
failed/missing-summary/fault/timeout outcomes halt the sweep.
No automatic retry or GPU reset occurs; use a fresh experiment
directory after health inspection.

## P2: comparison interpretation

* If the baseline faults: STOP. Inspect its logs and kernel
  messages before proceeding. Do not automatically run the
  serialized configuration against a tainted queue.
* If the baseline passes and controlled variants pass: the
  original fault remains unreplicated, not repaired. Preserve
  original full sweep/isolated/prefix/control receipts.
* If a different control changes reproducibility: only under
  repeated, matched **A/B/A/B or A/B/B/A** independent runs
  does that provide strong attribution. A single fault versus
  pass is insufficient.
* If only the full 23-entry MIOpen run faults while the exact
  42-case binary and derived prefixes pass: test upstream
  cross-sweep GPU state/tenant order and MIOpen cache lifecycle
  separately; do not alter pool solver tile math.
* If kernel journal reports a CPU Oops involving
  `hqd_sdma_get_doorbell` or a per-queue SDMA reset: evaluate
  running kernel callback/source backport provenance.
  If GPU page-not-present without CPU Oops, prioritize
  unmapped GPU VA, page tables, queue teardown, allocator,
  kernel argument and async dispatch diagnostics.
* If evidence points to the original pooling workspace:
  MIOpen's `miopenPoolingForward` documentation requires
  `workSpace=nullptr, workSpaceSize=0` when
  `do_backward=false`. The original source sets
  `do_backward=true` and allocates workspace. A future
  **separate** forward-only diagnostic derivative should
  change both parameters together, never partially.

## Exact open gates

- Current host kernel source-to-binary provenance for two
  gfx7/gfx8 KFD fixes — OPEN.
- One independently reproduced original-binary GPU fault
  with kernel logs + library map identity — OPEN.
- Repeatable A/B controls discriminating asynchronous
  scheduling, HSA fragment caching, SDMA and interrupts — OPEN.
- MIOpen selected kernel/solver and page-faulting GPU VA
  ownership — OPEN.
- Cross-sweep cumulative host pressure and activation OOM — OPEN.
- GroupNorm expected negative-control classification weld — OPEN.
- Exact upstream causal patch, independent unit tests and
  clean-client closure validation — OPEN.

No code or documentation here claims the historical fault
is already fixed or proves it was a doorbell regression.


## P3: separate forward-only pooling workspace control

A new diagnostic `scripts/gfx803_pool_forward_only_control.py`
retains the exact Schaka original `run_one` and all 42 input cases,
but surgically replaces the single workspace setup and the
`miopenPoolingForward(..., do_backward=true, workspace, size)`
call with the **documented forward-only** alternative:
`do_backward=false, workspace=nullptr, size=0`.
It does not change the MIOpen kernel, numerical CPU reference,
case order or original acceptance binary.

This is a different *semantics/dispatch* condition, so a pass
is not directly interchangeable with the original backward-ready
suite result. Only run after an independently healthy GPU check,
and preserve a distinct destination:

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
OLD=/mnt/truenas/comet-net/experiments/gfx803_schaka_miopen_20261113
FWD=/mnt/truenas/comet-net/experiments/gfx803_pool_forward_only_20261113

python3 -m unittest discover -s tests \
  -p test_gfx803_pool_forward_only_control.py -v

python3 scripts/gfx803_pool_forward_only_control.py \
  --build-receipt "$OLD/build.json" \
  --out "$FWD" --build

# Explicit single fresh-process GPU run, no repeat or automatic reset:
python3 scripts/gfx803_pool_forward_only_control.py \
  --build-receipt "$OLD/build.json" \
  --out "$FWD" --execute --timeout 180
```

Compare the original binary baseline with this derivative
only under matched healthy starting state and the same
staged runtime, not by claiming the forward-only switch fixed
a GPU page fault.


## P4: strict provenance join — no false repair claim

After obtaining the complete prefix and single-case receipts, the
joiner can already record the established constraints. Once new
runtime and kernel audits exist, include them as well:

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
python3 -m unittest discover -s tests -p 'test_gfx803_pool_fault_evidence_join.py' -v

ISO=/mnt/truenas/comet-net/experiments/gfx803_pool_isolation_20261113_v3/matrix.json
SEQ=/mnt/truenas/comet-net/experiments/gfx803_pool_prefix_20261113/matrix.json
OLD=/mnt/truenas/comet-net/experiments/gfx803_schaka_miopen_20261113/matrix.json
CTL=/mnt/truenas/comet-net/experiments/gfx803_pool_original_runtime_20261113/matrix.json
KFD=/mnt/truenas/comet-net/experiments/gfx803_kfd_doorbell_20261113/matrix.json

python3 scripts/gfx803_pool_fault_evidence_join.py \
  --isolated "$ISO" --prefix "$SEQ" --original "$OLD" \
  --controls "$CTL" --kfd "$KFD" \
  --out /mnt/truenas/comet-net/experiments/gfx803_pool_fault_causal_audit_20261113.json
```

Omit `--controls` or `--kfd` until that exact original receipt
exists. The join verifies the source hash, staged runtime and
42/42 plus 10/10 tests, and fails on missing/failed items.
The report explicitly leaves cumulative-state causality,
running-kernel doorbell callback presence, whole-MIOpen
coverage and release admission **unproven**.
