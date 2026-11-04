import hashlib
import tempfile
import unittest
from pathlib import Path

try:
    from PIL import Image
    from scripts.gfx803_comfyui_images import compare
    HAVE_PILLOW = True
except ImportError:
    HAVE_PILLOW = False


@unittest.skipUnless(HAVE_PILLOW, "Pillow image comparator is optional")
class ComfyUIImageComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        self.good = self.p / "good57.png"
        self.bad = self.p / "bad64.png"
        self.new = self.p / "new101.png"
        Image.new("RGB", (4, 4), (0, 0, 0)).save(self.good)
        Image.new("RGB", (4, 4), (255, 255, 255)).save(self.bad)
        Image.new("RGB", (4, 4), (0, 0, 0)).save(self.new)
        self.workflow = self.p / "workflow.json"
        self.workflow.write_text('{"seed": 42}')
        self.model = self.p / "model.safetensors"
        self.model.write_bytes(b"fixture model, not real weights")

    def run_test(self):
        return compare(self.good, self.bad, self.new,
                       workflow=self.workflow, model=self.model,
                       seed=42, max_rmse=0.1, improvement_ratio=0.5)

    def test_correct_candidate_beats_historical_failure(self):
        result = self.run_test()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["normalized_rmse_candidate_101_vs_good_57"], 0)
        self.assertEqual(result["normalized_rmse_bad_64_vs_good_57"], 1)
        self.assertEqual(result["seed"], 42)
        self.assertEqual(result["workflow_sha256"],
                         hashlib.sha256(self.workflow.read_bytes()).hexdigest())

    def test_corrupt_candidate_fails(self):
        Image.new("RGB", (4, 4), (255, 255, 255)).save(self.new)
        self.assertEqual(self.run_test()["status"], "fail")

    def test_explicit_tolerance_must_be_met(self):
        Image.new("RGB", (4, 4), (64, 64, 64)).save(self.new)
        self.assertEqual(self.run_test()["status"], "fail")

    def test_identical_good_and_bad_is_invalid_control(self):
        Image.new("RGB", (4, 4), (0, 0, 0)).save(self.bad)
        with self.assertRaisesRegex(ValueError, "invalid negative control"):
            self.run_test()

    def test_mismatched_image_sizes_fail(self):
        Image.new("RGB", (8, 8), (0, 0, 0)).save(self.new)
        with self.assertRaisesRegex(ValueError, "share dimensions"):
            self.run_test()


if __name__ == "__main__":
    unittest.main()
