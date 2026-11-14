"""CPU-only compilation/execution of the standalone GFX8 C1b behavioural model.

No HIP/ROCm/GPU is loaded. The model deliberately does not patch Linux.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "gfx803_kfd_c1b_mock.c"


class TestKfdC1bMock(unittest.TestCase):
    def test_compile_and_seven_contracts(self):
        cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if cc is None:
            self.skipTest("C compiler unavailable; no model execution claim")
        with tempfile.TemporaryDirectory(prefix="gfx803-c1b-") as tempdir:
            target = Path(tempdir) / "mock"
            compile_cmd = [cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                           "-pedantic", "-O2", str(SOURCE), "-o", str(target)]
            compile_result = subprocess.run(compile_cmd, capture_output=True,
                                            text=True, timeout=30)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run([str(target)], capture_output=True,
                                    text=True, timeout=10,
                                    env={"PATH": os.environ.get("PATH", "")})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("7/7 PASS", result.stdout)
            self.assertIn("kernel/hardware unqualified", result.stdout)


if __name__ == "__main__":
    unittest.main()
