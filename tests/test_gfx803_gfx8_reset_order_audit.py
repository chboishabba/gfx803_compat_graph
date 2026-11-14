"""CPU-only classification tests for the GFX8 reset source-order audit."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PATH = Path(__file__).parents[1] / "scripts" / "gfx803_gfx8_reset_order_audit.py"
SPEC = importlib.util.spec_from_file_location("gfx8_order", PATH)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def synthetic_sources(patched: bool) -> dict[str, str]:
    pre = "amdgpu_device_kfd_pre_reset(ctx, list);\n" if patched else ""
    old = "amdgpu_amdkfd_pre_reset(dev, ctx);\n" if not patched else ""
    sched = ("amdgpu_device_gpu_resume(adev, list, false);\n"
             "amdgpu_device_sched_resume(list, ctx, false);\n") if patched else (
             "amdgpu_device_sched_resume(list, ctx, false);\n"
             "amdgpu_device_gpu_resume(adev, list, false);\n")
    return {
        "device": (
            "int amdgpu_device_gpu_recover(void) {\n"
            + pre + "amdgpu_device_recovery_get_reset_lock(adev, list);\n"
            + "amdgpu_device_halt_activities(adev, ctx);\n"
            + sched + "}\n"
            + "void amdgpu_device_halt_activities(void) {\n" + old + "}\n"
            + "void amdgpu_pci_error_detected(void) {\n"
            + pre + "amdgpu_device_recovery_get_reset_lock(adev, list);\n"
            + "amdgpu_device_halt_activities(adev, ctx);\n}\n"
        ),
        "queue": (
            "int unmap_queues_cpsch(void) {\n"
            "if (!down_read_trylock(sem)) return -EIO;\n"
            "return amdkfd_fence_wait_timeout(dqm, 1, 100);\n}\n"
            "int restore_process_queues_cpsch(void) {\n"
            + ("if (amdgpu_in_reset(adev)) return -EAGAIN;\n" if patched else "")
            + "qpd->evicted--;\nreturn 0;\n}\n"
        ),
        "gfx8": (
            "int gfx_v8_0_mqd_init(void) {\n"
            + ("if (ring != &adev->gfx.kiq[0].ring) {\n" if patched else "")
            + "tmp = REG_SET_FIELD(tmp, CP_HQD_QUANTUM, QUANTUM_EN, 1);\n"
            + ("}\n" if patched else "")
            + "return 0;\n}\n"
        ),
    }


class ResetOrderTests(unittest.TestCase):
    def test_legacy_v73_classification(self) -> None:
        r = MOD.audit(synthetic_sources(False))
        self.assertEqual(r["gpu_recover_preempt_lock_order"],
                         "reset-lock-before-kfd-preempt")
        self.assertEqual(r["pci_error_preempt_lock_order"],
                         "reset-lock-before-kfd-preempt")
        self.assertEqual(r["post_reset_scheduler_order"],
                         "schedulers-before-gpu-kfd-post-reset")
        self.assertEqual(r["restore_queues_reset_guard"],
                         "no-reset-eagain-guard-seen")
        self.assertFalse(r["gfx8_kiq_quantum_exempt"])
        self.assertTrue(r["unmap_uses_reset_domain_read_trylock"])

    def test_corrected_order_classification(self) -> None:
        r = MOD.audit(synthetic_sources(True))
        self.assertEqual(r["gpu_recover_preempt_lock_order"],
                         "preempt-before-reset-lock")
        self.assertEqual(r["pci_error_preempt_lock_order"],
                         "preempt-before-reset-lock")
        self.assertEqual(r["post_reset_scheduler_order"],
                         "gpu-kfd-post-reset-before-schedulers")
        self.assertEqual(r["restore_queues_reset_guard"], "reset-guard-present")
        self.assertTrue(r["gfx8_kiq_quantum_exempt"])

    def test_missing_function_fails_closed(self) -> None:
        bad = synthetic_sources(False)
        bad["device"] = bad["device"].replace(
            "amdgpu_device_gpu_recover", "function_missing")
        with self.assertRaises(ValueError):
            MOD.audit(bad)

    def test_comments_do_not_invent_functions(self) -> None:
        source = "/* int fake(void) { } */\n// int fake(void) { }\n"
        with self.assertRaises(ValueError):
            MOD.function_body(source, "fake")

    def test_hashes_and_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            fixtures = synthetic_sources(True)
            for key, relative in MOD.SOURCE_FILES.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(fixtures[key])
            data, sha = MOD.read_sources(root)
            self.assertEqual(set(data), {"device", "queue", "gfx8"})
            self.assertEqual(len(sha["device"]), 64)
            (root / MOD.SOURCE_FILES["gfx8"]).unlink()
            with self.assertRaises(ValueError):
                MOD.read_sources(root)

    def test_cli_rejects_incomplete_source_without_gpu(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            result = subprocess.run([
                sys.executable, str(PATH), "--source", str(root),
                "--out", str(root / "out.json")
            ], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertIn("required exact source missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
