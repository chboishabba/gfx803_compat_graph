"""Offline contracts for gfx7/gfx8 KFD callback provenance."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("audit", ROOT / "gfx803_kfd_doorbell_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

BRIDGE = (
    "static uint32_t kgd_hqd_sdma_get_doorbell(void) { return 0; }\n"
    "const struct calls x = { .hqd_sdma_get_doorbell = kgd_hqd_sdma_get_doorbell };\n"
)
QUEUE = (
    "if (gfx_target_version >= 70000 && gfx_target_version < 90000)\n"
    " expected_queue_size = properties->queue_size / 2;\n"
    "kfd_queue_buffer_get(vm, x, &properties->ring_bo, expected_queue_size);\n"
)


class DoorbellAudit(unittest.TestCase):
    def test_callbacks_and_queue_validation_are_scoped_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drivers/gpu/drm/amd"
            ag = root / "amdgpu"
            kfd = root / "amdkfd"
            ag.mkdir(parents=True)
            kfd.mkdir(parents=True)
            (ag / "amdgpu_amdkfd_gfx_v7.c").write_text(BRIDGE)
            (ag / "amdgpu_amdkfd_gfx_v8.c").write_text(BRIDGE)
            (kfd / "kfd_queue.c").write_text(QUEUE)
            result = audit.audit(root.parents[3], "abc")
        self.assertTrue(result["sdma_callback_source_present"])
        self.assertTrue(result["queue_validation_source_present"])
        self.assertIsNone(result["callback_called_in_incident"])
        self.assertFalse(result["binary_source_rebuild_match"])

    def test_missing_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "required source files missing"):
                audit.audit(Path(tmp), None)

    def test_module_stub_audit_requires_two_zero_return_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "amdgpu.ko"
            module.write_bytes(b"module")
            nm = "00000010 t kgd_hqd_sdma_get_doorbell\n00000020 t kgd_hqd_sdma_get_doorbell\n"
            with patch("subprocess.run") as run:
                run.side_effect = [
                    type("P", (), {"returncode": 0, "stdout": nm})(),
                    type("P", (), {"returncode": 0, "stdout": "xor    %eax,%eax"})(),
                    type("P", (), {"returncode": 0, "stdout": "xor    %eax,%eax"})(),
                ]
                result = audit.module_zero_stub_audit(module)
        self.assertTrue(result["two_zero_return_stubs_present"])


if __name__ == "__main__":
    unittest.main()
