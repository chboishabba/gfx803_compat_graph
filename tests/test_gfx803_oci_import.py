import subprocess
import unittest
from pathlib import Path

from scripts.gfx803_component_graph import PIN_SOURCES
from scripts.gfx803_oci_runtime_contract import REQUIRED_IMAGE_ENV

PINS = " ".join(name + "=" + ("a" * 40) for name in PIN_SOURCES)


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
        import shutil
        import shlex
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            bin_dir = p / "bin"
            bin_dir.mkdir()
            # Reproduce the skopeo -> umoci -> nix-store command boundaries
            # without downloads, GPU access, root privileges or a Nix daemon.
            shell = "#!" + shutil.which("bash") + "\n"
            image_labels = json.dumps({"Digest": "sha256:" + "a" * 64, "Labels": {
                "io.rocm.gfx803.source-rev": SHA,
                "io.rocm.gfx803.line": "rocm10.1",
                "io.rocm.gfx803.stage": "final",
                "io.rocm.gfx803.pins": PINS,
            }, "Env": [k + "=" + v for k, v in REQUIRED_IMAGE_ENV.items()]})
            scripts = {
                "skopeo": shell + 'if [[ "$1" == "inspect" ]]; then printf "%s\n" ' + shlex.quote(image_labels) + '; fi\n',
                "umoci": shell + 'for last; do :; done\nmkdir -p "$last/rootfs/opt/rocm/lib" "$last/rootfs/opt/venv/bin" "$last/rootfs/root/.local/share/uv/python/cpython/bin"\necho shim > "$last/rootfs/opt/rocm/lib/libgfx803_sgemm_shim.so"\necho python > "$last/rootfs/root/.local/share/uv/python/cpython/bin/python3.12"\nln -s /root/.local/share/uv/python/cpython/bin/python3.12 "$last/rootfs/opt/venv/bin/python"\n',
                "nix": shell + 'echo "/nix/store/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-mock-gfx803"\n',
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
            self.assertEqual(candidate["provenance"]["upstream_commit_correspondence"], "publisher-oci-labels-matched")
            self.assertEqual(set(candidate["store_paths"]), {"rocm", "venv"})

    def test_rejects_inspect_digest_mismatch_before_layer_download(self):
        import json
        import os
        import shutil
        import shlex
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            bin_dir = p / "bin"
            bin_dir.mkdir()
            shell = "#!" + shutil.which("bash") + "\n"
            payload = json.dumps({"Digest": "sha256:" + "f" * 64, "Labels": {
                "io.rocm.gfx803.source-rev": SHA,
                "io.rocm.gfx803.line": "rocm10.1",
                "io.rocm.gfx803.stage": "final",
                "io.rocm.gfx803.pins": PINS,
            }, "Env": [k + "=" + v for k, v in REQUIRED_IMAGE_ENV.items()]})
            skopeo = bin_dir / "skopeo"
            skopeo.write_text(shell + 'printf "%s\\n" ' + shlex.quote(payload) + '\n')
            skopeo.chmod(0o755)
            for name in ("umoci", "nix"):
                stub = bin_dir / name
                stub.write_text(shell + "exit 99\n")
                stub.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
            run = subprocess.run(
                ["bash", str(SCRIPT), "--image", PREFIX + "a" * 64,
                 "--source-revision", SHA, "--out", str(p / "candidate")],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("OCI DIGEST MISMATCH", run.stderr)


if __name__ == "__main__":
    unittest.main()
