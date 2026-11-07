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
            self.assertIn("no-elf-files", [h["kind"] for h in report["hazards"]])
            self.assertEqual(report["elf_count"], 0)
            self.assertNotEqual(report["admission"], "accepted")

    def test_missing_nonrocm_needed_requires_declared_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "rocm"
            root.mkdir()
            provider = base / "nix-providers"
            provider.mkdir()
            (root / "libconsumer.so").write_bytes(b"\x7fELF" + b"\0" * 20)
            (provider / "libnixsystem.so.1").write_bytes(b"\x7fELF" + b"\0" * 20)
            reader = base / "mock-readelf"
            reader.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "if sys.argv[-1].endswith('libnixsystem.so.1'):\n"
                " print(' 0x0 (SONAME) Library soname: [libnixsystem.so.1]')\n"
                "else:\n"
                " print(' 0x0 (SONAME) Library soname: [libconsumer.so]')\n"
                " print(' 0x1 (NEEDED) Shared library: [libnixsystem.so.1]')\n"
            )
            reader.chmod(0o755)
            missing = audit_roots([root], readelf=str(reader))
            self.assertIn("missing-dt-needed",
                          [v["kind"] for v in missing["hazards"]])
            self.assertEqual(missing["unresolved_dt_needed_count"], 1)
            supplied = audit_roots([root], readelf=str(reader),
                                   provider_roots=[provider])
            self.assertEqual(supplied["unresolved_dt_needed_count"], 0)
            self.assertTrue(supplied["passed_static_screen"])

    def test_missing_rocm_library_never_silently_uses_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "libconsumer.so").write_bytes(b"\x7fELF" + b"\0" * 20)
            reader = base / "mock-readelf"
            reader.write_text(
                "#!/usr/bin/env python3\n"
                "print(' 0x1 (NEEDED) Shared library: [librocblas.so.5]')\n"
            )
            reader.chmod(0o755)
            report = audit_roots([base], readelf=str(reader))
            self.assertIn("missing-rocm-soname",
                          [v["kind"] for v in report["hazards"]])


if __name__ == "__main__":
    unittest.main()
