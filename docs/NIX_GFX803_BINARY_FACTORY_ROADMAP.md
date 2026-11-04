# gfx803 Nix binary factory: build and distribution roadmap (2026-11-04)

## Scope and ownership

The product is **both a reproducible build environment and independently installable gfx803 binaries**. Consumers should not need Docker, an old Ubuntu root filesystem, or ROCm compilation; developers should be able to reconstruct accepted packages from exact sources, patches, compiler and package graph.

- Schaka/rocm-gfx803 owns the original ROCm 10.x GFX8 fixes, source build recipes and correctness suite. Reuse and credit them; do not independently re-implement wave64, WGM, cache-coherency or MIOpen fixes.
- gfx803_compat_graph owns reproducible Nix packaging, build inputs, compatibility evidence, release policy, Cachix and upgrades.
- ROCm/TheRock remains the desired upstream destination. Existing PR #4 addresses that separately; this lane must not replace it.
- Application projects are optional consumers and canaries, not the definition of build-system correctness.

## State, as of this branch

| Gate | Current evidence | Status |
|---|---|---|
| Extracted ROCm 6.4 control | Existing measured direct_only pass, plus retained negative results | PRESERVED |
| Pinned Schaka revision | nix/gfx803/upstream.json names full 40-byte SHA and release | SOURCE-WRITTEN |
| Nix bootstrap tools | Root flake exports daemonless OCI tool shell, importer, policy, checks | SOURCE-WRITTEN |
| Digest-pinned upstream image import | skopeo + umoci -> Nix store paths + candidate.json | SOURCE-WRITTEN, not run |
| GPU numerical/reset admission | Seven required receipt types, exact hardware/provenance | OPEN |
| Accepted cached binary packages | Optional fetchClosure flake outputs after accepted manifest | DEFINED, no accepted release |
| Native, source-built ROCm Nix derivations | Patched runtime, math, compiler, frameworks in separate outputs | OPEN |
| Upstream change discovery | Scheduled weekly source update PR | SOURCE-WRITTEN, not run on default branch |
| Automatic native build/publish | DAG changes, CI, hardware gate and release promotion | OPEN |

SOURCE-WRITTEN is **not** built, run, hardware validated or production ready.

## Entry points

The **root flake** is the new canonical interface; gfx803_flake_v1 continues to preserve existing control and diagnostic shells.

- `nix develop .#gfx803-oci-build`: reproducible OCI/Nix tooling with NO unrelated Nixpkgs ROCm shared-library injection.
- `nix run .#gfx803-schaka-import -- --help`: import immutable image parts to Nix store (candidate only).
- `nix run .#gfx803-release-policy -- --help`: inspect source and evidence policy.
- `nix build .#gfx803-schaka-upstream-lock`: source pin artifact.
- `nix build .#checks.x86_64-linux.gfx803-release-policy`: offline mock-import and policy tests.
- Only with a committed hardware-accepted release manifest: `nix build .#gfx803-rocm-binary` (and optional `gfx803-venv-binary`), fetched from gfx803-rocm.cachix.org.

The latter use experimental `builtins.fetchClosure`, and current input-addressed paths require the configured Cachix trust key. Eventually use `nix store make-content-addressed` and record rewritten hashes to remove that dependency.

## Phase A: reuse the existing successful binaries first

The bootstrap imports an image **by OCI SHA256 digest**, via skopeo and rootless umoci; no Docker daemon is required. It adds only selected /opt/rocm and optional /opt/venv subtrees to the Nix store, not a full image tarball. It is an intentionally transitional **binary import**, not a native Nix compilation and not yet a minimal/runtime-relocated closure.

Example, with the image digest resolved independently:

```bash
nix develop .#gfx803-oci-build
repo=ghcr.io/schaka/rocm-migraphx-ort-torch-builder
digest="$(skopeo inspect --format '{{.Digest}}' "docker://$repo:rocm10.1-gfx803")"
rev="$(python3 -c 'import json; print(json.load(open("nix/gfx803/upstream.json"))["source_revision"])')"
gfx803-import-schaka --image "$repo@$digest" --source-revision "$rev" \
  --with-venv --out out/schaka-oci/rocm10.1
```

