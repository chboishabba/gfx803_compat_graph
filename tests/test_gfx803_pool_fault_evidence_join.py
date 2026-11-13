"""Offline source-bound pooling fault evidence join contracts."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/gfx803_pool_fault_evidence_join.py"
spec=importlib.util.spec_from_file_location("gfx803_pool_fault_evidence_join",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class EvidenceJoinTests(unittest.TestCase):
    def fixture(self,root):
        common={"source_sha":m.PIN,"release_admitted":False}
        a=root/"isolated.json"
        b=root/"prefix.json"
        a.write_text(json.dumps({**common,"original_sha256":"f"*64,
          "rocm_prefix":"/nix/store/a-staged",
          "cases":{str(i):{"status":"pass","tested":1,"wrong":0} for i in range(42)}}))
        b.write_text(json.dumps({**common,"original_pool_sha256":"f"*64,
          "rocm_prefix":"/nix/store/a-staged",
          "cases":{str(i):{"status":"passed"} for i in
                   (1,2,4,8,14,16,21,28,35,42)}}))
        return a,b

    def test_42_and_ten_are_not_causal_proof(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=self.fixture(Path(d))
            result=m.join(a,b)
            self.assertEqual(result["isolated_pass"],42)
            self.assertEqual(result["shared_process_pass"],10)
            self.assertFalse(result["cumulative_state_causality_established"])
            self.assertFalse(result["release_admitted"])
            self.assertEqual(result["doorbell_callback_in_running_kernel"],"unverified")

    def test_rejects_missing_and_unqualified_cases(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=self.fixture(Path(d))
            x=json.loads(a.read_text());x["cases"]["0"]["status"]="fault"
            a.write_text(json.dumps(x))
            with self.assertRaises(ValueError):m.join(a,b)

    def test_original_binary_fault_is_not_suppressed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a,b=self.fixture(root)
            ctrl=root/"controls.json"
            ctrl.write_text(json.dumps({"source_sha":m.PIN,
                "release_admitted":False,"original_source_sha256":"f"*64,
                "rocm_prefix":"/nix/store/a-staged",
                "controls":{"baseline":{},"sdma-off":{"HSA_ENABLE_SDMA":"0"}},
                "results":{"baseline":{"status":"fault"},
                           "sdma-off":{"status":"unassayed"}}}))
            out=m.join(a,b,ctrl)
            self.assertTrue(out["original_binary_reproduced_fault"])
            self.assertFalse(out["cumulative_state_causality_established"])

    def test_code_compiles(self):
        compile(SRC.read_text(),str(SRC),"exec")

if __name__=="__main__":unittest.main()
