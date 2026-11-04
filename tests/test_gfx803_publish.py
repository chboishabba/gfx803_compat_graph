import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.gfx803_release import REQUIRED, promote, write

SCRIPT = Path("scripts/publish-gfx803-accepted.sh")
SOURCE = "8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78"
DIGEST = "sha256:" + "a" * 64
LOCK = {
    "schema_version": 1, "source_repository": "Schaka/rocm-gfx803",
    "source_branch": "main", "source_revision": SOURCE,
    "rocm_version": "10.1.0",
    "image_repository": "ghcr.io/schaka/rocm-migraphx-ort-torch-builder",
    "image_digest": DIGEST,
}


class AcceptedPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.logs = self.base / "logs"
        self.logs.mkdir()
        self.path = self.base / "accepted-release.json"
        self.candidate = {
            "schema_version": 1, "upstream_revision": SOURCE,
            "rocm_version": LOCK["rocm_version"],
            "image_ref": LOCK["image_repository"] + "@" + DIGEST,
            "store_paths": {"rocm": "/nix/store/" + "a"*32 + "-rocm-gfx803"},
            "state": "candidate",
            "provenance": {"upstream_commit_correspondence": "verified",
                           "runtime_relocation": "verified"},
            "hardware": {"arch": "gfx803", "device": "RX 580",
                         "kernel": "6.19", "driver": "amdgpu",
                         "runner": "real-test-fixture-only"},
            "evidence": {},
        }
        for check in REQUIRED:
            name = check + ".log"
            data = ("mock test receipt: " + check + "\n").encode()
            (self.logs / name).write_bytes(data)
            self.candidate["evidence"][check] = {
                "status": "pass", "command": "mock command: " + check,
                "log_path": name, "log_sha256": hashlib.sha256(data).hexdigest(),
            }
        write(self.path, promote(self.candidate, LOCK, evidence_root=self.logs))
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        # Fake Nix closure lookup: publication policy can be tested without Nix.
        nix = bin_dir / "nix"
        nix.write_text("#!" + shutil.which("bash") +
                       "\n[[ \"$1\" == path-info ]] || exit 8\n")
        nix.chmod(0o755)
        self.env = os.environ.copy()
        self.env["PATH"] = str(bin_dir) + os.pathsep + self.env["PATH"]

    def run_publish(self, *extra):
        return subprocess.run(["bash", str(SCRIPT), str(self.path), *extra],
                              env=self.env, capture_output=True, text=True)

    def test_refuses_no_evidence_root(self):
        r = self.run_publish("--dry-run")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--evidence-root", r.stderr)

    def test_dry_run_accepts_only_retained_evidence(self):
        r = self.run_publish("--evidence-root", str(self.logs), "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("evidence-verified", r.stdout)

    def test_tampered_original_log_is_rejected(self):
        (self.logs / "gpu_enumeration.log").write_text("changed")
        r = self.run_publish("--evidence-root", str(self.logs), "--dry-run")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("sha256 mismatch", r.stderr)

    def test_forged_accepted_state_cannot_bypass_lock(self):
        manifest = json.loads(self.path.read_text())
        manifest["release_source_lock"]["image_digest"] = None
        write(self.path, manifest)
        r = self.run_publish("--evidence-root", str(self.logs), "--dry-run")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unlocked OCI image digest", r.stderr)

    def test_missing_original_log_is_rejected(self):
        (self.logs / "sustained_load.log").unlink()
        r = self.run_publish("--evidence-root", str(self.logs), "--dry-run")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("missing or escaping retained log", r.stderr)


if __name__ == "__main__":
    unittest.main()
