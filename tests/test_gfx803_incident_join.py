"""Offline incident join contract tests; synthetic source records, no GPU work."""
from pathlib import Path
import importlib.util
import json
import tempfile
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/gfx803_incident_join.py"
SPEC = importlib.util.spec_from_file_location("gfx803_join", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class OfflineIncidentJoinTests(unittest.TestCase):
    def write(self, p, text):
        p.write_text(text)
        return p

    def test_original_november_sequence_preserved_with_first_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(Path(d) / "kernel.log", "\n".join((
                "Nov 14 12:39:28 host kernel: ring gfx timeout, signaled seq=1, emitted seq=3",
                "Nov 14 12:39:28 host kernel: Failed to quiesce KFD",
                "Nov 14 12:39:29 host kernel: ring kiq_0.2.1.0 test failed (-110)",
                "Nov 14 12:39:29 host kernel: BACO reset",
                "Nov 14 12:39:30 host kernel: GPU reset(2) succeeded!",
                "Nov 14 12:39:32 host kernel: VM fault (0x01, vmid 7, pasid 7)"
            )))
            o = MOD.join([("topk", p)])
            g = o["gates"]["topk"]
            self.assertEqual(g["first_logged_ring_timeout"]["ring"], "gfx")
            self.assertEqual(g["first_logged_ring_timeout"]["time"],
                             "2026-11-14T12:39:28")
            self.assertEqual(g["first_logged_baco"]["time"], "2026-11-14T12:39:29")
            self.assertEqual(g["first_stalled_dispatch"], "open-not-captured")
            self.assertEqual(g["runtime_svm_registration"], "open-not-captured")
            self.assertEqual(o["gpu_commands"], 0)
            self.assertEqual(sum(x["kind"] == "reset_reported_success"
                                 for x in o["events"]), 1)

    def test_userptr_is_not_svm(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(Path(d) / "march.log",
                           "Mar 20 13:55:28 host kernel: amdgpu: init_user_pages: "
                           "Failed to get user pages: -1\n"
                           "Mar 20 13:55:29 host kernel: ring comp_1.3.1 timeout\n")
            g = MOD.join([("ollama", p)])["gates"]["ollama"]
            self.assertEqual(g["raw_userptr_failures"], 1)
            self.assertEqual(g["first_logged_userptr_failure"]["errno"], "-1")
            self.assertEqual(g["raw_svm_mentions"], 0)
            self.assertEqual(g["two_concurrent_svm_invalidations"],
                             "open-not-captured")

    def test_no_event_not_negative_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(Path(d) / "quiet.log", "Mar 20 13:55:29 host kernel: unrelated\n")
            g = MOD.join([("quiet", p)])["gates"]["quiet"]
            self.assertEqual(g["raw_svm_mentions"], 0)
            self.assertEqual(g["runtime_svm_registration"], "open-not-captured")
            self.assertIsNone(g["first_logged_ring_timeout"])

    def test_benchmark_skip_not_a_success_or_failing_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(Path(d) / "cases.csv",
                           "shape,dtype,k,status,error\n"
                           "32x151936,float32,50,known-fault-skip,excluded\n"
                           "1x151936,float32,50,ok,\n")
            o = MOD.join([("topk", p)])
            cases = [x for x in o["events"] if x["kind"] == "benchmark_case"]
            self.assertEqual([x["status"] for x in sorted(cases, key=lambda x: x["line"])],
                             ["known-fault-skip", "ok"])
            self.assertEqual(len(cases), 2)
            self.assertEqual(o["gates"]["topk"]["first_stalled_dispatch"],
                             "open-not-captured")

    def test_secondary_markdown_does_not_become_kernel_record(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(Path(d) / "incident.md",
                           "Narrative: ring comp_1.3.1 timeout; GPU Hang\n")
            o = MOD.join([("whisper", p)])
            self.assertEqual(o["gates"]["whisper"]["raw_ring_timeout_count"], 0)
            self.assertTrue(any(x["confidence"] == "secondary-report"
                                for x in o["events"]))

    def test_jsonl_stage_trace_and_malformed_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(Path(d) / "events.jsonl",
                           '{"event":"stage_start","stage":"align",'
                           '"timestamp":"2026-03-30T00:41:27+10:00"}\nnot-json\n')
            o = MOD.join([("whisper", p)])
            self.assertEqual(o["events"][0]["event"], "stage_start")
            self.assertEqual(o["events"][0]["time"],
                             "2026-03-30T00:41:27+10:00")
            self.assertTrue(any(x["kind"] == "malformed_jsonl" for x in o["events"]))

    def test_hash_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(Path(d) / "kernel.log",
                           "Nov 14 12:39:29 host kernel: BACO reset\n")
            out = Path(d) / "result.json"
            cmd = [sys.executable, str(SCRIPT), "--input", "topk", str(p),
                   "--out", str(out)]
            first = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            self.assertEqual(first.returncode, 0, first.stderr)
            data = json.loads(out.read_text())
            self.assertEqual(len(data["files"][0]["sha256"]), 64)
            second = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("refuse to overwrite", second.stderr)

    def test_unsupported_input_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(Path(d) / "trace.bin", "x")
            with self.assertRaises(ValueError):
                MOD.join([("topk", p)])


if __name__ == "__main__":
    unittest.main()
