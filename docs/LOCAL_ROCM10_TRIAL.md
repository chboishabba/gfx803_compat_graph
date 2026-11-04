# Local ROCm 10 gfx803 trial

This runbook compares the installed Arch/CachyOS ROCm control with the published Schaka ROCm 10 gfx803 reference without replacing `/opt/rocm` or mutating installed packages.

## 1. Use the PR branch

```bash
git fetch origin agent/therock-gfx803-prebuilt-lane
git switch agent/therock-gfx803-prebuilt-lane
git pull --ff-only
```

Expected branch purpose: current-upstream TheRock restoration + community reference probes + diff/update-note tooling.

## 2. Capture the native distro control

```bash
bash scripts/capture-native-rocm-manifest.sh
```

This records:

- installed ROCm/HSA/HIP package versions from `pacman`
- `/opt/rocm` ELF hashes, SONAMEs and `DT_NEEDED`
- embedded `gfx*` target strings where visible
- current `rocminfo` GPU-agent topology (including chip/BDF identity)
- a tiny host PyTorch GPU correctness smoke when host PyTorch is available
- evidence payment state

Outputs are timestamped under:

```text
out/native-rocm-control/<timestamp>/
```

The main comparison artifact is:

```text
release-manifest.json
```

## 3. Probe the Schaka ROCm 10 reference

```bash
bash scripts/probe-schaka-rocm10-gfx803-reference.sh
```

Default image:

```text
ghcr.io/schaka/rocm-migraphx-ort-torch-builder:rocm10.0-gfx803
```

The probe passes `/dev/kfd` and `/dev/dri` into the container and records the immutable image ID/digest before testing it. It then records `rocminfo`, inventories `/opt/rocm`, and runs a tiny PyTorch GPU correctness smoke.

Outputs are timestamped under:

```text
out/rocm10-gfx803-reference/<timestamp>/
```

The primary artifact is again:

```text
release-manifest.json
```

This lane is `reference-only`: a successful community image is evidence that a capability works on the tested machine, not an AMD support/release-readiness receipt.

## 4. Diff the newest manifests

```bash
NATIVE_MANIFEST="$(find out/native-rocm-control -name release-manifest.json -print | sort | tail -1)"
ROCM10_MANIFEST="$(find out/rocm10-gfx803-reference -name release-manifest.json -print | sort | tail -1)"

python stack_manifest_diff.py \
  "$NATIVE_MANIFEST" \
  "$ROCM10_MANIFEST" \
  --json-out out/native-vs-rocm10.json \
  --markdown-out out/NATIVE_VS_ROCM10.md

cat out/NATIVE_VS_ROCM10.md
```

The generated note keeps separate:

```text
component/source delta
!= SONAME / dependency surface
!= embedded GPU target
!= device/topology delta
!= patch delta
!= behavioral promotion/regression
!= evidence payment
!= official AMD support
```

## 5. First interpretation gate

Do not jump directly to large workloads. First inspect:

```bash
cat "$(dirname "$ROCM10_MANIFEST")/torch-smoke.json"
grep -E 'Name:|Marketing Name:|Chip ID:|BDFID:' "$(dirname "$ROCM10_MANIFEST")/rocminfo.txt"
```

A useful first promotion is:

```text
ROCm 10 reference enumerates the intended Polaris agent
AND tiny tensor result is correct
```

That is sufficient to proceed to the existing Leech minimal correctness repro. It is not sufficient to claim async/reset safety.

## 6. Next discriminators after the tiny smoke

If the reference is clean, run in this order:

1. Leech tensor-only layout/determinism reproducer.
2. Minimal `nn.Linear` correctness fixture inspired by Robert issue #55.
3. Small D2H pinned/pageable copy-churn reproducer.
4. Short WhisperX workload.
5. Long async WhisperX/reset lane only after the smaller gates are paid.

Record VBIOS / memory-clock state before interpreting a reset-class result, because community history includes at least one software-looking hang that was later attributed to VRAM-clock/VBIOS marginality.

## Failure handling

Keep failures as evidence. Do not delete the timestamped output directory. A failed ROCm 10 probe can still distinguish:

- image/runtime admission failure
- missing gfx803 agent
- topology mismatch
- Torch import failure
- GPU visibility failure
- tiny numerical correctness failure
- inventory/ABI differences

Those are different compatibility cuts and should not be collapsed into `ROCm 10 does not work`.
