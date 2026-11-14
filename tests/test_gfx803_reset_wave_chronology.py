"""Offline unit tests for GFX8 reset waves, including reported success followed by faults."""
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gfx803_reset_wave_chronology.py"
SPEC = importlib.util.spec_from_file_location("gfx803_wave", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def line(clock: str, msg: str) -> str:
    return f"Nov 14 {clock} testhost kernel: amdgpu 0000:01:00.0: {msg}"


class ResetWaveTests(unittest.TestCase):
    def test_transient_reported_success_then_vm_fault(self):
        data = [
            line("12:39:28", "Failed to quiesce KFD"),
            line("12:39:29", "ring kiq_0.2.1.0 test failed (-110)"),
            line("12:39:29", "BACO reset"),
            line("12:39:30", "GPU reset(2) succeeded!"),
            line("12:39:32", "ring gfx timeout, but soft recovered"),
            line("12:39:32", "VM fault (0x01, vmid 7, pasid 7) at page 123"),
        ]
        r = MODULE.analyse(data)
        self.assertEqual(r["key_findings"]["first_kiq_failure"]["clock"], "2026-11-14T12:39:29")
        self.assertEqual(r["key_findings"]["first_baco"]["clock"], "2026-11-14T12:39:29")
        self.assertEqual(len(r["reset_successes"]), 1)
        self.assertTrue(r["reset_successes"][0]["post_success_fault_within_window"])
        self.assertEqual(r["key_findings"]["success_then_fault_count"], 1)
        self.assertTrue(r["no_gpu_executed"])

    def test_no_fault_after_success_is_not_physical_acceptance(self):
        r = MODULE.analyse([line("12:39:29", "BACO reset"),
                            line("12:39:30", "GPU reset(2) succeeded!")])
        self.assertEqual(r["key_findings"]["success_then_fault_count"], 0)
        self.assertIn("never proves", r["key_findings"]["note"])

    def test_unrelated_traffic_and_malformed_time_are_ignored(self):
        r = MODULE.analyse(["[UFW BLOCK]", "Nov 41 13:00:00 bad: GPU reset(1) succeeded!",
                            line("12:39:30", "GPU reset(2) succeeded!")])
        self.assertEqual(r["event_count"], 1)

    def test_window_is_bounded(self):
        data = [line("12:39:30", "GPU reset(2) succeeded!"),
                line("12:41:00", "ring gfx timeout")]
        self.assertFalse(MODULE.analyse(data, horizon=10)["reset_successes"][0]["post_success_fault_within_window"])
        self.assertTrue(MODULE.analyse(data, horizon=120)["reset_successes"][0]["post_success_fault_within_window"])

    def test_cli_refuses_overwrite_and_does_not_use_gpu(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            journal = root / "journal.log"
            output = root / "out.json"
            journal.write_text(line("12:39:30", "GPU reset(2) succeeded!") + "\n")
            cmd = [sys.executable, str(SCRIPT), "--journal", str(journal), "--output", str(output)]
            first = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn('"reported_successes": 1', first.stdout)
            second = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            self.assertEqual(second.returncode, 2)
            self.assertIn("refuse to overwrite", second.stderr)


if __name__ == "__main__":
    unittest.main()
