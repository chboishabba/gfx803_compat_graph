"""Synthetic source-contract tests: NEVER physical gfx803 admission."""
import unittest

from scripts.gfx803_lila_two_lane_receipts import adjudicate


def common_gate(hip="10.1"):
    return {
        "gpu": {"gcn_arch_name": "gfx803"},
        "torch_hip": hip,
        "source_sha256": {"teacher": "a"*64, "student": "b"*64, "train": "c"*64},
        "checks_result": {
            "stage": "complete", "checks": {
                "dense_cpu_gpu_logits": {"passed": True},
                "focused_training_gradients": {"passed": True},
                "post_optimizer_step_logits": {"passed": True}}},
        "admitted": True,
    }


def shim_evidence(gate):
    meta={"shim_mapped":True,"shim_enabled":True,"shim_sha256":"d"*64,
          "shim_path":"/nix/store/abc-rocm/lib/libgfx803_sgemm_shim.so",
          "selected_rocm_root":"/nix/store/abc-rocm"}
    gate["shim_runtime_before"]=meta
    gate["shim_runtime_after"]=meta.copy()
    summary={"status":"supports-scoped-interposer-effect",
             "shim_effect_at_original_QKV_shape":True,
             "both_traces_complete_and_observer_effect_free":True,
             "actual_interposer_kernel_discrimination":True,
             "same_library_shim_fixture_and_numeric_identity":True}
    arm={"teacher_sha256":"a"*64,"shim_sha256":"d"*64,
         "shim_realpath":meta["shim_path"],
         "required_image_root":meta["selected_rocm_root"],"torch_hip":"10.1"}
    return summary, arm, arm.copy()


class DualLaneAdjudicationTests(unittest.TestCase):
    def test_64_hybrid_is_never_training_admitted(self):
        gate=common_gate("6.4")
        gate["admitted"]=False
        gate["gate_only_hybrid"]=True
        gate["linear_repair"]={
            "kind":"cpu-fp32-linear-diagnostic","installed":True,
            "gpu_linear_calls_repaired":20,
            "training_admission":"denied","full_gpu_execution":False}
        got=adjudicate("6.4-cpu-linear",gate)
        self.assertTrue(got["numerical_hybrid_diagnostic_passed"])
        self.assertFalse(got["training_admitted"])
        self.assertEqual(got["gpu_native_correctness"],"not-established")

    def test_64_no_repaired_calls_is_rejected(self):
        gate=common_gate("6.4")
        gate["linear_repair"]={"kind":"cpu-fp32-linear-diagnostic",
                               "installed":True,"gpu_linear_calls_repaired":0,
                               "training_admission":"denied","full_gpu_execution":False}
        self.assertFalse(adjudicate("6.4-cpu-linear",gate)
                         ["numerical_hybrid_diagnostic_passed"])

    def test_101_candidate_still_not_release(self):
        gate=common_gate()
        summary,on,off=shim_evidence(gate)
        got=adjudicate("10.1-schaka",gate,summary=summary,on=on,off=off)
        self.assertTrue(got["numerical_candidate_supported"])
        self.assertFalse(got["training_admitted"])
        self.assertFalse(got["release_accepted"])

    def test_101_rejects_wrong_teacher(self):
        gate=common_gate()
        summary,on,off=shim_evidence(gate)
        on["teacher_sha256"]="x"*64
        got=adjudicate("10.1-schaka",gate,summary=summary,on=on,off=off)
        self.assertFalse(got["numerical_candidate_supported"])

    def test_101_rejects_missing_trace(self):
        gate=common_gate()
        summary,on,off=shim_evidence(gate)
        got=adjudicate("10.1-schaka",gate,summary=None,on=on,off=off)
        self.assertFalse(got["numerical_candidate_supported"])

    def test_101_rejects_missing_optimizer_evidence(self):
        gate=common_gate()
        gate["checks_result"]["checks"]["post_optimizer_step_logits"]["passed"]=False
        summary,on,off=shim_evidence(gate)
        got=adjudicate("10.1-schaka",gate,summary=summary,on=on,off=off)
        self.assertFalse(got["numerical_candidate_supported"])


if __name__ == "__main__":
    unittest.main()
