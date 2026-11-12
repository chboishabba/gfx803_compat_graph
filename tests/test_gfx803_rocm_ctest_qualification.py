"""Offline contracts for ten-layer reuse-first ROCm CTest qualification."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/"scripts/gfx803_rocm_ctest_qualification.py"
spec=importlib.util.spec_from_file_location("gfx803_rocm_ctest_qualification",FILE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ROCmQualificationTests(unittest.TestCase):
    def test_catalog_all_ten_layers_and_no_release(self):
        doc=json.loads((ROOT/"qualification/rocm_layers_v1.json").read_text())
        ids=[r["id"] for r in doc["layers"]]
        self.assertEqual(len(ids),10)
        self.assertEqual(len(set(ids)),10)
        self.assertFalse(doc["release_admitted"])
        self.assertFalse(doc["all_rocm_apis_qualified"])
        self.assertIn("hip-runtime",ids)
        self.assertIn("rocr-hsa-kfd",ids)
        self.assertIn("llvm-hip-compiler",ids)
        with self.assertRaises(ValueError):m.validate_layer("pytorch-opinfo")

    def test_original_source_requires_exact_commit(self):
        with self.assertRaises(ValueError):
            m.pin_source(Path("/tmp"),"not-a-hash")
        with self.assertRaises(ValueError):
            m.pin_runtime(Path("/opt/rocm"))

    def test_initial_plan_preserves_every_case_as_unassayed(self):
        row=m.initial("miopen","/src","a"*40,"/nix/store/rocm",
                      "/build","/nix/store/ctest","b"*64,
                      ["conv","pool"],"c"*64)
        self.assertEqual(list(row["cases"]),["conv","pool"])
        self.assertTrue(all(x["status"]=="unassayed" for x in row["cases"].values()))
        self.assertFalse(row["gpu_validated"])
        self.assertFalse(row["release_admitted"])
        self.assertFalse(row["runtime_coherence_verified"])
        m.verify_resume(row,row)

    def test_drift_and_promotions_fail_closed(self):
        row=m.initial("miopen","/src","a"*40,"/nix/store/rocm",
                      "/build","/nix/store/ctest","b"*64,["conv"],"c"*64)
        altered=json.loads(json.dumps(row))
        altered["discovery_sha256"]="changed"
        with self.assertRaises(ValueError):m.verify_resume(row,altered)
        modified=json.loads(json.dumps(row))
        modified["cases"]["conv"]["status"]="imagined-pass"
        with self.assertRaises(ValueError):m.verify_resume(modified,row)
        modified=json.loads(json.dumps(row))
        modified["release_admitted"]=True
        with self.assertRaises(ValueError):m.verify_resume(modified,row)

    def test_ctest_outputs_do_not_infer_full_gpu_pass(self):
        row=m.initial("hip-runtime","/src","a"*40,"/nix/store/rocm",
                      "/build","/nix/store/ctest","b"*64,["memcpy"],"c"*64)
        row["cases"]["memcpy"]={"status":"ctest-pass"}
        self.assertEqual(m.summary(row)["ctest-pass"],1)
        self.assertFalse(row["gpu_validated"])

    def test_receipt_atomicity(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"receipt.json"
            m.save(out,{"status":"unassayed"})
            self.assertEqual(json.loads(out.read_text())["status"],"unassayed")
            self.assertFalse(out.with_name(out.name+".tmp").exists())

    def test_ctest_build_must_be_from_pinned_source(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"source"
            source.mkdir()
            build=root/"build"
            build.mkdir()
            (build/"CTestTestfile.cmake").write_text("add_test(one /bin/true)")
            (build/"CMakeCache.txt").write_text(
                "CMAKE_HOME_DIRECTORY:INTERNAL="+str(source)+"\n")
            row=m.validate_build_source(source,build)
            self.assertEqual(row["cmake_home"],str(source))
            self.assertEqual(len(row["ctestfile_sha256"]),64)
            (build/"CMakeCache.txt").write_text(
                "CMAKE_HOME_DIRECTORY:INTERNAL=/unrelated/source\n")
            with self.assertRaises(ValueError):
                m.validate_build_source(source,build)

    def test_source_compiles(self):
        compile(FILE.read_text(),str(FILE),"exec")

if __name__=="__main__":unittest.main()
