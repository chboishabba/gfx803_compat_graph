import tempfile
import unittest
from pathlib import Path

from benchmark_schema import append_jsonl, build_benchmark_record, classify_status, parse_drift_metrics


class BenchmarkSchemaTests(unittest.TestCase):
    def test_parse_drift_metrics(self):
        text = "ITER 001: DRIFT 1.500000e-01\nITER 003: DRIFT 2.500000e-02\n"
        metrics = parse_drift_metrics(text)
        self.assertEqual(metrics["drift_count"], 2)
        self.assertAlmostEqual(metrics["max_drift"], 0.15)
        self.assertEqual(metrics["first_drift_iter"], 1)

    def test_classify_status(self):
        self.assertEqual(classify_status(0, {"drift_count": 0, "max_drift": 0.0}), "pass")
        self.assertEqual(classify_status(0, {"drift_count": 1, "max_drift": 0.1}), "partial")
        self.assertEqual(classify_status(139, {"drift_count": 0, "max_drift": 0.0}), "crash")
        self.assertEqual(classify_status(None, {"drift_count": 0, "max_drift": 0.0}), "hang")

    def test_append_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            record = build_benchmark_record(
                stack_id="stack",
                reference_class="reference",
                runtime_family="rocm64_patched",
                workload="bug_report_mre",
                profile="default",
                runtime_source="itir",
                started_at=1.0,
                finished_at=2.0,
                returncode=0,
                log_file=Path(tmp) / "default.log",
                final_json=None,
                metrics={"drift_count": 0, "max_drift": 0.0, "min_drift": 0.0, "mean_drift": 0.0, "first_drift_iter": None},
            )
            append_jsonl(path, record)
            self.assertIn('"stack_id": "stack"', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
