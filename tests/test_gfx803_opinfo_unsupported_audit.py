"""Offline tests for immutable 183-skip OpInfo audit."""
import importlib.util
import json
from pathlib import Path
import unittest

SRC=Path(__file__).resolve().parents[1]/"scripts/gfx803_opinfo_unsupported_audit.py"
spec=importlib.util.spec_from_file_location("gfx803_opinfo_unsupported_audit",SRC)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class UnsupportedAuditTests(unittest.TestCase):
    def test_opinfo_naming(self):
        self.assertEqual(mod.parse_name(
            "test/test_ops.py::TestCommonCUDA::test_compare_cpu_linalg_svd_cuda_float32"),
            ("test_compare_cpu","float32","linalg_svd"))
        self.assertEqual(mod.parse_name(
            "test/test_ops.py::TestCommonCUDA::test_variant_consistency_eager_acos_cuda_complex64"),
            ("test_variant_consistency_eager","complex64","acos"))

    def test_skips_never_imply_missing_gpu_support(self):
        cases={f"test_compare_cpu_a{i}_cuda_float32":{"status":"unsupported"} for i in range(183)}
        cases.update({f"test_compare_cpu_b{i}_cuda_float32":{"status":"pass"} for i in range(1591)})
        report=mod.audit(json.dumps({"cases":cases}).encode(),expected_hash=None)
        self.assertEqual(report["unsupported_count"],183)
        self.assertEqual(report["hardware_unsupported_proven"],0)
        self.assertEqual(report["reason_classes"],{"skip-reason-not-recorded":183})
        self.assertFalse(report["release_admitted"])

    def test_immutable_original_hash(self):
        with self.assertRaises(ValueError):mod.audit(b'{"cases":{}}')

    def test_syntax(self):
        compile(SRC.read_text(),str(SRC),"exec")
if __name__=="__main__":unittest.main()
