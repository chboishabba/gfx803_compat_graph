import unittest
from pathlib import Path


class NativeRocmCaptureContractTests(unittest.TestCase):
    def test_native_capture_emits_diff_ready_manifest(self):
        text = Path("scripts/capture-native-rocm-manifest.sh").read_text(encoding="utf-8")
        self.assertIn("stack_inventory.py", text)
        self.assertIn("pacman", text)
        self.assertIn("rocminfo", text)
        self.assertIn("release-manifest.json", text)
        self.assertIn("native-distro-control", text)


if __name__ == "__main__":
    unittest.main()
