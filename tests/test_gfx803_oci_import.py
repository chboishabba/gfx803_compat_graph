import subprocess
import unittest
from pathlib import Path


SCRIPT = Path("scripts/import-schaka-oci-to-nix.sh")
PREFIX = "ghcr.io/schaka/rocm-migraphx-ort-torch-builder@sha256:"
SHA = "8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78"


class OciImportContractTests(unittest.TestCase):
    def call(self, *args):
        return subprocess.run(
            ["bash", str(SCRIPT), *args], capture_output=True, text=True, check=False
        )

    def test_shell_parses(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_refuses_moving_tag(self):
        result = self.call("--image", PREFIX[:-8] + ":latest-gfx803",
                           "--source-revision", SHA, "--dry-run")
        self.assertEqual(result.returncode, 2)
        self.assertIn("floating tags", result.stderr)

    def test_requires_full_commit(self):
        result = self.call("--image", PREFIX + "a" * 64,
                           "--source-revision", "main", "--dry-run")
        self.assertEqual(result.returncode, 2)

    def test_digest_pinned_dry_run_no_network(self):
        result = self.call("--image", PREFIX + "a" * 64,
                           "--source-revision", SHA, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dry-run: pinned image=", result.stdout)


if __name__ == "__main__":
    unittest.main()
