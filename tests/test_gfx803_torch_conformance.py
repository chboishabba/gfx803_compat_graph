"""CPU-only source and receipt contracts for isolated gfx803 operator matrix."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/gfx803_torch_conformance.py"
spec = importlib.util.spec_from_file_location("gfx803_torch_conformance", MODULE)
assay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assay)


class ConformanceContracts(unittest.TestCase):
    def test_source_compiles_without_importing_torch(self):
        compile(MODULE.read_text(), str(MODULE), "exec")

    def test_registry_spans_all_core_families(self):
        self.assertEqual(len(assay.CASES), len(set(assay.CASES)))
        for family in ("core", "normalization", "reduction", "linear",
                       "selection", "indexing", "nn", "optimizer"):
            self.assertIn(family, assay.CASES.values())

    def test_known_vm_fault_never_runs_without_optin(self):
        self.assertIn("topk_2x4_k2", assay.KNOWN_FAULTS)
        code = MODULE.read_text()
        self.assertIn("not args.include_known_faults", code)
        self.assertIn('and not args.continue_after_fault', code)
        self.assertIn("subprocess.run(", code)
        self.assertIn("timeout=args.timeout", code)

    def test_no_gpu_training_or_release_promotion(self):
        matrix = {"cases": {k: {"status": "pass"} for k in assay.CASES}}
        result = assay.verdict(matrix)
        self.assertTrue(result["all_cases_pass"])
        self.assertFalse(result["training_admitted"])
        self.assertFalse(result["cachix_release_admitted"])
        matrix["cases"]["topk_2x4_k2"]["status"] = "unassayed"
        self.assertFalse(assay.verdict(matrix)["all_cases_pass"])

    def test_missing_case_or_unknown_status_rejected(self):
        matrix = {"cases": {k: {"status": "pass"} for k in assay.CASES}}
        matrix["cases"].pop("topk_2x4_k2")
        with self.assertRaises(ValueError):
            assay.verdict(matrix)
        matrix["cases"]["topk_2x4_k2"] = {"status": "promoted"}
        with self.assertRaises(ValueError):
            assay.verdict(matrix)

    def test_atomic_receipt_replaces_without_temp_file(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "matrix.json"
            assay.atomically_write(path, {"a": 1})
            self.assertEqual(json.loads(path.read_text()), {"a": 1})
            self.assertFalse((Path(t) / "matrix.json.tmp").exists())

    def test_cli_requires_pinned_absolute_nix_root(self):
        p = subprocess.run([sys.executable, str(MODULE), "--rocm-root", "."],
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("absolute", p.stderr)


if __name__ == "__main__":
    unittest.main()
