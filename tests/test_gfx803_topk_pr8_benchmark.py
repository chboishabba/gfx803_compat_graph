"""CPU-only contracts for the fault-contained PR #8 benchmark scheduler."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "gfx803_topk_pr8_benchmark.py"
SPEC = importlib.util.spec_from_file_location("topk_bench", MODULE_PATH)
assert SPEC and SPEC.loader
BENCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCH)


class TopKBenchmarkSchedulingTests(unittest.TestCase):
    def test_known_faults_are_not_scheduled(self) -> None:
        self.assertEqual(
            BENCH.planned_cases({0, 1, 4}),
            (3, 5, 6, 7, 8, 2),
        )

    def test_unknown_skip_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BENCH.planned_cases({99})

    def test_default_excludes_historic_fault_cases(self) -> None:
        self.assertEqual(BENCH.planned_cases(set()), (3, 5, 6, 7, 8, 2))
        self.assertEqual(BENCH.HAZARDOUS_CASES, frozenset((0, 1, 4)))

    def test_explicit_safehost_allowlist_is_still_filterable(self) -> None:
        self.assertEqual(BENCH.planned_cases(set(), allow_hazardous=True), BENCH.ORDER)
        self.assertEqual(BENCH.planned_cases({4}, allow_hazardous=True),
                         (3, 5, 6, 7, 8, 1, 2, 0))

    def test_receipt_requires_every_recovery_prerequisite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "safehost.json"
            valid = {"schema": 1, **{key: True for key in BENCH.SAFE_HOST_FIELDS}}
            path.write_text(json.dumps(valid))
            self.assertEqual(BENCH.validate_safe_host_receipt(path), valid)
            for field in BENCH.SAFE_HOST_FIELDS:
                invalid = dict(valid)
                invalid[field] = False
                path.write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    BENCH.validate_safe_host_receipt(path)
            path.write_text("not json")
            with self.assertRaises(ValueError):
                BENCH.validate_safe_host_receipt(path)

    def test_missing_safehost_receipt_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            BENCH.validate_safe_host_receipt(Path("/nonexistent/gfx803_safehost.json"))

    def test_direct_fault_case_refused_before_torch_import(self) -> None:
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--case", "4"],
            text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("independently recoverable safe host", result.stderr)

    def test_auto_recovery_refused_without_gpu_work(self) -> None:
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--recover-after-fault"],
            text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("automatic healthcheck/continuation", result.stderr)


if __name__ == "__main__":
    unittest.main()
