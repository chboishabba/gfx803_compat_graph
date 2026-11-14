"""CPU-only synthetic postmortem tests; no GPU, kernel tracing or profiler."""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location(
    "gfx803_one_shot_postmortem", SCRIPTS / "gfx803_one_shot_postmortem.py")
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def store(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj) + "\n")


class OneShotPostmortemTests(unittest.TestCase):
    def receipt(self, root):
        store(root / "preflight.json", {"armed": True, "one_shot": True})
        store(root / "child-events.jsonl",
              {"event": "pre_gpu_dispatch",
               "runtime": {"libtorch_hip_sha256": MOD.EXPECTED_LIB_SHA}})
        (root / "kernel-follow.log").write_text(
            "Nov 15 08:00:01 ring gfx timeout\n"
            "Nov 15 08:00:02 Failed to quiesce KFD\n"
            "Nov 15 08:00:02 ring kiq_0.2.1.0 test failed (-110)\n")
        prof = root / "rocprof"
        prof.mkdir()
        (prof / "101_kernel_trace.csv").write_text(
            "Kernel_Name,Grid_Size,Queue_Id,Start_Timestamp,End_Timestamp\n"
            "mbtopk_case4,32,5,100,\n")
        return root

    def test_full_synthetic_join_without_promotion_to_first_stall(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.receipt(Path(d))
            kfd = root / "kfd.jsonl"
            kfd.write_text(
                '{"event":"kfd_probe_start","monotonic_ns":1}\n'
                '{"event":"fence_wait_return","monotonic_ns":20,"return_code":-62}\n'
                '{"event":"unmap_return","monotonic_ns":25,"return_code":-62}\n')
            result = MOD.analyze(root, kfd_path=kfd)
            self.assertEqual(result["gates"]["original_nix_binary_match"], "verified-child")
            self.assertEqual(result["gates"]["new_run_first_kfd_return"], "observed")
            self.assertEqual(result["first_kfd_return_in_captured_stream"]["return_code"], -62)
            self.assertEqual(result["gates"]["new_run_kernel_dispatch_metadata"],
                             "records-present-not-first-stall-proof")
            self.assertEqual(result["gates"]["first_stalled_gpu_instruction"], "open")
            self.assertEqual(result["first_recorded_gpu_issue"]["ring"], "gfx")
            self.assertEqual(result["gpu_commands"], 0)

    def test_no_profiler_and_no_kfd_stay_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.receipt(Path(d))
            (root / "rocprof" / "101_kernel_trace.csv").unlink()
            res = MOD.analyze(root)
            self.assertEqual(res["gates"]["new_run_first_kfd_return"], "not-captured")
            self.assertEqual(res["gates"]["new_run_kernel_dispatch_metadata"], "not-captured")
            self.assertEqual(res["gates"]["SVM_two_range_invalidation"], "open-not-captured")

    def test_reject_wrong_libtorch_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.receipt(Path(d))
            store(root / "child-events.jsonl",
                  {"event": "pre_gpu_dispatch",
                   "runtime": {"libtorch_hip_sha256": "wrong"}})
            with self.assertRaisesRegex(ValueError, "different GPU library"):
                MOD.analyze(root)

    def test_reject_unarmed_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.receipt(Path(d))
            store(root / "preflight.json", {"armed": False, "one_shot": True})
            with self.assertRaisesRegex(ValueError, "not an armed"):
                MOD.analyze(root)

    def test_malformed_jsonl_preserves_partial_capture_warning(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.receipt(Path(d))
            with (root / "child-events.jsonl").open("a") as f:
                f.write('{"event":"truncated"\n')
            res = MOD.analyze(root)
            self.assertTrue(any("invalid or partial" in x for x in res["parse_warnings"]))

    def test_csv_missing_completion_is_not_stall_proof(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.receipt(Path(d))
            rec = MOD.rocprof_summary(root / "rocprof")
            self.assertEqual(rec["status"], "kernel-records-captured")
            self.assertIn("not prove first stalled", rec["dispatch_causality"])

    def test_no_receipt_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "no armed preflight"):
                MOD.analyze(Path(d))


if __name__ == "__main__":
    unittest.main()
