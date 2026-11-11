"""Offline contracts: reuse pinned upstream tests, never forge hardware evidence."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

def import_script(name):
    p=ROOT/"scripts"/(name+".py")
    spec=importlib.util.spec_from_file_location(name,p)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ops=import_script("gfx803_upstream_assay")
inventory=import_script("gfx803_upstream_inventory")

class UpstreamReuseTests(unittest.TestCase):
    def test_actual_generated_cuda_ids_only(self):
        s=("test/test_ops.py::TestCommonCUDA::test_compare_cpu_cuda_float32_torch_add\n"
           "test/test_ops.py::TestCommonCPU::test_compare_cpu_cpu_float32\n"
           "test/test_ops.py::TestCommonCUDA::test_variant_consistency_eager_cuda_float16_torch_mul\n"
           "12000 tests collected\n")
        self.assertEqual(len(ops.ids_from_collection(s)),2)

    def test_crashes_and_skips_are_not_passes(self):
        self.assertEqual(ops.classify(0,"1 passed"),"pass")
        self.assertEqual(ops.classify(-6,""),"fault")
        self.assertEqual(ops.classify(137,""),"fault")
        self.assertEqual(ops.classify(1,"1 failed"),"fail")
        self.assertEqual(ops.classify(0,"1 skipped"),"unsupported")
        self.assertEqual(ops.classify(0,"1 xfailed"),"unsupported")
        self.assertEqual(ops.classify(0,"1 xpassed"),"unsupported")
        self.assertEqual(ops.classify(1,"1 skipped"),"fail")

    def test_refuse_missing_source(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):ops.check_source(Path(d))

    def test_refuse_host_runtime(self):
        with self.assertRaises(ValueError):
            ops.check_runtime(Path("/bin/python3"),Path("/opt/rocm"))

    def test_atomic_evidence_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"matrix.json"
            ops.persist(p,{"status":"unassayed"})
            self.assertIn("unassayed",p.read_text())
            self.assertFalse(p.with_suffix(".json.tmp").exists())

    def test_upstream_inventory_does_not_claim_hardware(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for origin,rel,_ in inventory.ASSETS.values():
                f=root/origin/rel;f.parent.mkdir(parents=True,exist_ok=True)
                f.write_text("test source")
            with patch.object(inventory,"pinned",side_effect=lambda path,rev:path):
                row=inventory.inventory(root/"schaka",root/"pytorch")
            self.assertEqual(len(row["assets"]),9)
            self.assertFalse(row["gpu_validated"])
            self.assertFalse(row["release_admitted"])
            self.assertTrue(all(x["status"]=="source-present-unexecuted"
                                for x in row["assets"].values()))

    def test_source_contracts_are_syntax_valid(self):
        for name in ("gfx803_upstream_assay","gfx803_upstream_inventory"):
            path=ROOT/"scripts"/(name+".py")
            compile(path.read_text(),str(path),"exec")

if __name__=="__main__":unittest.main()
