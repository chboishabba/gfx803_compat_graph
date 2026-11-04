import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.gfx803_capture import assess_diffusion_log, capture
from scripts.gfx803_release import load, write


class HardwareReceiptCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.candidate = self.root / "candidate.json"
        self.logs = self.root / "logs"
        write(self.candidate, {"schema_version": 1,
                               "state": "candidate", "evidence": {}})

    def fixture(self, statuses):
        tests = {name: {"status": state}
                 for name, state in enumerate(statuses)}
        summary = {"total": len(tests),
                   "passed": sum(s == "pass" for s in statuses),
                   "tests": tests}
        return "PROBE_JSON:" + json.dumps(summary)

    def test_rejects_historical_six_of_seven_even_with_exit_zero(self):
        text = self.fixture(["pass"] * 6 + ["fail_nondeterministic"])
        entry, ok = capture(self.candidate, self.logs, "numerical_correctness",
                            [sys.executable, "-c", "print(" + repr(text) + ")"],
                            expect_diffusion=True)
        self.assertFalse(ok)
        self.assertEqual(entry["status"], "fail")
        self.assertEqual(entry["return_code"], 0)
        self.assertIn("partial diffusion test pass", entry["reason"])
        self.assertTrue((self.logs / entry["log_path"]).exists())
        self.assertEqual(load(self.candidate)["evidence"]["numerical_correctness"],
                         entry)

    def test_accepts_complete_structured_probe(self):
        text = self.fixture(["pass"] * 7)
        entry, ok = capture(self.candidate, self.logs, "numerical_correctness",
                            [sys.executable, "-c", "print(" + repr(text) + ")"],
                            expect_diffusion=True)
        self.assertTrue(ok)
        self.assertEqual(entry["status"], "pass")

    def test_rejects_missing_structured_probe(self):
        entry, ok = capture(self.candidate, self.logs, "numerical_correctness",
                            [sys.executable, "-c", "print('nothing')"],
                            expect_diffusion=True)
        self.assertFalse(ok)
        self.assertIn("expected one PROBE_JSON", entry["reason"])

    def test_nonzero_process_never_passes(self):
        text = self.fixture(["pass"] * 7)
        entry, ok = capture(self.candidate, self.logs, "numerical_correctness",
                            [sys.executable, "-c",
                             "print(" + repr(text) + "); raise SystemExit(1)"],
                            expect_diffusion=True)
        self.assertFalse(ok)
        self.assertEqual(entry["return_code"], 1)

    def test_literal_gpu_arch_expectation(self):
        cmd = [sys.executable, "-c", "print('AMD gfx803')"]
        entry, ok = capture(self.candidate, self.logs, "gpu_enumeration",
                            cmd, expect_text=["gfx803"])
        self.assertTrue(ok)
        entry, ok = capture(self.candidate, self.logs, "gpu_enumeration",
                            cmd, expect_text=["gfx900"])
        self.assertFalse(ok)
        self.assertIn("gfx900", entry["reason"])

    def test_rejects_unknown_gate_and_non_candidate(self):
        from scripts.gfx803_release import AdmissionError
        with self.assertRaises(AdmissionError):
            capture(self.candidate, self.logs, "not_real_gate", ["true"])
        write(self.candidate, {"state": "accepted"})
        with self.assertRaises(AdmissionError):
            capture(self.candidate, self.logs, "gpu_enumeration", ["true"])


if __name__ == "__main__":
    unittest.main()
