"""No-GPU regression tests for exact-library ROCm ELF symbol inventory."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/gfx803_rocm_abi_inventory.py"
spec=importlib.util.spec_from_file_location("gfx803_rocm_abi_inventory",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ABIInventoryTests(unittest.TestCase):
    def test_library_mapping_only_exact_sonames(self):
        self.assertEqual(m.identify_lib("librocblas.so"),
                         ("rocblas-hipblas","librocblas"))
        self.assertEqual(m.identify_lib("librocsolver.so.0"),
                         ("rocsolver-rocsparse","librocsolver"))
        self.assertIsNone(m.identify_lib("librocblas-extra.so"))
        self.assertIsNone(m.identify_lib("libtorch.so"))

    def test_missing_libs_are_empty_not_capabilities(self):
        with tempfile.TemporaryDirectory() as d:
            matches=m.discover(Path(d))
            self.assertEqual(matches["librocblas"],[])
            self.assertEqual(matches["libamdhip64"],[])

    def test_collision_is_not_arbitrarily_selected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"a").mkdir()
            (root/"b").mkdir()
            (root/"a/librocblas.so").write_bytes(b"not a real ELF")
            (root/"b/librocblas.so.0").write_bytes(b"also not real")
            matches=m.discover(root)
            self.assertEqual(len(matches["librocblas"]),2)

    def test_byte_identical_version_aliases_are_one_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            lib=root/"librocsolver.so.0"
            lib.write_bytes(b"same binary under two SONAME aliases")
            (root/"librocsolver.so.0.12").write_bytes(lib.read_bytes())
            matches=m.discover(root)
            self.assertEqual(matches["librocsolver"],[str(lib)])

    def test_symbols_do_not_claim_public_api(self):
        self.assertIn("rocPRIM",m.HEADER_ONLY)
        self.assertIn("triton",m.NO_ELF_LIBRARY)
        with self.assertRaises(ValueError):
            m.executable(Path("/usr/bin/nm"))

    def test_source_compiles(self):
        compile(SRC.read_text(),str(SRC),"exec")

if __name__=="__main__":unittest.main()
