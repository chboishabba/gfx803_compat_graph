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

    def test_schaka_execution_and_numeric_validation_remain_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"matrix.json"
            ids=["bf16","fp16","fp32","i8"]
            row={"schema":1,"suite":"triton-dot",
                 "schaka_sha":"8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78",
                 "selected":ids,
                 "cases":{name:{"status":"numeric-unqualified"} for name in ids},
                 "rocm_root":"/nix/store/123-test-runtime",
                 "release_admitted":False,"gpu_validated":False}
            file.write_text(json.dumps(row))
            report=mod.aggregate(self.catalog(),[],[("triton-dot",file)])
            self.assertEqual(report["source_suite_receipts_count"],1)
            source=report["layers"]["triton"]["source_owned_direct_suites"][0]
            self.assertEqual(source["execution_only_numeric_unqualified"],4)
            self.assertEqual(source["source_verified_pass"],0)
            self.assertFalse(report["all_rocm_apis_qualified"])

    def test_schaka_suite_rejects_wrong_source_identity(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"matrix.json"
            file.write_text(json.dumps({"schema":1,"suite":"triton-dot",
                "schaka_sha":"wrong","selected":["bf16","fp16","fp32","i8"],
                "cases":{x:{"status":"numeric-unqualified"} for x in
                         ("bf16","fp16","fp32","i8")},
                "rocm_root":"/nix/store/mock",
                "gpu_validated":False,"release_admitted":False}))
            with self.assertRaises(ValueError):
                mod.aggregate(self.catalog(),[],[("triton-dot",file)])

    def test_source_compiles(self):
        compile(SRC.read_text(),str(SRC),"exec")

if __name__=="__main__":unittest.main()
