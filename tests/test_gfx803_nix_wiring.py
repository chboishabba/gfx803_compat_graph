import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class StandaloneNixToolWiringTests(unittest.TestCase):
    def test_policy_and_recorder_run_from_isolated_script_store(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("gfx803_component_graph.py", "gfx803_oci_runtime_contract.py",
                         "gfx803_release.py", "gfx803_capture.py"):
                shutil.copy2(Path("scripts") / name, root / name)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(root)
            for name in ("gfx803_release.py", "gfx803_capture.py"):
                proc = subprocess.run(
                    [sys.executable, str(root / name), "--help"],
                    cwd=root, env=env, capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0,
                                 name + ": " + proc.stderr)
                self.assertIn("usage:", proc.stdout)

    def test_nix_apps_use_directory_inputs_not_singleton_module_path(self):
        nix = Path("nix/gfx803/default.nix").read_text()
        self.assertIn("sourceScripts = ../../scripts;", nix)
        self.assertIn('GFX803_SOURCE_LOCK="${sourceLockFile}"', nix)
        self.assertIn('GFX803_SCRIPTS_DIR="${sourceScripts}"', nix)
        self.assertIn('PYTHONPATH="${sourceScripts}"', nix)
        self.assertIn('export LD_PRELOAD="${shim}"', nix)
        self.assertIn("export GFX803_SGEMM_SHIM_DISABLE=0", nix)
        self.assertNotIn("${../../scripts/gfx803_release.py}", nix)
        self.assertNotIn("${../../scripts/gfx803_capture.py}", nix)
        self.assertNotIn("${../../scripts/import-schaka-oci-to-nix.sh}", nix)


if __name__ == "__main__":
    unittest.main()
