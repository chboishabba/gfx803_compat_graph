"""Offline PASID-specific KFD SVM invalidation witness negative controls."""
from pathlib import Path
import importlib.util
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/gfx803_kfd_event_correlation.py"
SPEC = importlib.util.spec_from_file_location("gfx803_svm_corr", SCRIPT)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def event(name, time, **fields):
    return dict(capture_id="safe-host-a", boot_id="boot-x",
                mm_id="mm-7", pasid=42, monotonic_ns=time, event=name, **fields)


def original():
    return [
        event("svm_range_register", 1, range_id="range-a"),
        event("svm_range_register", 2, range_id="range-b"),
        event("svm_invalidate_enter", 10, range_id="range-a",
              invalidation_id="a", notifier_event="MMU_NOTIFY_MIGRATE",
              xnack_off=True),
        event("kfd_quiesce_begin", 20, quiesce_id="q1"),
        event("svm_invalidate_enter", 25, range_id="range-b",
              invalidation_id="b", notifier_event="MMU_NOTIFY_MIGRATE",
              xnack_off=True),
        event("svm_invalidate_return", 30, range_id="range-b",
              invalidation_id="b", notifier_event="MMU_NOTIFY_MIGRATE",
              xnack_off=True),
        event("kfd_quiesce_end", 40, quiesce_id="q1", return_code=0),
        event("svm_invalidate_return", 50, range_id="range-a",
              invalidation_id="a", notifier_event="MMU_NOTIFY_MIGRATE",
              xnack_off=True),
    ]


class KfdEventCorrelationTests(unittest.TestCase):
    def test_two_distinct_svm_invalidation_overlap(self):
        r = MOD.correlate(original())
        self.assertEqual(r["status"], "overlap-observed")
        self.assertEqual(len(r["witnesses"]), 1)
        self.assertEqual(r["witnesses"][0]["second_return_ns"], 30)
        self.assertEqual(r["witnesses"][0]["quiesce_end_ns"], 40)
        self.assertEqual(r["witnesses"][0]["causal_gpu_hang_attribution"],
                         "not-established")

    def test_serialized_lock_eliminates_overlap(self):
        ev = original()
        for e in ev:
            if e["event"] == "svm_invalidate_enter" and e.get("invalidation_id") == "b":
                e["monotonic_ns"] = 60
            if e["event"] == "svm_invalidate_return" and e.get("invalidation_id") == "b":
                e["monotonic_ns"] = 70
        self.assertFalse(MOD.correlate(ev)["witnesses"])

    def test_unmap_is_not_the_svm_evict_branch(self):
        ev = original()
        for e in ev:
            if e.get("invalidation_id") == "b":
                e["notifier_event"] = "MMU_NOTIFY_UNMAP"
        self.assertFalse(MOD.correlate(ev)["witnesses"])

    def test_different_pasids_cannot_be_joined(self):
        ev = original()
        for e in ev:
            if e.get("invalidation_id") == "b":
                e["pasid"] = 100
        self.assertFalse(MOD.correlate(ev)["witnesses"])

    def test_different_mm_cannot_be_joined(self):
        ev = original()
        for e in ev:
            if e.get("invalidation_id") == "b":
                e["mm_id"] = "mm-8"
        self.assertFalse(MOD.correlate(ev)["witnesses"])

    def test_xnack_on_not_accepted_as_evict_branch(self):
        ev = original()
        for e in ev:
            if e.get("invalidation_id") == "b":
                e["xnack_off"] = False
        self.assertFalse(MOD.correlate(ev)["witnesses"])

    def test_unregistered_svm_range_cannot_be_imagined(self):
        ev = [e for e in original()
              if not (e["event"] == "svm_range_register" and
                      e.get("range_id") == "range-b")]
        self.assertFalse(MOD.correlate(ev)["witnesses"])

    def test_missing_return_is_not_an_overlapping_return(self):
        ev = [e for e in original()
              if not (e["event"] == "svm_invalidate_return" and
                      e.get("invalidation_id") == "b")]
        self.assertFalse(MOD.correlate(ev)["witnesses"])

    def test_quiesce_failure_does_not_become_recovered(self):
        ev = original()
        for e in ev:
            if e["event"] == "kfd_quiesce_end":
                e["return_code"] = -5
        r = MOD.correlate(ev)
        self.assertEqual(r["witnesses"][0]["quiesce_return_code"], -5)
        self.assertEqual(r["causal_attribution"], "unproven")

    def test_cross_boot_mixing_is_fatal(self):
        ev = original()
        ev[-1]["boot_id"] = "boot-y"
        with self.assertRaises(ValueError):
            MOD.correlate(ev)

    def test_duplicate_and_wrong_clock_are_fatal(self):
        ev = original()
        with self.assertRaises(ValueError):
            MOD.correlate(ev + [dict(ev[0])])
        ev = original()
        ev[0]["monotonic_ns"] = "10"
        with self.assertRaises(ValueError):
            MOD.correlate(ev)

    def test_unknown_input_is_not_hardware_proof(self):
        self.assertEqual(MOD.correlate([])["status"], "no-capture")


if __name__ == "__main__":
    unittest.main()
