"""CPU-only original QKV release evidence firewall regressions.

No synthetic test is falsely marked as a real Leech/gfx803 admission.
Schaka's original WGM and FP32 SGEMM patches remain upstream-owned.
"""
import csv
import math
import struct
import tempfile
import unittest
from pathlib import Path

from scripts.gfx803_leech_qkv_admission import (
    QKVAdmissionError, actual_profiler_kernels, fp32_compare,
    stage_original_evidence, verify_bundle,
)
from scripts.gfx803_release import CAPABILITY_GATES, validate_candidate


class QKVRawEvidenceContractTests(unittest.TestCase):
    def test_actual_float_bytes_not_json_assertions_drive_parity(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            good=base/"ref.f32"
            actual=base/"gpu.f32"
            good.write_bytes(struct.pack("<3f",1.,2.,3.))
            actual.write_bytes(struct.pack("<3f",1.,2.,3.))
            ok=fp32_compare(good,actual,atol=0.001,rtol=0.0001)
            self.assertEqual(ok["status"],"pass")
            self.assertEqual(ok["compared_fp32_values"],3)
            actual.write_bytes(struct.pack("<3f",1.,2.,4.))
            bad=fp32_compare(good,actual,atol=0.001,rtol=0.0001)
            self.assertEqual(bad["status"],"fail")
            self.assertEqual(bad["outside_tolerance"],1)

    def test_corrupt_nonfinite_and_wrong_size_are_never_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            ref=base/"ref.f32"; gpu=base/"gpu.f32"
            ref.write_bytes(struct.pack("<2f",1.,2.))
            gpu.write_bytes(struct.pack("<1f",1.))
            with self.assertRaisesRegex(QKVAdmissionError,"length"):
                fp32_compare(ref,gpu,atol=.001,rtol=.0001)
            gpu.write_bytes(struct.pack("<2f",math.nan,2.))
            with self.assertRaisesRegex(QKVAdmissionError,"nonfinite"):
                fp32_compare(ref,gpu,atol=.001,rtol=.0001)

    def make_trace(self, base, arm="on", symbol="gfx803_sgemm_gfx803"):
        p=base/arm/"profiler"
        p.mkdir(parents=True)
        with (p/"demo_marker_api_trace.csv").open("w",newline="") as f:
            c=csv.DictWriter(f,fieldnames=("Function","Start_Timestamp","End_Timestamp"))
            c.writeheader()
            c.writerow({"Function":"leech:qkv:sgemm-shim:"+arm,
                        "Start_Timestamp":100,"End_Timestamp":200})
        with (p/"demo_kernel_trace.csv").open("w",newline="") as f:
            c=csv.DictWriter(f,fieldnames=("Kernel_Name","Start_Timestamp","End_Timestamp"))
            c.writeheader()
            c.writerow({"Kernel_Name":symbol,"Start_Timestamp":120,"End_Timestamp":140})
        return p

    def test_real_marker_and_kernel_CSV_reopened(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.make_trace(root)
            self.assertEqual(actual_profiler_kernels(root/"on/profiler","on"),
                             {"gfx803_sgemm_gfx803"})
            with self.assertRaisesRegex(QKVAdmissionError,"ROCTX"):
                actual_profiler_kernels(root/"on/profiler","off")

    def test_reported_kernel_without_CSV_is_not_proof(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"on/profiler").mkdir(parents=True)
            with self.assertRaisesRegex(QKVAdmissionError,"ROCTX"):
                actual_profiler_kernels(root/"on/profiler","on")

    def test_staging_refuses_to_fabricate_missing_raw_GPU_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            (base/"source").mkdir()
            (base/"fixture").mkdir()
            with self.assertRaisesRegex(QKVAdmissionError,"cannot stage"):
                stage_original_evidence(base/"source",base/"fixture",base/"evidence")

    def test_arbitrary_non_store_root_rejected_before_false_admission(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            with self.assertRaisesRegex(QKVAdmissionError,"Nix-store"):
                verify_bundle(base,expected_rocm_root=base)

    def test_leech_claim_is_optional_but_not_self_attesting(self):
        self.assertIn("leech_qkv",CAPABILITY_GATES)
        self.assertEqual(CAPABILITY_GATES["leech_qkv"],("leech_qkv_original",))
        # A self-asserted pass without an actual evidence directory cannot
        # pass strict claim validation, even with other unrelated green flags.
        # Checking source contract rather than inventing a valid 10.1 fixture.
        from inspect import getsource
        src=getsource(validate_candidate)
        self.assertIn('verify_bundle(',src)
        self.assertIn('leech_qkv: source byte or profiler verification failed',src)


if __name__=="__main__":
    unittest.main()
