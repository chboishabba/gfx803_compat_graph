"""Offline fixtures for pinned Schaka MIOpen build/qualification, no GPU needed."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/gfx803_schaka_miopen_qualification.py"
spec=importlib.util.spec_from_file_location("gfx803_schaka_miopen_qualification",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class MIOpenQualificationTests(unittest.TestCase):
    def test_original_sources_enumerated(self):
        self.assertEqual(len(m.OPS),13)
        self.assertEqual(len(m.EXPECTED),14)
        self.assertIn("conv_solver_sweep",m.EXPECTED)
        self.assertEqual(m.PIN,"8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78")

    def test_valid_original_numeric_summary(self):
        got=m.evaluate(0,b"mode=RELU cos=1.00000 OK\n",
                       b"SUMMARY: 120 cases tested, 0 WRONG\n")
        self.assertEqual(got["status"],"passed")
        self.assertEqual(got["effective_tested"],120)
        self.assertEqual(got["wrong"],0)

    def test_no_eligible_solver_never_passes(self):
        got=m.evaluate(0,b"shape #1 -> SKIP\nshape #2 -> SKIP\n",
                       b"SUMMARY: 2 shapes tested, 0 WRONG\n")
        self.assertEqual(got["status"],"empty-results")
        self.assertEqual(got["effective_tested"],0)

    def test_original_wrong_result_is_failure(self):
        got=m.evaluate(1,b"shape -> WRONG\n",
                       b"SUMMARY: 1 shapes tested, 1 WRONG\n")
        self.assertEqual(got["status"],"failed")
        self.assertEqual(got["wrong"],1)
        self.assertEqual(m.evaluate(0,b"",b"")["status"],"empty-results")
        self.assertEqual(m.evaluate(-11,b"",b"")["status"],"fault")
        self.assertEqual(m.evaluate(None,b"",b"")["status"],"timeout")

    def test_no_false_promotion_on_resume(self):
        identity={"schema":1,"source_sha":m.PIN,"selected":["activ_sweep"],
                  "rocm_root":"/nix/store/test"}
        state={**identity,"cases":{"activ_sweep":{"status":"unassayed"}},
               "release_admitted":False}
        self.assertEqual(m.validate_resume(state,identity),state)
        state["release_admitted"]=True
        with self.assertRaises(ValueError):m.validate_resume(state,identity)

    def test_identity_uses_exact_original_source(self):
        t=m.make_identity(Path("/source"),Path("/source/tools"),{"build.sh":"abc"},
                          {"pool_sweep":{"binary":"pool_sweep"}},
                          "/nix/store/example","/nix/store/example/core-10.1",
                          "/nix/store/bin/hipcc","abc")
        self.assertEqual(t["source_sha"],m.PIN)
        self.assertEqual(t["selected"],["pool_sweep"])

    def test_atomic_matrix_output(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"matrix.json"
            m.persist(path,{"status":"planned"})
            self.assertEqual(json.loads(path.read_text())["status"],"planned")
            self.assertFalse(path.with_name("matrix.json.tmp").exists())

    def test_syntax(self):
        compile(SCRIPT.read_text(),str(SCRIPT),"exec")

if __name__=="__main__":unittest.main()
