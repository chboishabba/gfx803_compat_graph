"""CPU-only tests for the manually armed TopK repro/capture harness.

Never import torch, access /dev/kfd, set tracing or execute the hazardous case.
"""
from pathlib import Path
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


CHILD = load("gfx803_one_shot_case4")
CAPTURE = load("gfx803_one_shot_repro_capture")
DURABLE = load("gfx803_durable_stream")


class OneShotReproHarnessTests(unittest.TestCase):
    def test_case_identity_and_core_binary_sha_frozen(self):
        self.assertEqual(CHILD.CASE, 4)
        self.assertEqual(CHILD.SHAPE, (32, 151936))
        self.assertEqual(CHILD.K, 50)
        self.assertEqual(CHILD.DTYPE, "float32")
        self.assertEqual(CHILD.EXPECTED_LIBTORCH_SHA256,
                         "c1ad552aac76766b14ad78b993b5e3ee7a3b72c7fc48b7d72345516cf6fba7ff")

    def test_original_overlay_required_before_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rocm = root / "rocm"
            lib = root / "overlay/torch/lib/libtorch_hip.so"
            rocm.mkdir()
            lib.parent.mkdir(parents=True)
            lib.write_bytes(b"test")
            with self.assertRaisesRegex(ValueError, "wrong incident-time Nix"):
                CHILD.preflight_overlay(root / "overlay", rocm)
            d = CHILD.preflight_overlay(root / "overlay", rocm, enforce_original=False)
            self.assertEqual(len(d["libtorch_hip_sha256"]), 64)
            self.assertFalse(d["sha_matches_original"])

    def test_fail_closed_wrong_original_binary(self):
        with mock.patch.object(CHILD, "EXPECTED_OVERLAY", "/fake/overlay"):
            with mock.patch.object(CHILD, "EXPECTED_ROCM_ROOT", "/fake/rocm"):
                with self.assertRaisesRegex(ValueError, "missing original"):
                    CHILD.preflight_overlay(Path("/fake/overlay"), Path("/fake/rocm"))

    def test_baseline_exact_one_shot_command_no_gpu_execution(self):
        cmd = CAPTURE.command("baseline", Path("/exact/python"), Path("/tmp/new"))
        self.assertEqual(cmd[0], "/exact/python")
        self.assertIn("--arm-token", cmd)
        self.assertEqual(cmd[cmd.index("--warmup") + 1], "10")
        self.assertEqual(cmd[cmd.index("--iterations") + 1], "50")
        self.assertEqual(cmd[cmd.index("--benchmark") + 1], str(CAPTURE.BENCH))
        self.assertNotIn("rocprofv3", cmd)
        self.assertNotIn("--healthcheck", cmd)

    def test_rocprof_arm_has_explicit_instrumentation(self):
        cmd = CAPTURE.command("rocprof", Path("/exact/python"), Path("/tmp/new"))
        self.assertEqual(cmd[0], "rocprofv3")
        for arg in ("--hip-trace", "--hsa-trace", "--kernel-trace",
                    "--memory-copy-trace", "--memory-allocation-trace"):
            self.assertIn(arg, cmd)
        self.assertEqual(cmd.count("--"), 1)
        self.assertEqual(cmd[cmd.index("--") + 1], "/exact/python")

    def test_invalid_mode_fails(self):
        with self.assertRaises(ValueError):
            CAPTURE.command("unsafe-unknown", Path("python"), Path("/tmp/new"))

    def test_receipt_exclusive_creation_and_content(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "receipt.json"
            CAPTURE.flush_json(f, {"case": 4, "no_gpu": True})
            self.assertEqual(json.loads(f.read_text())["case"], 4)
            with self.assertRaises(FileExistsError):
                CAPTURE.flush_json(f, {"case": 5})

    def test_durable_sink_fsync_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "probe.log"
            DURABLE.record(['{"event":"kfd_probe_start"}\n',
                            '{"event":"fence_wait_return","return_code":-62}\n'],
                           out, echo=False)
            self.assertEqual(len(out.read_text().splitlines()), 2)
            with self.assertRaises(FileExistsError):
                DURABLE.record(["again\n"], out, echo=False)

    def test_safe_parent_does_not_import_torch(self):
        self.assertNotIn("torch", CAPTURE.__dict__)
        self.assertNotIn("torch", DURABLE.__dict__)

    def test_confirmation_phrase_is_pinned(self):
        self.assertIn("WEDGE AND REQUIRE REBOOT", CAPTURE.CONFIRM)


if __name__ == "__main__":
    unittest.main()
