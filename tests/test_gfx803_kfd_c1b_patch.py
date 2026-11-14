"""CPU-only review checks for the RFC CPSCH source patch.

The default fixture is minimal upstream-v7.3 source-context, not the full
Linux kernel. Set GFX803_KERNEL_SOURCE_ROOT for an additional exact-tree
git-apply check on a pristine Linux v7.3/verified matching source checkout.
No build, driver load or GPU activity.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/linux/gfx803-c1b-cpsch-startup-rfc.patch"
REL = "drivers/gpu/drm/amd/amdkfd/kfd_device_queue_manager.c"


def upstream_context_fixture() -> str:
    lines = ["/* C1b context-only padding */\n"] * 2170
    first = [
        "\t/* clear hang status when driver try to start the hw scheduler */\n",
        "\tdqm->sched_running = true;\n",
        "\n",
        "\tif (!dqm->dev->kfd->shared_resources.enable_mes) {\n",
        "\t\tif (pm_config_dequeue_wait_counts(&dqm->packet_mgr,\n",
        "\t\t\t\tKFD_DEQUEUE_WAIT_INIT, 0 /* unused */))\n",
        '\t\t\tdev_err(dev, "Setting optimized dequeue wait failed. Using default values\\n");\n',
        "\t\texecute_queues_cpsch(dqm, KFD_UNMAP_QUEUES_FILTER_DYNAMIC_QUEUES, 0, USE_DEFAULT_GRACE_PERIOD);\n",
        "\t}\n",
    ]
    second = [
        "\n",
        "\treturn 0;\n",
        "fail_detect_hang_buffer:\n",
        "\tkfd_gtt_sa_free(dqm->dev, dqm->fence_mem);\n",
        "fail_allocate_vidmem:\n",
        "fail_set_sched_resources:\n",
    ]
    lines[2117 - 1:2117 - 1 + len(first)] = first
    lines[2146 - 1:2146 - 1 + len(second)] = second
    return "".join(lines)


class TestCpschRfcPatch(unittest.TestCase):
    def test_patch_applies_to_v73_context_and_removes_false_success(self):
        git = shutil.which("git")
        if not git:
            self.skipTest("git unavailable")
        with tempfile.TemporaryDirectory(prefix="gfx803-cpsch-patch-") as root:
            target = Path(root) / REL
            target.parent.mkdir(parents=True)
            target.write_text(upstream_context_fixture())
            for args in (["apply", "--check", str(PATCH)],
                         ["apply", str(PATCH)]):
                result = subprocess.run([git, *args], cwd=root,
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
            modified = target.read_text()
            self.assertIn("if (!amdgpu_in_reset(adev))", modified)
            self.assertIn("retval = execute_queues_cpsch(dqm,", modified)
            self.assertIn("if (retval)\n\t\t\t\tgoto fail_detect_hang_buffer", modified)
            self.assertIn("fail_detect_hang_buffer:\n\tdqm->sched_running = false;", modified)
            self.assertEqual(modified.count("dqm->sched_running = false;"), 1)

    def test_exact_source_optional(self):
        root = os.environ.get("GFX803_KERNEL_SOURCE_ROOT")
        if not root:
            self.skipTest("Set GFX803_KERNEL_SOURCE_ROOT for a source-package check")
        git = shutil.which("git")
        if not git:
            self.skipTest("git unavailable")
        target = Path(root) / REL
        self.assertTrue(target.is_file(), str(target))
        result = subprocess.run([git, "apply", "--check", str(PATCH)],
                                cwd=root, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
