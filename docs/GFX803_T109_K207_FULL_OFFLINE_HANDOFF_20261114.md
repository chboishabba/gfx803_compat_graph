# T1.09–T1.12 / K2.07–K2.08 — offline execution and acceptance

14 November 2026. Code committed, but this new stage is not yet
physically run on the RX580 host.

## Grounded starting point

- Incident journal integrity and AMDGPU module identity verified.
- Linux v7.3 reference GFX8 non-MES eviction reaches
  evict_process_queues_cpsch -> unmap_queues_cpsch ->
  amdkfd_fence_wait_timeout. Original errno and exact CachyOS
  source equivalence are still missing.
- Retained pre-review source routes both original TopK shapes to
  mbtopk. Historic source-to-loaded-wheel mapping is not proven.
- Extracted 5,246,152-byte gfx803 HSACO SHA:
  3aacb81a0c571c10d842922935db1f248a59602746d0497f5aa383fad101a0c8.
  A target bundle contains kernels, but inclusion is not execution.
- The four original JSON receipts are under
  docs/receipts/gfx803_t105_t108_host_20261114/.
- 33/33 previous offline tests passed. These NEW scripts require
  host acceptance before assigning pass counts.

## Run the entire read-only package

No root, HIP import, GPU execution, kernel probe attachment,
device reset, source download or vendor patch.

~~~bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
git pull --ff-only
bash scripts/run_gfx803_t109_k207_offline.sh \
  /mnt/truenas/comet-net/experiments/gfx803_t109_k207_20261114
~~~

Output directory must not exist; this is deliberate fail-closed
evidence preservation. The runner uses the retained original
TensorTopK.hip and extracted gfx803.hsaco paths from previous
handoffs. Override TOPK_SOURCE, TOPK_BASE or HSACO only if those
same exact original artifacts have moved.

Required: Python 3.10+ and readelf. Optional: llvm-readobj for
more code-object metadata. Unsupported LLVM options are recorded
rather than being treated as proof.

Optionally provide KFD_SOURCE_DQM and KFD_SOURCE_GPUVM environment
variables pointing to already present targeted kernel source C
files. This does not fetch the full kernel tree or assert their
exact match to incident CachyOS.

## Produced files

| Output | Meaning |
| --- | --- |
| hsaco_metadata.json | Exact ELF SHA, e_machine 224, notes/symbols and available LLVM metadata |
| amdgpu_msgpack_notes.json | Bounded PT_NOTE MessagePack kernel descriptors, if present |
| kernel_disasm_inventory.json | Verified candidate symbol list, no ISA disassembly until explicit selection |
| mbtopk_retained_source.json | Original source SHA, source function and launch-expression evidence |
| safehost_trace_qualification.json | Future separate-host checklist; defaults NOT READY |
| kfd_nonmes_safehost_trace.bt | Inert generated bpftrace source; NEVER automatically attached |
| kfd_nonmes_source.json | Optional targeted source logsite/fence branch evidence |
| t109_k207_final_join.json | Identity-welded evidence gates; historical dispatch/errno remain unknown |

All outputs are offline. Do not commit full ELF, fatbin, host secrets,
or bulky metadata unnecessarily. Share small curated JSON evidence.

## Optional kernel-specific ISA disassembly

After inspecting amdgpu_msgpack_notes.json, choose a real kernel
symbol from the decoded metadata. Do not guess a name.
Only then run:

~~~bash
python3 scripts/gfx803_mbtopk_kernel_disasm.py \
  --hsaco /mnt/truenas/comet-net/experiments/gfx803_t108_offload_20261114/gfx803.hsaco \
  --note-metadata /mnt/truenas/comet-net/experiments/gfx803_t109_k207_20261114/amdgpu_msgpack_notes.json \
  --kernel 'EXACT_SYMBOL_FROM_METADATA' \
  --out /mnt/truenas/comet-net/experiments/gfx803_t109_k207_20261114/selected_kernel_disasm.json
~~~

The ISA tool verifies the object SHA and the symbol's presence
before offline llvm-objdump. It counts waits/barriers/atomics/
global memory instructions, without inferring a causal defect.

## Gates remaining after a successful offline run

| Gate | Status and next evidence |
| --- | --- |
| T1.09 | Static HSACO metadata: test and inspect |
| T1.10 | Retained source SHA and launch expression audit: test |
| T1.11 | Pure Python AMDGPU MessagePack note decoding: test |
| T1.12 | Optional exact named-kernel offline ISA inventory |
| T1.06 | Original source -> compiled ELF -> benchmark process linkage OPEN |
| T1.07 | Actual original kernel/HSACO dispatch and first stall OPEN |
| K2.07 | Exact CachyOS source and non-MES fence return path OPEN |
| K2.05 | Original missing KFD eviction/fence error code OPEN |
| K2.08 | Dedicated recoverable non-display host trace not authorized/executed |
| J1/F1 | Causal join and minimal repair blocked |
| Release | GPU/Wayland recovery and full clean Nix/Cachix qualification blocked |

The original kernel dispatch and KFD internal return were not
retained. A completed static analysis cannot reconstruct missing
runtime information. Never claim those causal gates closed merely
because the tools pass.

## Safety

Do not rerun the crashing float32 [32,151936], k=50 workload on
the sole RX580 display GPU; no GPU fault injection, tracefs
attachment, firmware/device reset or kernel patch on this host.
Keep forensic scripts and AI-work documents out of Schaka PR #8.
