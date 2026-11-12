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
                                          "nodes":{"one":{},"two":{}}},requested))
        self.assertFalse(m.child_complete({"pytest_returncode":4,"nodes":{}},requested))
        self.assertFalse(m.child_complete({"pytest_returncode":0,"nodes":{"one":{}}},requested))

if __name__=="__main__":unittest.main()
