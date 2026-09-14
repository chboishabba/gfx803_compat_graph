from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build-therock-gfx803-artifacts.sh"
PUBLISH_SCRIPT = REPO_ROOT / "scripts" / "publish-ollama-and-extracted-artifacts-to-cachix.sh"


def test_therock_build_lane_exists_and_pins_known_restore_commit():
    text = BUILD_SCRIPT.read_text()
    assert "lucbruni-amd/TheRock" in text
    assert "3d4ad6093a0069876fbfff590bb56ddb340ae9c5" in text
    assert "gfx803-dgpu" in text
    assert "--patch-tag gfx803" in text
    assert "artifacts/therock-gfx803" in text


def test_therock_lane_separates_core_build_from_framework_promotion():
    text = BUILD_SCRIPT.read_text()
    assert "rocminfo" in text
    assert "clinfo" in text
    assert "hipBLASLt" in text
    assert "MIOpen" in text
    assert "unsupported_component_frontier" in text


def test_standard_cachix_publish_set_includes_therock_gfx803_artifact():
    text = PUBLISH_SCRIPT.read_text()
    assert "artifacts/therock-gfx803" in text
