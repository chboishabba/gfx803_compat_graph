"""CPU-only tests for manually armed TopK one-shot capture (never dispatch GPU)."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
from unittest import mock
import subprocess
import sys
import tempfile
import unittest

P = Path(__file__).resolve().parents[1] / "scripts/gfx803_topk_one_shot_capture.py"
spec = importlib.util.spec_from_file_location("gfx803_case4_capture", P)
assert spec and spec.loader
MOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MOD)


class OneShotCaptureTests(unittest.TestCase):
    def test_provenance_is_exact_november_incident_core(self):
        r = MOD.expected()
        self.assertEqual(r["incident"]["case"], 4)
        self.assertEqual(r["runtime"]["libtorch_hip"]["sha256"],
                         "c1ad552aac76766b14ad78b993b5e3ee7a3b72c7fc48b7d72345516cf6fba7ff")
        self.assertEqual(r["runtime"]["libtorch_hip"]["gnu_build_id"],
                         "3d27b29d191725660bbc4b8a83cb2f4753a09921")

    def test_no_gpu_import_or_extra_benchmark_case_in_capture_code(self):
        text = P.read_text()
        self.assertIn("result = module._one(4,10,50)", text)
        self.assertIn("assert module.CASES[4] ==", text)
        self.assertIn("automatic_reset", text)
        self.assertNotIn("torch.cuda.synchronize()", text)
        self.assertNotIn("amdgpu_gpu_recover", text)

    def test_sha256_streaming(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "payload.bin"
            f.write_bytes(b"abc")
            self.assertEqual(MOD.sha256(f), hashlib.sha256(b"abc").hexdigest())

    def test_exact_overlay_and_build_id_admitted_in_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            overlay = root / "torch-site"
            lib = overlay / "torch/lib/libtorch_hip.so"
            lib.parent.mkdir(parents=True)
            lib.write_bytes(b"fake-test-ELF")
            rocm = root / "rocm"
            rocm.mkdir()
            shim = root / "shim.so"
            shim.write_bytes(b"shim")
            r = {"incident": {"case":4},
                 "runtime":{"torch_overlay":str(overlay), "rocm_root":str(rocm),
                 "sgemm_shim_preloaded":True,
                 "libtorch_hip":{"sha256":hashlib.sha256(b"fake-test-ELF").hexdigest(),
                                 "gnu_build_id":"0123456789abcdef"}}}
            with mock.patch.object(MOD, "expected", return_value=r), mock.patch.object(
                    MOD, "check_build_id", return_value="0123456789abcdef"):
                got = MOD.validate_paths(Path(sys.executable), overlay, rocm, shim)
                self.assertEqual(got["build_id"], "0123456789abcdef")
                with self.assertRaisesRegex(ValueError, "overlay must match"):
                    MOD.validate_paths(root / "wrong", root / "other", rocm, shim)
                lib.write_bytes(b"wrong binary")
                with self.assertRaisesRegex(ValueError, "wrong incident libtorch_hip"):
                    MOD.validate_paths(Path(sys.executable), overlay, rocm, shim)

    def test_volatile_directory_and_overwrite_refused(self):
        with self.assertRaisesRegex(ValueError, "volatile"):
            MOD.durable_directory(Path("/tmp/gfx803-incident-test"))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "existing"):
                MOD.durable_directory(Path(d))
            MOD.durable_directory(Path(d) / "new-capture")

    def test_unexpected_preload_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            overlay = root / "torch-site"
            rocm = root / "rocm"
            shim = root / "shim.so"
            shim.write_bytes(b"test")
            with mock.patch.dict(os.environ, {"LD_PRELOAD":"/other/library.so"}):
                with self.assertRaisesRegex(ValueError, "unexpected LD_PRELOAD"):
                    MOD.build_env(overlay, rocm, shim)

    def test_env_preserves_explicit_original_shim_and_overlay(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            shim = root / "shim.so"
            shim.write_bytes(b"test")
            with mock.patch.dict(os.environ, {"LD_PRELOAD":""}, clear=True):
                env = MOD.build_env(root / "torch-site", root / "rocm", shim)
                self.assertEqual(env["LD_PRELOAD"], str(shim))
                self.assertEqual(env["PYTHONPATH"], str(root / "torch-site"))

    def test_no_execution_when_required_arguments_missing(self):
        r = subprocess.run([sys.executable, str(P), "--execute"], text=True,
                           capture_output=True, timeout=10)
        self.assertEqual(r.returncode, 2)
        self.assertIn("required", r.stderr)

    def test_manifest_writer_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            MOD.sync_json(p, {"abc":42})
            self.assertEqual(json.loads(p.read_text()), {"abc":42})
            with self.assertRaises(FileExistsError):
                MOD.sync_json(p, {"abc":2})

    def test_default_has_no_execute(self):
        text = P.read_text()
        self.assertIn('parser.add_argument("--execute", action="store_true"', text)
        self.assertIn("if not a.execute:", text)
        self.assertIn("if a.ack != ACK or not a.accept_single_display_risk:", text)

    def test_bpftrace_is_optin(self):
        text = P.read_text()
        self.assertIn('parser.add_argument("--enable-kfd-probes", action="store_true"', text)
        self.assertIn("if args.enable_kfd_probes:", text)
        self.assertIn("cannot attach required KFD return probes", text)


if __name__ == "__main__":
    unittest.main()
