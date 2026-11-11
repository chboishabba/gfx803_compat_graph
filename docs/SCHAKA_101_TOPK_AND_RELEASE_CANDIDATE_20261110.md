# Schaka 10.1 / patched Torch: operator assurance and Nix candidate closure

**10 November 2026. Source-level integration only; no new host execution is claimed.**
Original Schaka work is attributed to [Schaka/rocm-gfx803](https://github.com/Schaka/rocm-gfx803).
The generic gfx803 native TopK fix is proposed in [upstream PR #8](https://github.com/Schaka/rocm-gfx803/pull/8).

## Confirmed boundary

The imported Schaka ROCm 10.1 runtime and original dense inference passed the local
RX 580 qualification. Both upstream HIP `warptopk` and `sbtopk` had faulted
on float32 TopK [2,4], k=2. The successful wheel is a **different**
sort-backed `TensorTopK.cpp` routing patch, not the older sbtopk candidate.
On the RX 580 the patched wheel ran native TopK, and the focused 20-step
forward/backward/AdamW control passed. This does not establish exhaustive
operator compatibility or sustained host safety.

Wheel: `/nix/store/0l9bysk6xfx9dsndx9diwqf44x0h6zf2-torch-2.14.0-gfx803-topk-sort-fallback-20261110`

SHA-256: `0968548982ba69858d2dfe4ec0090ef1ce41ed610f0f9b3b9f38aebe0f0319eb`

## 2 — Expanded TopK semantics

The new `scripts/gfx803_topk_semantics.py` tests 120 combinations:
FP32/FP16; [2,4], [2,8], [2,64]; k in {1,2,3,4,8} where valid;
largest/smallest; sorted/unsorted; unique/tied/NaN entries.
Each subprocess compares returned values and valid unique indices, checks
selection/value multisets against CPU without falsely requiring tie-index
stability, checks input gradient against analytical scatter, and records
three repeat outcomes. NaN and tie index policies are explicitly scoped.

Each case writes its own supervisor receipt; timeouts or signals stop the
run by default, preserving unassayed entries. The old binary is known to
fault, so **do not run this matrix on the original unpatched wheel**.

Run using the **composed candidate wrapper** created below:

```bash
COMPOSED=/nix/store/ACTUAL-COMPOSED-OUTPUT
ROCM=/nix/store/ACTUAL-SELECTED-ROCM
"$COMPOSED/bin/gfx803-schaka101-python" scripts/gfx803_topk_semantics.py \
  --rocm-root "$ROCM" \
  --out out/gfx803-101-topk-semantics-20261110 --timeout 45
```

No full training/release claim is inferred even if 120/120 pass. The legacy
11-case conformance pass applied to the original binary; rerun all 12
operators including original native TopK on the patched wheel, using
`scripts/gfx803_torch_conformance.py --include-known-faults`.

## 4 — Compose a candidate from existing immutable store inputs

First use the existing `candidate-runtime-selector.json` produced by the
pinned Schaka import, and materialize the wheel from the public
`gfx803-rocm` Cachix cache (already published by upstream PR #8).

```bash
nix-store --realise /nix/store/0l9bysk6xfx9dsndx9diwqf44x0h6zf2-torch-2.14.0-gfx803-topk-sort-fallback-20261110

python3 scripts/gfx803_101_release_assembly.py \
  --selector out/schaka-oci/import-101/candidate-runtime-selector.json \
  --out out/gfx803-101-assembly-candidate.json

# These two must come from that SAME selected importer receipt.
ROCM=$(python3 -c 'import json;print(json.load(open("out/schaka-oci/import-101/candidate-runtime-selector.json"))["rocm_root"])')
VENV=$(python3 -c 'import json;print(json.load(open("out/schaka-oci/import-101/candidate-runtime-selector.json"))["venv_root"])')
WHEEL=/nix/store/0l9bysk6xfx9dsndx9diwqf44x0h6zf2-torch-2.14.0-gfx803-topk-sort-fallback-20261110

nix-build nix/gfx803/schaka101-composed-candidate.nix \
  --arg pkgs "(import $(nix flake archive --json . | jq -r '.inputs.nixpkgs.path') { system = \"x86_64-linux\"; })" \
  --argstr rocmStore "$ROCM" \
  --argstr venvStore "$VENV" \
  --argstr wheelStore "$WHEEL" \
  -o out/gfx803-101-composed-candidate

out/gfx803-101-composed-candidate/bin/gfx803-schaka101-python -c \
  'import torch; print(torch.__version__, torch.version.hip)'
```

The composition derivation checks the pinned wheel SHA256, unpacks it into a
new immutable PyTorch import overlay, links the original imported venv and
relocated ROCm root, and supplies a controlled loader wrapper. It does not
modify the existing store inputs. It is a **candidate**: no Nix evaluation,
build or GPU execution of the expression was possible in the authoring
environment, and its actual wheel/venv ABI must be verified on-device.

Clean-client verification must restore all referenced store paths from
Cachix on an independent machine; the imported ROCm and venv may not yet
have been pushed. Do not assume that publishing a wheel publishes the whole
closure. Capture `nix-store -q --references`, `nix path-info -r`, and
actual clean-client `nix-store --realise` receipts with hashes.

Release **must continue through** `scripts/gfx803_release.py` and
`scripts/publish-gfx803-accepted.sh --evidence-root ...` only after
their strict, original-log admission requirements are met. Neither the
candidate JSON nor the Nix composition is an accepted release manifest.
The current checked-in source lock has `image_digest: null`: update and
review that lock with observed immutable provenance before promotion.

## Independent experimental lane

The user is running original C2 training and fair dense-control quality
comparison separately. No quality improvement, full training safety,
codec compression gain or transport benchmark is asserted by this lane.
