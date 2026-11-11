"""Offline evidence-only capability ledger tests; no device or PyTorch required."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import json

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/"scripts/gfx803_capability_atlas.py"
spec=importlib.util.spec_from_file_location("gfx803_capability_atlas",path)
atlas=importlib.util.module_from_spec(spec)
spec.loader.exec_module(atlas)

PROFILE={k:"present" for k in atlas.FIELDS}
PROFILE["torch_wheel_sha256"]="0"*64

class CapabilityAtlasTests(unittest.TestCase):
    def test_original_pass_and_unassayed_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            original=Path(d)/"matrix.json"
            original.write_text(json.dumps({"cases":{"case-1":{"status":"pass"},
                                                       "case-2":{"status":"unassayed"}}}))
            output=atlas.aggregate(PROFILE,[("topk",original)])
            self.assertEqual(output["counts"]["pass"],1)
            self.assertEqual(output["counts"]["unassayed"],1)
            self.assertFalse(output["general_gpu_compatibility"])
            self.assertFalse(output["release_admitted"])
            self.assertTrue(all(len(x["original_receipt_sha256"])==64
                                for x in output["cases"]))

    def test_unknown_status_and_missing_profile_fail_closed(self):
        with self.assertRaises(ValueError):
            atlas.validate_profile({"board":"RX 580"})
        with self.assertRaises(ValueError):
            atlas.normalize("suite",{"cases":{"x":{"status":"promoted"}}},"a"*64)

    def test_duplicate_case_cannot_double_count(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"matrix.json"
            p.write_text(json.dumps({"cases":{"x":{"status":"pass"}}}))
            with self.assertRaises(ValueError):
                atlas.aggregate(PROFILE,[("torch",p),("torch",p)])

    def test_source_compiles(self):
        compile(path.read_text(),str(path),"exec")

if __name__=="__main__":
    unittest.main()
