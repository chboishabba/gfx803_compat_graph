"""Pure offline regression checks for complex unary fault isolation."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

SRC=Path(__file__).resolve().parents[1]/"scripts/gfx803_complex_unary_fault_probe.py"
spec=importlib.util.spec_from_file_location("gfx803_complex_unary_fault_probe",SRC)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ComplexUnaryProbeTests(unittest.TestCase):
    def test_four_fault_candidates_are_explicit(self):
        self.assertTrue({"acos","acosh","asin","asinh"}.issubset(set(mod.OPS)))
        self.assertIn("complex64-contiguous",mod.PROFILES)
        self.assertIn("complex64-strided",mod.PROFILES)
        self.assertIn("complex128-contiguous",mod.PROFILES)
        self.assertIn("float32-contiguous",mod.PROFILES)

    def test_inputs_and_strides_are_generated_by_original_torch(self):
        torch=MagicMock()
        torch.complex64="c64"
        torch.complex128="c128"
        torch.float32="f32"
        mod.sample(torch,"complex64-contiguous")
        torch.tensor.assert_called()
        kwargs=torch.tensor.call_args.kwargs
        self.assertEqual(kwargs["dtype"],"c64")

    def test_source_contains_explicit_execution_gate(self):
        source=SRC.read_text()
        self.assertIn("if not a.execute:",source)
        self.assertIn("interrupted",source)
        self.assertIn("subprocess.run",source)
        self.assertIn("release_admitted",source)

    def test_compile(self):
        compile(SRC.read_text(),str(SRC),"exec")

if __name__=="__main__":unittest.main()
