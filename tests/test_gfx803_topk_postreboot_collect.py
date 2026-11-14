"""Pure offline post-reboot collection tests: subprocess output mocked, no GPU."""
from pathlib import Path
import importlib.util
import json
import tempfile
from unittest import mock
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/gfx803_topk_postreboot_collect.py"
SPEC=importlib.util.spec_from_file_location("gfx803_postcollector",SCRIPT)
assert SPEC and SPEC.loader
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class PostRebootCaptureTests(unittest.TestCase):
    def fixture(self,root,boot="12345678-1234-1234-1234-123456789abc"):
        run=root/"capture"
        run.mkdir()
        (run/"manifest.json").write_text(json.dumps({
            "schema":1,"mode":"ONE-SHOT-KNOWN-GPU-HANG",
            "boot_id":boot,"run_id":"testing-run"}))
        (run/"kernel-journal.log").write_text("Nov 14 12:39:28 ring gfx timeout\n")
        return run

    def test_exact_boot_id_not_minus_one(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=self.fixture(root)
            with mock.patch.object(MOD.subprocess,"run") as run_command:
                run_command.return_value.returncode=0
                run_command.return_value.stderr=b""
                result=MOD.collect(run,root/"post")
            self.assertEqual(result["mode"],"POST-REBOOT-READ-ONLY-COLLECT")
            self.assertEqual(result["gpu_commands"],0)
            self.assertEqual(result["original_boot_id"],
                             "12345678-1234-1234-1234-123456789abc")
            self.assertEqual(run_command.call_count,3)
            for call in run_command.call_args_list:
                command=call.args[0]
                self.assertIn("12345678-1234-1234-1234-123456789abc",command)
                self.assertNotIn("-1",command)
            self.assertEqual(len(result["original_artifacts"]
                                 ["kernel-journal.log"]["sha256"]),64)

    def test_original_remains_unchanged_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=self.fixture(root)
            original=(run/"manifest.json").read_bytes()
            with mock.patch.object(MOD.subprocess,"run") as cmd:
                cmd.return_value.returncode=0
                cmd.return_value.stderr=b""
                MOD.collect(run,root/"post")
            self.assertEqual((run/"manifest.json").read_bytes(),original)
            with self.assertRaisesRegex(ValueError,"refuse overwrite"):
                MOD.collect(run,root/"post")

    def test_invalid_boot_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=self.fixture(root,"bad")
            with self.assertRaisesRegex(ValueError,"invalid original boot ID"):
                MOD.collect(run,root/"post")
            self.assertFalse((root/"post").exists())

    def test_missing_capture_manifest_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=root/"capture";run.mkdir()
            with self.assertRaisesRegex(ValueError,"missing original"):
                MOD.collect(run,root/"post")

    def test_command_failures_recorded_not_claimed_clean(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=self.fixture(root)
            with mock.patch.object(MOD.subprocess,"run") as cmd:
                cmd.return_value.returncode=1
                cmd.return_value.stderr=b"No journal files were found"
                result=MOD.collect(run,root/"post")
            self.assertTrue(all(v["returncode"]==1
                                for v in result["journal_queries"].values()))
            self.assertFalse(result["original_gpu_dispatch_proven"])
            self.assertFalse(result["first_kfd_return_proven_by_kernel_journal"])

if __name__=="__main__":
    unittest.main()
