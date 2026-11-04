import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.gfx803_oci_links import ImageLinkError, image_resolve, stage_tree


class OciSymlinkStagingTests(unittest.TestCase):
    def make_root(self, parent):
        root = parent / "image"
        core = root / "opt/rocm/core-10.1/lib"
        core.mkdir(parents=True)
        (core / "libMIOpen.so.1").write_bytes(b"fixture")
        alt = root / "etc/alternatives"
        alt.mkdir(parents=True)
        (alt / "rocm-lib").symlink_to("/opt/rocm/core-10.1/lib")
        (root / "opt/rocm/lib").symlink_to("/etc/alternatives/rocm-lib")
        return root

    def test_resolves_alternatives_inside_image_not_host(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            root = self.make_root(parent)
            self.assertEqual(
                image_resolve(root, "/opt/rocm/lib/libMIOpen.so.1"),
                "/opt/rocm/core-10.1/lib/libMIOpen.so.1",
            )
            report = stage_tree(root, "/opt/rocm", parent / "stage")
            self.assertTrue(report["all_links_relocated"])
            staged = parent / "stage/lib"
            self.assertTrue(staged.is_symlink())
            self.assertEqual(os.readlink(staged), "core-10.1/lib")
            self.assertEqual((staged / "libMIOpen.so.1").read_bytes(), b"fixture")
            self.assertFalse(os.readlink(staged).startswith("/"))

    def test_preserves_provenance_of_unresolved_external_link(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            root = self.make_root(parent)
            (root / "usr/lib").mkdir(parents=True)
            (root / "usr/lib/libfoo.so").write_bytes(b"external")
            (root / "opt/rocm/libforeign.so").symlink_to("/usr/lib/libfoo.so")
            report = stage_tree(root, "/opt/rocm", parent / "stage")
            self.assertEqual(report["unresolved"][0]["reason"],
                             "outside-selected-tree")
            self.assertFalse(report["all_links_relocated"])
            self.assertEqual(os.readlink(parent / "stage/libforeign.so"),
                             "/usr/lib/libfoo.so")

    def test_rejects_missing_and_cyclic_aliases(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            root = self.make_root(parent)
            (root / "opt/rocm/missing").symlink_to("/opt/rocm/no-file")
            (root / "etc/alternatives/loop").symlink_to("/etc/alternatives/loop")
            (root / "opt/rocm/loop").symlink_to("/etc/alternatives/loop")
            report = stage_tree(root, "/opt/rocm", parent / "stage")
            self.assertEqual({x["reason"] for x in report["unresolved"]},
                             {"missing-image-target",
                              "symlink cycle at /etc/alternatives/loop"})
            with self.assertRaises(ImageLinkError):
                image_resolve(root, "/opt/rocm/loop")

    def test_refuses_existing_staging_destination(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            root = self.make_root(parent)
            (parent / "stage").mkdir()
            with self.assertRaises(ValueError):
                stage_tree(root, "/opt/rocm", parent / "stage")

    def test_strict_command_writes_report_then_fails(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            root = self.make_root(parent)
            (root / "opt/rocm/bad-link").symlink_to("/etc/no-such-file")
            report = parent / "report.json"
            cmd = [
                sys.executable, "scripts/gfx803_oci_links.py",
                "--rootfs", str(root), "--tree", "/opt/rocm",
                "--out", str(parent / "stage"),
                "--report", str(report), "--strict",
            ]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 3, run.stderr)
            self.assertTrue(json.loads(report.read_text())["unresolved"])

    def test_venv_tree_stages_independently(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            root = self.make_root(parent)
            (root / "opt/venv/bin").mkdir(parents=True)
            (root / "opt/venv/bin/activate").write_text("test")
            report = stage_tree(root, "/opt/venv", parent / "venv")
            self.assertTrue(report["all_links_relocated"])
            self.assertTrue((parent / "venv/bin/activate").is_file())


if __name__ == "__main__":
    unittest.main()
