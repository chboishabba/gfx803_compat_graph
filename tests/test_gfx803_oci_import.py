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


    def test_offline_mock_import_writes_unpromoted_manifest(self):
        import json
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            bin_dir = p / "bin"
            bin_dir.mkdir()
            # Reproduce the skopeo -> umoci -> nix-store command boundaries
            # without downloads, GPU access, root privileges or a Nix daemon.
            scripts = {
                "skopeo": '#!/usr/bin/env bash\nif [[ "$1" == "inspect" ]]; then echo \'{"Labels":{}}\'; fi\n',
                "umoci": '#!/usr/bin/env bash\nfor last; do :; done\nmkdir -p "$last/rootfs/opt/rocm" "$last/rootfs/opt/venv"\n',
                "nix": '#!/usr/bin/env bash\necho "/nix/store/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-mock-gfx803"\n',
            }
            for name, contents in scripts.items():
                tool = bin_dir / name
                tool.write_text(contents, encoding="utf-8")
                tool.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
            out = p / "candidate"
            run = subprocess.run(
                ["bash", str(SCRIPT), "--image", PREFIX + "a" * 64,
                 "--source-revision", SHA, "--with-venv", "--out", str(out)],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            candidate = json.loads((out / "candidate.json").read_text(encoding="utf-8"))
            self.assertEqual(candidate["state"], "candidate")
            self.assertEqual(candidate["upstream_revision"], SHA)
            self.assertFalse(candidate["provenance"]["native_nix_build"])
            self.assertEqual(set(candidate["store_paths"]), {"rocm", "venv"})


if __name__ == "__main__":
    unittest.main()
