"""Offline contracts for isolated HIP/ROCr/HSA direct smoke assay."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/gfx803_hip_hsa_direct_assay.py"
spec=importlib.util.spec_from_file_location("gfx803_hip_hsa_direct_assay",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class DirectAssayTests(unittest.TestCase):
    def test_seven_exactly_sourced_api_cases(self):
        self.assertEqual(len(m.CASES["hip"]),4)
        self.assertEqual(len(m.CASES["hsa"]),3)
        self.assertIn("pinned-host-copy",m.CASES["hip"])
        self.assertIn("signal-wait",m.CASES["hsa"])
        self.assertIn("queue-create-destroy",m.CASES["hsa"])
        self.assertTrue(all((m.NATIVE/path).is_file() for path in m.SOURCES.values()))

    def test_gpu_pass_requires_original_numeric_marker(self):
        good=b"GFX803_ASSAY case=h2d-d2h count=8192 wrong=0 result=PASS\n"
        self.assertEqual(m.classify("hip","h2d-d2h",0,good,b"")["status"],"passed")
        self.assertEqual(m.classify("hip","h2d-d2h",0,b"",b"")["status"],"invalid-output")
        self.assertEqual(m.classify("hip","h2d-d2h",0,
                         good.replace(b"wrong=0",b"wrong=7"),b"")["status"],
                         "invalid-output")
        self.assertEqual(m.classify("hip","h2d-d2h",1,good,b"")["status"],"nonzero-exit")
        self.assertEqual(m.classify("hip","h2d-d2h",-11,b"",b"")["status"],"fault")
        self.assertEqual(m.classify("hip","h2d-d2h",None,b"",b"")["status"],"timeout")

    def test_hsa_queue_cannot_pass_without_observed_marker(self):
        valid=b"GFX803_ASSAY case=queue-create-destroy result=PASS\n"
        self.assertEqual(m.classify("hsa","queue-create-destroy",0,valid,b"")["status"],
                         "passed")
        self.assertEqual(m.classify("hsa","queue-create-destroy",0,
                         valid.replace(b"queue-create-destroy",b"signal-wait"),b"")["status"],
                         "invalid-output")

    def test_source_contains_no_driver_modification_or_reset(self):
        native="\n".join((m.NATIVE/path).read_text() for path in m.SOURCES.values())
        self.assertNotIn("hsa_amd_memory_async_copy",native)  # future direct async copy gate
        self.assertNotIn("amdgpu_gpu_recover",native)
        self.assertNotIn("hipDeviceReset(",native)

    def test_runner_is_valid_python(self):
        compile(SRC.read_text(),str(SRC),"exec")

if __name__=="__main__":unittest.main()
