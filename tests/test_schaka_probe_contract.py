import unittest
from pathlib import Path


class SchakaProbeContractTests(unittest.TestCase):
    def test_probe_produces_inventory_and_manifest_for_diffing(self):
        text = Path("scripts/probe-schaka-rocm10-gfx803-reference.sh").read_text(encoding="utf-8")
        self.assertIn("stack_inventory.py", text)
        self.assertIn("stack-inventory.json", text)
        self.assertIn("release-manifest.json", text)
        self.assertIn("image_digest", text)
        self.assertIn("reference-only", text)


if __name__ == "__main__":
    unittest.main()
