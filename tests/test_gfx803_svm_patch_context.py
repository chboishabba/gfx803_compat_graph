"""Offline git-apply checks for the AMD-reviewed SVM eviction RFC port.

Synthetic fixture checks unified-diff syntax and hunk consistency, not
physical kernel correctness. GFX803_KERNEL_SOURCE_ROOT optionally checks
a verified Linux v7.3 tree, without modifying it.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/linux/gfx803-t1-svm-concurrent-eviction-v73-rfc.patch"
HUNK = re.compile(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@")


def extract_old_hunks(patch):
    files = {}
    path = None
    current = None
    for line in patch.splitlines():
        if line.startswith("diff --git a/"):
            path = line.split(" ")[2][2:]
            files[path] = []
            current = None
        elif line.startswith("@@"):
            m = HUNK.match(line)
            if not m:
                raise ValueError("unsupported diff hunk: " + line)
            current = {"start": int(m[1]), "old_count": int(m[2]),
                       "new_count": int(m[4]), "old": [], "new": []}
            files[path].append(current)
        elif current is not None:
            if line.startswith(" "):
                current["old"].append(line[1:])
                current["new"].append(line[1:])
            elif line.startswith("-"):
                current["old"].append(line[1:])
            elif line.startswith("+"):
                current["new"].append(line[1:])
            elif line.startswith("\\ No newline"):
                pass
            else:
                raise ValueError("invalid hunk line " + line)
    for path, hunks in files.items():
        for h in hunks:
            if len(h["old"]) != h["old_count"] or len(h["new"]) != h["new_count"]:
                raise ValueError("incorrect hunk counts " + path)
    return files


class RfcSvmBackportTests(unittest.TestCase):
    def test_hunks_apply_and_remove_early_return(self):
        if not shutil.which("git"):
            self.skipTest("git not installed")
        patch = PATCH.read_text()
        hunks_by_path = extract_old_hunks(patch)
        self.assertEqual(set(hunks_by_path),
                         {"drivers/gpu/drm/amd/amdkfd/kfd_priv.h",
                          "drivers/gpu/drm/amd/amdkfd/kfd_svm.c"})
        with tempfile.TemporaryDirectory(prefix="gfx803-svm-rfc-") as tmp:
            for path, hunks in hunks_by_path.items():
                target = Path(tmp) / path
                target.parent.mkdir(parents=True, exist_ok=True)
                end = max(h["start"] + h["old_count"] for h in hunks)
                lines = [""] * (end + 20)
                for h in hunks:
                    start = h["start"] - 1
                    lines[start:start + h["old_count"]] = h["old"]
                target.write_text("\n".join(lines) + "\n")
            for argv in (["git", "apply", "--check", str(PATCH)],
                         ["git", "apply", str(PATCH)]):
                result = subprocess.run(argv, cwd=tmp, capture_output=True,
                                        text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
            svm = (Path(tmp) / "drivers/gpu/drm/amd/amdkfd/kfd_svm.c").read_text()
            self.assertIn("mutex_lock(&svms->evict_lock);", svm)
            self.assertIn("mutex_unlock(&svms->evict_lock);", svm)
            self.assertNotIn("if (evicted_ranges != 1)", svm)
            priv = (Path(tmp) / "drivers/gpu/drm/amd/amdkfd/kfd_priv.h").read_text()
            self.assertIn("evict_lock", priv)

    def test_pristine_source_tree_opt_in(self):
        source = os.environ.get("GFX803_KERNEL_SOURCE_ROOT")
        if not source:
            self.skipTest("Set GFX803_KERNEL_SOURCE_ROOT for exact source check")
        if not shutil.which("git"):
            self.skipTest("git not installed")
        result = subprocess.run(["git", "apply", "--check", str(PATCH)],
                                cwd=source, capture_output=True,
                                text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
