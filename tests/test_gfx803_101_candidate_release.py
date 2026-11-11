"""Offline source/attestation contracts for Schaka 10.1 candidate release + TopK assay."""
import importlib.util
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    path=ROOT/"scripts"/(name+".py")
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

assembly=load("gfx803_101_release_assembly")
topk=load("gfx803_topk_semantics")

class CandidateOnlyContracts(unittest.TestCase):
    def selector(self):
        root="/nix/store/"+"a"*32+"-rocm"
        venv="/nix/store/"+"b"*32+"-venv"
        return {"immutable_image":assembly.IMAGE,"source_revision":assembly.SOURCE_REV,
                "rocm_root":root,"venv_root":venv,
                "shim":root+"/lib/libgfx803_sgemm_shim.so",
                "chosen_python":venv+"/bin/python",
                "required_ld_library_path":[root+"/lib",root+"/core-10.1/lib"]}

    def test_exact_source_candidate_denies_promotion(self):
        m=assembly.validate_selector(self.selector())
        self.assertFalse(m["release_admitted"])
        self.assertFalse(m["gpu_training_admitted"])
        self.assertIn("clean-client-nix-restore",m["unpaid_checks"])

    def test_wrong_image_and_host_lib_paths_denied(self):
        s=self.selector();s["immutable_image"]="floating"
        with self.assertRaises(ValueError):assembly.validate_selector(s)
        s=self.selector();s["required_ld_library_path"]=["/opt/rocm/lib"]
        with self.assertRaises(ValueError):assembly.validate_selector(s)
        s=self.selector();s["chosen_python"]="/usr/bin/python"
        with self.assertRaises(ValueError):assembly.validate_selector(s)

    def test_unpinned_wheel_path_denied(self):
        with self.assertRaises(ValueError):
            assembly.validate_selector(self.selector(),"/tmp/torch.whl")

    def test_fixed_output_wheel_file_is_a_valid_wheel_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel=Path(tmp)/"cached-wheel-without-extension"
            # Cachix fixed-output paths need not end with .whl.  The content
            # and metadata, not the store-file suffix, decide wheel identity.
            with zipfile.ZipFile(wheel,"w") as z:
                z.writestr("torch-2.14.0.dist-info/WHEEL","Wheel-Version: 1.0\n")
                z.writestr("torch-2.14.0.dist-info/METADATA",
                           "Name: torch\nVersion: 2.14.0+gitd70fd61\n")
            with mock.patch.object(assembly,"WHEEL_SHA256",
                                   hashlib.sha256(wheel.read_bytes()).hexdigest()):
                result=assembly.inspect_wheel(wheel)
            self.assertEqual(result["file"],str(wheel))

    def test_topk_matrix_has_120_unique_cases_and_authentic_shape(self):
        self.assertEqual(len(topk.CASES),120)
        names={topk.label(c) for c in topk.CASES}
        self.assertEqual(len(names),120)
        self.assertIn("float32-2x4-k2-largest-sorted-unique",names)

    def test_topk_retain_receipt_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"matrix.json"
            topk.write(file,{"state":"candidate"})
            self.assertIn("candidate",file.read_text())
            self.assertFalse((Path(tmp)/"matrix.json.tmp").exists())

    def test_modules_compile_without_pytorch(self):
        for name in ("gfx803_101_release_assembly","gfx803_topk_semantics"):
            path=ROOT/"scripts"/(name+".py")
            compile(path.read_text(),str(path),"exec")

if __name__=="__main__":unittest.main()
