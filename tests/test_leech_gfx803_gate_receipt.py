"""Source-first negative Leech gate cannot be promoted to ROCm compatibility."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))

from classify_leech_gfx803_gate import (
    KNOWN_CONTROL_SHA256, InvalidObservation, classify_gate, sha256_file)

SOURCE=ROOT/"docs/receipts/leech_gfx803_rocm64_dense_parity_rejected_20261104.json"


class LeechGfx803GateReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt=json.loads(SOURCE.read_text())

    def test_locked_original_bytes_and_exact_source_identity(self):
        self.assertEqual(sha256_file(SOURCE),KNOWN_CONTROL_SHA256)
        verdict=classify_gate(self.receipt)
        self.assertEqual(verdict["status"],"observed_rejection")
        self.assertFalse(verdict["dense_cpu_gpu_numerically_admissible"])
        self.assertFalse(verdict["dense_same_device_repeatable"])
        self.assertFalse(verdict["c2_forward_executed_in_gate"])
        self.assertFalse(verdict["c2_gradients_executed_in_gate"])
        self.assertFalse(verdict["training_authorized_by_gate"])
        self.assertTrue(verdict["not_a_schaka_10_1_result"])
        self.assertEqual(verdict["teacher_checkpoint_sha256"],
                         "581fdc3b4b6d169a03e2b06896e10d454fd4f819b40a2836c1d5b76849e4c674")
        self.assertEqual(verdict["student_candidate_sha256"],
                         "f26a5d9246bd0e1f89330b4864124835e3df82bb86e4d1da23fdf5fb3c09224c")
        self.assertAlmostEqual(verdict["dense_logits_max_abs_diff"],28.557292938232422)
        self.assertAlmostEqual(verdict["dense_repeat_max_abs_diff"],0.23707842826843262)

    def test_never_promote_admission_true_or_missing_negative_stage(self):
        tampered=copy.deepcopy(self.receipt)
        tampered["admitted"]=True
        with self.assertRaises(InvalidObservation):
            classify_gate(tampered)
        tampered=copy.deepcopy(self.receipt)
        tampered["checks_result"]["stage"]="complete"
        with self.assertRaises(InvalidObservation):
            classify_gate(tampered)

    def test_never_confuse_missing_or_false_positive_checks(self):
        tampered=copy.deepcopy(self.receipt)
        del tampered["checks_result"]["checks"]["dense_gpu_repeat_1"]
        with self.assertRaises(InvalidObservation):
            classify_gate(tampered)
        tampered=copy.deepcopy(self.receipt)
        tampered["checks_result"]["checks"]["dense_cpu_gpu_logits"]["passed"]=True
        with self.assertRaises(InvalidObservation):
            classify_gate(tampered)
        tampered=copy.deepcopy(self.receipt)
        tampered["checks_result"]["checks"]["teacher_layer_input"]["max_abs_diff"]=0
        with self.assertRaises(InvalidObservation):
            classify_gate(tampered)

    def test_student_only_absence_is_an_explicit_boundary(self):
        tampered=copy.deepcopy(self.receipt)
        tampered["checks_result"]["checks"]["focused_cpu_gpu_logits"]={
            "passed":False,"max_abs_diff":1.,"max_allowed_error":.01}
        with self.assertRaises(InvalidObservation):
            classify_gate(tampered)


if __name__=="__main__":
    unittest.main()