This has NOT run here. It produces an unvalidated candidate manifest and Nix store paths. Its source-commit-to-image correspondence and runtime relocatability remain unverified until supported by actual receipts.

## Phase B: close the first accepted binary release

1. Resolve and pin immutable OCI digest and verify the published build revision matches the selected Schaka SHA.
2. Import on a Nix machine. Audit ELF DT_NEEDED, RPATH, duplicate ROCm/HIP/HSA/LLVM libraries, absolute /opt/rocm paths, wheel shebangs and runtime dependencies. Eliminate or wrap nonrelocatable paths without blending ABI lines.
3. Run Schaka's tools/imgvalidate.sh, verify.py and relevant negative controls on actual Polaris hardware; integrate the compat graph's drift, repeated-run and reset diagnostics.
4. Record source provenance, GPU enumeration, kernel dispatch, numerical correctness, repeatability, sustained load, and runtime linkage. Each must have pass status, executed command, relative log_path, and retained log SHA256. Promotion opens the real log files under --evidence-root and checks their bytes against those digests; also include actual gfx803 device, kernel, driver and runner.
5. Only after all gates pass, run the release policy promoter to generate an accepted-release.json and review it. Then publish only those accepted store paths via the Cachix script.
6. Fetch the resulting Nix outputs on a clean client and verify they work without Docker or mixed system ROCm.

```bash
python3 scripts/gfx803_release.py promote \
  --manifest out/schaka-oci/rocm10.1/candidate.json \
  --out nix/gfx803/accepted-release.json \
  --evidence-root out/schaka-oci/rocm10.1/logs
bash scripts/publish-gfx803-accepted.sh nix/gfx803/accepted-release.json --dry-run
bash scripts/publish-gfx803-accepted.sh nix/gfx803/accepted-release.json
```

The promoter is deliberately fail-closed: importing, compiling or enumerating a GPU is insufficient. Acceptance does not assert universal gfx803 correctness or official AMD support.

## Phase C: native, modular Nix source builds

Port Schaka's exact source and patch graph into independently cacheable derivations, retaining original attribution:

`patched ROCr/CLR -> rocBLAS + MIOpen -> rocSOLVER -> MIGraphX -> PyTorch / ONNX Runtime / optional Triton and consumers`.

Use a **matched ROCm release compiler, headers and device-libs**. The earlier LLVM 22 versus 19 and old/new HIP-HSA mixups are reasons to isolate the entire SDK, not to extend ad hoc LD_LIBRARY_PATH wrappers.

Separate runtime, development, device-code, tools and Python wheel outputs; avoid duplicating the ROCm tree across packages or shipping compilers in consumers' runtime closures. Reuse upstream build scripts and patches with only packaging adaptations; run the same on-card tests against the native binaries. Never rebuild an unchanged component just because an unrelated project changed.

## Phase D: automatic source/update/build/release

The weekly upstream-watch workflow *only* proposes changed source revisions. It never asserts a successful new GPU build. Once native derivations exist, CI should rebuild precisely the derivations invalidated by their hashes, re-run hosted source checks, then run physical gfx803 checks on a self-hosted runner. Candidate Cachix artifacts and receipts should be separate from accepted stable closures. Promotion is explicit and evidence-dependent; retain earlier accepted manifests and Nix store closures for rollback.

## Definition of done

- A clean consumer downloads the needed **finished patched binaries** through Nix/Cachix without Docker or local compilation.
- A clean Nix builder can reproducibly construct the full patched SDK/runtime/math/framework stack from immutable, attributed source and patches.
- Every supported hardware/stack combination has reproducible numerical, dispatch, linkage and sustained-load evidence.
- Automated upstream change discovery and incremental builds produce candidates; only admitted candidates become stable.
- The original 6.4 control and historical failure receipts remain available and never get relabelled as universal correctness.

**Remaining exact max-cut:** first real digest import + relocation audit + on-card acceptance, then native source derivations and automated incremental build/promote. This branch implements the source lock, import/policy surface, conditional Cachix outputs, and candidate source-watch, but does not pretend the unexecuted gates are closed.
