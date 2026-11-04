import tempfile
import unittest
from pathlib import Path

from scripts.audit_gfx803_closure import audit_roots, parse_dynamic


class ClosureAuditTests(unittest.TestCase):
    def test_dynamic_parser(self):
        line = """ 0x0000000000000001 (NEEDED) Shared library: [librocblas.so.5]
 0x000000000000000e (SONAME) Library soname: [libtest.so]
 0x000000000000001d (RUNPATH) Library runpath: [/opt/rocm/lib:$ORIGIN]
"""
        result = parse_dynamic(line)
        self.assertEqual(result["NEEDED"], ["librocblas.so.5"])
        self.assertEqual(result["RUNPATH"], ["/opt/rocm/lib:$ORIGIN"])

    def test_absolute_and_dangling_symlinks_are_hazards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad").symlink_to("/opt/rocm/core-10.1/lib/test.so")
            report = audit_roots([root])
            kinds = [x["kind"] for x in report["hazards"]]
            self.assertIn("absolute-symlink", kinds)
            self.assertIn("dangling-symlink", kinds)
            self.assertFalse(report["passed_static_screen"])
            self.assertEqual(report["admission"], "not-established-by-static-audit")

    def test_empty_root_has_no_hazards_but_no_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = audit_roots([Path(tmp)])
            self.assertEqual(report["hazards"], [])
            self.assertEqual(report["elf_count"], 0)
            self.assertNotEqual(report["admission"], "accepted")


if __name__ == "__main__":
    unittest.main()
