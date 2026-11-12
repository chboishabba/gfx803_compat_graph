"""Offline contract tests for source-bound ten-layer ROCm evidence aggregation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/gfx803_rocm_coverage_report.py"
spec=importlib.util.spec_from_file_location("gfx803_rocm_coverage_report",SRC)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class CoverageReportTests(unittest.TestCase):
    def catalog(self):
        return json.loads((ROOT/"qualification/rocm_layers_v1.json").read_text())

    def test_no_receipts_retains_opinfo_and_nine_unqualified(self):
        report=mod.aggregate(self.catalog(),[])
        self.assertEqual(len(report["layers"]),10)
        self.assertEqual(report["layers"]["pytorch-opinfo"]["passed_opinfo"],1583)
        self.assertEqual(report["layers"]["pytorch-opinfo"]["historical_upstream_skips"],183)
        self.assertEqual(report["layers"]["miopen"]["status"],"unqualified-in-this-aggregation")
        self.assertFalse(report["all_rocm_apis_qualified"])
        self.assertFalse(report["release_admitted"])

    def test_ctest_case_inventory_join(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"matrix.json"
            row={"schema":1,"layer":"hip-runtime",
                 "all_discovered_tests":["memcpy","stream","event"],
                 "cases":{"memcpy":{"status":"ctest-pass"},
                          "stream":{"status":"ctest-fail"},
                          "event":{"status":"unassayed"}},
                 "rocm_root":"/nix/store/123-test-runtime",
                 "release_admitted":False,"gpu_validated":False,
                 "runtime_coherence_verified":False}
            file.write_text(json.dumps(row))
            report=mod.aggregate(self.catalog(),[("hip-runtime",file)])
            info=report["layers"]["hip-runtime"]
            self.assertEqual(info["passed_ctest_reports"],1)
            self.assertEqual(info["failed_or_faulted"],1)
            self.assertEqual(info["unassayed"],1)
            self.assertFalse(info["runtime_coherence_verified"])

    def test_promoted_source_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"matrix.json"
            file.write_text(json.dumps({"schema":1,"layer":"miopen",
                "all_discovered_tests":["conv"],"cases":{"conv":{"status":"ctest-pass"}},
                "release_admitted":True,"gpu_validated":False,
                "rocm_root":"/nix/store/mock"}))
            with self.assertRaises(ValueError):
                mod.aggregate(self.catalog(),[("miopen",file)])

    def test_duplicate_and_foreign_cases_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"matrix.json"
            file.write_text(json.dumps({"schema":1,"layer":"miopen",
                "all_discovered_tests":["conv"],"cases":{"not-conv":{"status":"ctest-pass"}},
                "release_admitted":False,"gpu_validated":False,
                "rocm_root":"/nix/store/mock"}))
            with self.assertRaises(ValueError):
                mod.aggregate(self.catalog(),[("miopen",file)])

    def test_source_compiles(self):
        compile(SRC.read_text(),str(SRC),"exec")

if __name__=="__main__":unittest.main()
