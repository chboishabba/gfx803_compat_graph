# Evidence-aware stack manifest differ

`stack_manifest_diff.py` compares two compatibility/release manifests and emits both a machine-readable delta and human-readable update notes.

The purpose is not merely to say "ROCm changed from X to Y". For gfx803, that is too coarse to be useful. A useful update note must keep at least these coordinates separate:

```text
component/source revision
!= target registration
!= patch set
!= GPU enumeration
!= numerical correctness
!= long-run/reset safety
!= evidence/payment state
!= official support state
```

This is the same evidence discipline used elsewhere in the repo: an observed change is not automatically a causal explanation, and a passing smoke is not automatically a support guarantee.

## Usage

Given two manifests:

```bash
python stack_manifest_diff.py old-release.json new-release.json
```

To retain both output forms:

```bash
python stack_manifest_diff.py old-release.json new-release.json \
  --json-out out/update-delta.json \
  --markdown-out out/UPDATE_NOTES.md
```

The existing `scripts/build_release_manifest.py` output is accepted as-is. Optional richer fields are also understood:

```json
{
  "release_id": "rocm10-gfx803-2026-09-14",
  "stack_id": "gfx803",
  "components": {
    "rocm-systems": "c83f23b31d8a64aef9cefece339713e6898efb2d",
    "rocblas": "release/rocm-rel-10.0"
  },
  "targets": ["gfx803"],
  "patch_set": [
    "legacy-doorbell",
    "d2h-staged-copy"
  ],
  "benchmark_summary": {
    "statuses": {
      "enumeration": "pass",
      "leech": "partial",
      "whisperx": "crash"
    }
  },
  "evidence": {
    "build": "paid",
    "enumeration": "paid",
    "numerical_correctness": "partial",
    "reset_safety": "unpaid"
  }
}
```

Missing optional sections are treated as empty so historical manifests remain comparable.

## Status ordering

The first tranche reuses the repo's existing benchmark ordering:

```text
crash < hang < fail < partial < pass
```

This ordering is an operational summary only. For example, `crash -> hang` is recorded as a promotion in process survivability, not as evidence that the underlying mechanism improved or that the resulting stack is usable.

Unknown/custom status names are retained under `changed_unknown` instead of being forced into an invented order.

## Why this is needed for gfx803

Historical issues demonstrate that one-dimensional release notes are insufficient.

### Enumeration without correctness

Robert Rosenbusch issue #43 reports RX570/RX580 ComfyUI workloads that enumerate and run but produce corrupted output on newer ROCm paths, while a 5.7 image is reported working in the same discussion. The thread also contains an FP16 hypothesis, but that remains discussion evidence rather than a general root-cause proof.

Robert issue #55 is an even smaller example: `nn.Linear` on an RX580 returns a numerically wrong GPU result while a nearby explicit matrix multiplication returns the CPU-expected answer. A release note that says only "GPU supported" would erase the consumer-relevant coordinate.

### Same ISA label, different topology

Robert issue #50 reports a laptop where both the RX560X dGPU and Vega 8 iGPU appear as `gfx803`; `rocminfo` enumerates both, while OpenCL reports zero devices and importing torch segfaults. A commenter reports that disabling integrated graphics avoids the failure on another multi-GPU system.

Therefore:

```text
same gfx ISA string != same physical device != same topology != same compatibility result
```

Future manifest enrichment should retain PCI/BDF or stable device identity so the differ can distinguish topology changes from software changes.

### Source build progress is not whole-stack support

The earlier `lamikr/rocm_sdk_builder` gfx803 work is another useful pattern. The gfx803 target could be introduced to the build configuration and the build progressed deeply into the stack; rocFFT then failed during its shipped AOT-cache generation because the helper invocation lacked a target argument. That is a component/build-seam defect, not evidence that gfx803 itself cannot execute FFTs.

A later `rocm_sdk_builder` issue hit a SONAME mismatch (`librocm_smi64.so.1` expected versus `.so.7` produced) while building torchvision. That motivates a future ABI/ELF manifest coordinate rather than treating all failures as target-architecture failures.

## Intended next enrichment

The next useful manifest coordinates, in priority order, are:

1. component repo + exact commit/tag
2. exported/required SONAMEs and symbol versions
3. compiled GPU target/code-object inventory
4. GPU identity/topology (BDF, chip ID, marketing name, ISA)
5. patch provenance (source repo/commit/blob)
6. benchmark/consumer status
7. evidence/payment state

The differ should remain a projection over those recorded facts. It must not infer AMD support, root cause, or hardware capability merely from a changed field.
