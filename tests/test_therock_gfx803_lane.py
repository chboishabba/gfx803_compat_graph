from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build-therock-gfx803-artifacts.sh"
PUBLISH_SCRIPT = REPO_ROOT / "scripts" / "publish-ollama-and-extracted-artifacts-to-cachix.sh"
CUSTOM_TARGET = REPO_ROOT / "patches" / "therock-gfx803" / "therock_custom_amdgpu_targets.cmake"
ROADMAP = REPO_ROOT / "docs" / "THEROCK_GFX803_PREBUILT.md"
PATCH_ATLAS = REPO_ROOT / "docs" / "GFX803_UPSTREAM_PATCH_ATLAS.md"
SCHAKA_REF = REPO_ROOT / "scripts" / "probe-schaka-rocm10-gfx803-reference.sh"


def test_primary_lane_targets_current_upstream_therock_and_keeps_luca_as_reference():
    text = BUILD_SCRIPT.read_text()
    assert "https://github.com/ROCm/TheRock.git" in text
    assert "4213e176e29199c5dea5b54513bc3b1d36d91ca9" in text
    assert "--reference-luca" in text
    assert "lucbruni-amd/TheRock" in text
    assert "3d4ad6093a0069876fbfff590bb56ddb340ae9c5" in text


def test_gfx803_registration_uses_therock_custom_target_extension():
    target = CUSTOM_TARGET.read_text()
    assert "therock_add_amdgpu_target(gfx803" in target
    assert "gfx803-dgpu" in target
    assert "hipBLASLt" in target
    assert "MIOpen" in target

    script = BUILD_SCRIPT.read_text()
    assert "therock_custom_amdgpu_targets.cmake" in script
    assert "cmake/therock_custom_amdgpu_targets.cmake" in script


def test_therock_lane_separates_build_enumeration_correctness_and_release_promotion():
    text = BUILD_SCRIPT.read_text()
    assert "rocminfo" in text
    assert "clinfo" in text
    assert "unsupported_component_frontier" in text
    assert "promotion.env" in text

    roadmap = ROADMAP.read_text()
    assert "official AMD support" in roadmap
    assert "Build Passing" in roadmap
    assert "Sanity Tested" in roadmap
    assert "Release Ready" in roadmap
    assert "gfx803" in roadmap


def test_schaka_rocm10_is_a_reference_lane_not_an_amd_support_receipt():
    text = SCHAKA_REF.read_text()
    assert "ghcr.io/schaka/rocm-migraphx-ort-torch-builder:rocm10.0-gfx803" in text
    assert "reference-only" in text
    assert "rocm10-gfx803-reference" in text
    assert "rocminfo" in text
    assert "torch" in text

    atlas = PATCH_ATLAS.read_text()
    assert "Schaka/rocm-gfx803" in atlas
    assert "bc4b5acfd24cf29e1736900d54c047ca608da0b2" in atlas
    assert "hsa-agent-rejects-legacy-doorbell.patch" in atlas
    assert "d2h-staged-copy.patch" in atlas
    assert "d2h-null-dsthost.patch" in atlas
    assert "va-reuse-defer-noremap.patch" in atlas
    assert "superseded" in atlas
    assert "hardware / VBIOS" in atlas
    assert "community success != AMD Release Ready" in atlas


def test_standard_cachix_publish_set_includes_therock_gfx803_artifact():
    text = PUBLISH_SCRIPT.read_text()
    assert "artifacts/therock-gfx803" in text
