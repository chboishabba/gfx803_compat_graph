# Schaka ROCm 10.1: resolve published image → Nix candidate → original LILA A/B

**6 November 2026. Source-written, no physical import or on-card 10.1 result claimed.**

The actual original gfx803 6.4 receipts already established that replacing FP32
GPU linear operators with CPU GEMM did **not** repair the entire transformer:
layer-1 input max error 1.947485, dense logits 13.887831, and substantial
GPU-only repeated-forward drift. A separately traced WGM1 solution (537657384)
ran three times but still entered QKV with input bytes unequal to the standalone
fixture; dense logits 13.888970. This is evidence of an **earlier model-path
failure**, not evidence that Schaka's later 10.1 SGEMM replacement works or fails.

## Phase 1 — identify an immutable upstream 10.1 image without building

Work from the existing **gfx803_compat_graph PR #5** checkout:

```bash
cd /mnt/truenas/comet-net/gfx803_compat_graph
git fetch origin
git switch feat/gfx803-nix-binary-factory-20261104
git pull --ff-only

nix develop .#gfx803-oci-build -c bash \
  scripts/bootstrap-schaka-101-candidate.sh \
  --inspect-only --out out/schaka-oci/inspect-101-first
```

This uses Schaka's **release tag**
`ghcr.io/schaka/rocm-migraphx-ort-torch-builder:rocm10.1-gfx803`,
resolves it to `sha256:<64>`, and checks the publisher's original
source-revision, ROCm line, final stage, full eight-SHA dependency pin graph
and required shim preload. **If the current image label has moved past
the checked-in Schaka revision, the script fails rather than pretending
the old source lock identifies the new image.** Review the changed
`nix/gfx803/upstream.json` SHA in its own PR before proceeding.

Do **not** use the floating `latest-gfx803` tag for a reproducible test,
copy 10.1 .so files into `lib-compat`, or run 10.1 torch with the 6.4
`host-docker-python.sh`.

## Phase 2 — actual binary import (not compiling Schaka ROCm)

```bash
nix develop .#gfx803-oci-build -c bash \
  scripts/bootstrap-schaka-101-candidate.sh \
  --out out/schaka-oci/import-101-first
cat out/schaka-oci/import-101-first/candidate-runtime-selector.json
```

Uses the immutable inspected digest for the download, rootless `skopeo`
and `umoci`, stages the original `/opt/rocm` and `/opt/venv`
into Nix store with the original symlink policy, and records candidate
library roots, shim and candidate Python paths. Both runs use **fresh**
output directories. This remains a candidate—not a stable Nix package.

**Validate relocation before GPU:** check
`import/rocm-links.json`, `import/venv-links.json`,
`import/runtime-env.json`, `import/candidate.json`, and run the
existing closure/ELF audit. Then verify the selected Python imports Torch,
reports HIP `10.1`, and maps the selected ROCm tree. Executable
`python_candidates` in the selector report are *not* a successful
interpreter/provenance test. The original 6.4 runtime must not be in
`LD_LIBRARY_PATH`.

## Phase 3 — fastest independent original QKV Schaka shim test

From **LeechTransformer PR #4** checkout, reusing the original
CPU-frozen fixture and checkpoint:

```bash
cd /home/c/Documents/code/.leech-gpu-work
# Replace the two variables below with ACTUAL verified paths from
# candidate-runtime-selector.json after confirming the selected interpreter.
PY101=/nix/store/ACTUAL-10_1-VENV/bin/python
ROCM101=/nix/store/ACTUAL-10_1-ROCM

env -u LD_PRELOAD bash scripts/run_gfx803_qkv_shim_ab.sh \
  --trial --repeats 3 \
  --out-dir artifacts/gfx803_schaka101_shim_trial_first \
  --fixture artifacts/gfx803_qkv_wgm_ab/fixture \
  --python "$PY101" --rocm-root "$ROCM101" \
  --shim "$ROCM101/lib/libgfx803_sgemm_shim.so" \
  --hip-prefix 10.1
```

The **ON** process loads Schaka's actual shim, the **OFF** process
loads the same library disabled using his own
`GFX803_SGEMM_SHIM_DISABLE=1` control. Original FP32 input and weight
hashes, actual runtime library paths, output hashes, CPU reference errors
and repeats are recorded separately. Three-repeat trial receipts are
**numeric-only and non-promotional**, with no profiler attribution.
The trial does not need to rerun the already completed 6.4 100-repeat scan.

If the trial supports a useful effect, run the existing full profiler
ON/OFF with a **fresh directory**, `--repeats 100` and a
same-root `rocprofv3`. The profiler must show Schaka's actual
`gfx803_sgemm_kernel` ON, and absence OFF; matched source and
observer-free output identities are required before attributing the effect.

## Phase 4 — real dense and early-operator control

Run an original dense/C2 numerical gate in **separate** 10.1 shim-on
and, where safe, shim-off processes. The shim-on gate requires the
correct 10.1 Python and original teacher/student/token files:

```bash
env -u LD_PRELOAD bash scripts/run_gfx803_lila_repair_gate.sh \
  --lane 10.1-schaka \
  --python "$PY101" --rocm-root "$ROCM101" \
  --shim "$ROCM101/lib/libgfx803_sgemm_shim.so" \
  --receipt artifacts/gfx803_schaka101_lila_new.json \
  --repeats 3 --stability-steps 20 -- \
  --teacher /home/c/Documents/code/DASHIg/LeechTransformer/data/best_model.pt \
  --student /path/to/C2/student_model.pt \
  --config artifacts/gfx803_c2/leech_dense_config.json \
  --train-ids artifacts/gfx803_c2/dataset/train_ids.npy
```

On failure of the dense forward stage the gate deliberately stops
**before** C2 optimizer steps; this means the reported 20-step stability
probe was not executed, not that it passed or failed. A matching
10.1 operator-stage differential diagnosis is the next step if QKV is
fixed yet the layer-1 input still diverges.

For the independent release-side check:
```bash
python3 scripts/gfx803_lila_two_lane_receipts.py \
  --lane 10.1-schaka --gate-receipt /path/to/gfx803_schaka101_lila_new.json \
  --shim-ab-dir /path/to/FULL_profiled_shim_ab \
  --out out/schaka-oci/new-lila-101-candidate-verdict.json
```

**No training launch or release acceptance** from a successful
three-repeat shim test, a 20-step C2 test, or a mapped .so by itself.
Physical device/reset stress, original input tracing, profile attribution,
source and binary provenance, and clean Nix-client testing remain gates.

### Upstream attribution

Schaka owns the source/patches of the WGM fix **and** separate FP32 SGEMM
replacement and the published ROCm 10.1 image:
https://github.com/Schaka/rocm-gfx803
The local two-repository changes are Nix import, physical LILA test orchestration
and fail-closed evidence joining, not independent inventions of his kernels.
