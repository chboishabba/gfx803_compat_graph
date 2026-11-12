"""Offline tests for immutable OpInfo skip-reason recovery without GPU execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/gfx803_opinfo_skip_reason_probe.py"
SPEC=importlib.util.spec_from_file_location("gfx803_opinfo_skip_reason_probe",SOURCE)
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

class Marker:
    def __init__(self,name,reason="",args=()):
        self.name=name
        self.kwargs={"reason":reason}
        self.args=args

class Item:
    def __init__(self,name,markers):
        self.nodeid=name
        self.markers=markers
    def iter_markers(self):
        return iter(self.markers)

class SkipReasonProbeTests(unittest.TestCase):
    def fixture(self):
        return {"schema":1,"source_matrix_sha256":m.MATRIX_SHA,
                "unsupported_count":183,
                "rows":[{"nodeid":f"test/test_ops.py::TestCommonCUDA::test_compare_cpu_case{i}_cuda_float32",
                         "original_status":"unsupported","reason":None}
                        for i in range(183)]}

    def test_collect_exact_183_nodes_without_run(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"audit.json"
            f.write_text(json.dumps(self.fixture()))
            names,sha=m.read_audit(f)
            self.assertEqual(len(names),183)
            self.assertEqual(sha,hashlib.sha256(f.read_bytes()).hexdigest())

    def test_original_status_and_hash_must_match(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"audit.json"
            doc=self.fixture()
            doc["rows"][0]["reason"]="invented reason"
            f.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):m.read_audit(f)
            doc["rows"][0]["reason"]=None
            doc["source_matrix_sha256"]="bad"
            f.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):m.read_audit(f)

    def test_static_markers_preserve_upstream_reason(self):
        markers=[Marker("skipif","ROCm unsupported",("cond",)),
                 Marker("xfail","known issue"),Marker("slow","not skip")]
        row=m.marker_record(Item("node",markers))
        self.assertEqual(len(row),2)
        self.assertEqual(row[0]["reason"],"ROCm unsupported")
        self.assertEqual(row[1]["name"],"xfail")

    def test_guard_replaces_original_runtest_callable(self):
        # This is stronger than relying on a pytest_runtest_call hook to
        # execute before the upstream call implementation.
        class FakeItem:
            nodeid="test/test_ops.py::TestCommonCUDA::test_compare_cpu_fake_cuda_float32"
            def iter_markers(self):return iter(())
            def runtest(self):raise AssertionError("original body executed")
        item=FakeItem()
        original=item.runtest
        capture=m.Capture("setup")
        capture.pytest_collection_modifyitems([item])
        self.assertNotEqual(item.runtest, original)
        self.assertEqual(capture.rows[item.nodeid]["runtime_outcome"],"not-run")

    def test_replay_capture_preserves_a_passed_call(self):
        class Report:
            nodeid="test/test_ops.py::TestCommonCUDA::test_compare_cpu_fake_cuda_float32"
            when="call"
            skipped=False
            failed=False
            passed=True
            longrepr=""
        capture=m.Capture("replay")
        capture.rows[Report.nodeid]={"markers":[],"runtime_outcome":"not-run"}
        capture.pytest_runtest_logreport(Report())
        self.assertEqual(capture.finished()[Report.nodeid]["runtime_outcome"],"executed-passed")

    def test_replay_capture_distinguishes_xfail_from_skip(self):
        class Report:
            nodeid="test/test_ops.py::TestCommonCUDA::test_compare_cpu_fake_cuda_float32"
            when="call"
            skipped=True
            failed=False
            passed=False
            wasxfail="known upstream discrepancy"
            longrepr="expected failure detail"
        capture=m.Capture("replay")
        capture.rows[Report.nodeid]={"markers":[],"runtime_outcome":"not-run"}
        capture.pytest_runtest_logreport(Report())
        self.assertEqual(capture.finished()[Report.nodeid]["runtime_outcome"],"upstream-xfailed")

    def test_replay_completion_accepts_a_test_failure_receipt(self):
        child={"pytest_returncode":1,"nodes":{"one":{"runtime_outcome":"execution-failed"}}}
        self.assertTrue(m.child_complete(child,["one"],"replay"))
        self.assertFalse(m.child_complete({"pytest_returncode":2,"nodes":{"one":{}}},["one"],"replay"))

    def test_no_test_body_execution_in_source(self):
        code=SOURCE.read_text()
        self.assertIn('pytest.skip(GUARD)',code)
        self.assertIn('"--collect-only"',code)
        self.assertIn("--execute-setup",code)
        self.assertIn("release_admitted",code)
        compile(code,str(SOURCE),"exec")

    def test_collection_requires_all_requested_generated_nodes(self):
        requested=["one","two"]
        self.assertTrue(m.child_complete({"pytest_returncode":0,
                                          "nodes":{"one":{},"two":{}}},requested,"static"))
        self.assertFalse(m.child_complete({"pytest_returncode":4,"nodes":{}},requested,"static"))
        self.assertFalse(m.child_complete({"pytest_returncode":0,"nodes":{"one":{}}},requested,"static"))

    def test_static_collection_keeps_not_run_as_phase_not_evidence_failure(self):
        code=SOURCE.read_text()
        self.assertIn('"replayed" if a.mode=="replay" else "collected"',code)
        self.assertIn('runtime_outcome: not-run',code)

if __name__=="__main__":unittest.main()
