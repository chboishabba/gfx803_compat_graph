# T1.13–T1.14: exhaust all 219 CCOB member candidates offline

**14 November 2026 — source and tests committed, host acceptance pending.**

Starting evidence (commit 11223f6): 61/61 previous CPU-only
contracts passed; exact extracted gfx803 object SHA
3aacb81a0c571c10d842922935db1f248a59602746d0497f5aa383fad101a0c8.
Its AMDGPU MessagePack metadata decoded 336 kernels with **zero
TopK-name matches**. That is not proof against mbtopk: the CCOB
fatbin has 219 gfx803-target occurrences, and the one extracted
object is not an exhaustive per-translation-unit code-object
inventory.

## Execute the remaining multi-bundle audit, no GPU

~~~bash
set -euo pipefail
cd /mnt/truenas/comet-net/gfx803_compat_graph
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_gfx803_ccob_member_index.py' -v
python3 -m unittest discover -s tests -p 'test_gfx803_ccob_all_members.py' -v

PREV=/mnt/truenas/comet-net/experiments/gfx803_t105_k206_20261114_r2
OUT=/mnt/truenas/comet-net/experiments/gfx803_t113_t114_20261114
mkdir -p "$OUT"
FATBIN="$PREV/libtorch_hip_fatbin.bin"
RECEIPT=docs/receipts/gfx803_t105_t108_host_20261114/fatbin_container.json
BUNDLER=/nix/store/5dbvxcs7l4mvnj1cq3ybbkdm15jpvqr9-staged-rocm/core-10.1/lib/llvm/bin/clang-offload-bundler

python3 scripts/gfx803_ccob_member_index.py \
  --fatbin "$FATBIN" --container-receipt "$RECEIPT" \
  --out "$OUT/ccob_member_index.json"

python3 scripts/gfx803_ccob_all_members_topk.py \
  --fatbin "$FATBIN" \
  --index-receipt "$OUT/ccob_member_index.json" \
  --bundler "$BUNDLER" \
  --out "$OUT/all_member_topk_inventory.json"
~~~

The indexer **does not search inside compressed payload for the
next CCOB magic**. It trusts each v3 member's authoritative
Total File Size and checks only a bounded inter-member padding
region for the next valid header. This matters because a payload
can legitimately contain the literal bytes CCOB.

The batch analyzer verifies each member SHA, runs the installed
bundler on *each individual compressed member* and decodes its
AMDGPU note metadata. It extracts into a temporary directory and
retains only JSON: member index, target IDs, compressed-member SHA,
unbundled code-object SHA, metadata-kernel counts and any readable
TopK-name matches. It checkpoints results after each member.
No HIP runtime is imported or invoked, and no GPU workload is run.

If one member fails to unbundle, its status is recorded; that
member must not be counted as a negative TopK result. The completed
receipt must account for **all indexed members**, rather than
silently reporting a partial subset as exhaustive. If the header
index count differs from the 219 target occurrences, inspect the
alignment and file boundaries rather than forcing an equality.

## Follow-up if there are TopK-named kernel descriptors

Inspect the exact member index and kernel descriptors first. Then
use the existing metadata/ISA tools with that member's exact
extracted object and its own SHA receipt. Do not substitute the
previous aggregate 5.25 MB object for a different member.

Even if all member objects contain no readable TopK name, record
that as absence of **readable names**, not absence of inlined,
renamed, linked or runtime-generated TopK kernels. T1.06 requires
original source-to-binary build provenance; T1.07 requires actual
incident kernel dispatch evidence. Neither is closed by static
metadata alone.

## Required receipt handoff

Share or commit the small:
- ccob_member_index.json
- all_member_topk_inventory.json

Do not commit 42.9 MB CCOB, per-member extracts, or 5.25 MB HSACO.
Keep K2.05 historical fence errno OPEN, T1.07 incident kernel OPEN,
and F1/release BLOCKED until corresponding evidence is acquired.

Background: LLVM Clang offload-bundle format explicitly supports
concatenated compressed bundles. Header length is authoritative
on v2/v3; literal magic scanning inside payload was a known bug.
Reference: https://clang.llvm.org/docs/ClangOffloadBundler.html
