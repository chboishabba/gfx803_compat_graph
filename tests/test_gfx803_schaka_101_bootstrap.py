"""Offline source contracts for pinned Schaka 10.1 OCI candidate bootstrap.

No registry access, container layers, Nix store writes or GPU in these tests.
"""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/bootstrap-schaka-101-candidate.sh"


class Schaka101BootstrapTests(unittest.TestCase):
    def test_bash_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_help_needs_no_download(self):
        response=subprocess.run(["bash",str(SCRIPT),"--help"],
                                capture_output=True,text=True)
        self.assertEqual(response.returncode,0,response.stderr)
        self.assertIn("INSPECT",response.stdout.upper())

    def test_requires_operator_out_and_never_guesses_digest(self):
        response=subprocess.run(["bash",str(SCRIPT),"--inspect-only"],
                                capture_output=True,text=True)
        self.assertNotEqual(response.returncode,0)
        source=SCRIPT.read_text()
        for required in (
            "rocm10.1-gfx803", "skopeo inspect",
            'repo', "source_revision",
            "io.rocm.gfx803.source-rev",
            "io.rocm.gfx803.stage", "parse_pins",
            "inspect_runtime",
            "--with-venv",
            '"$IMAGE@$PIN"',
            "candidate-runtime-selector.json",
        ):
            self.assertIn(required,source)
        self.assertNotIn("docker pull",source)
        self.assertNotIn("docker build",source)
        self.assertNotIn("nix store add-path /opt/rocm",source)

    def test_source_lock_is_not_automatically_rewritten(self):
        script=SCRIPT.read_text()
        self.assertNotIn("lock-image --digest",script)
        self.assertNotIn("git push",script)
        self.assertIn("Review upstream and change the source lock",script)


if __name__ == "__main__":
    unittest.main()
