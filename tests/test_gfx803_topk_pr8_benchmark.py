"""CPU-only contracts for the fault-contained PR #8 benchmark scheduler."""
from __future__ import annotations

import importlib.util
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
