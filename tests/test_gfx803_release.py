import copy
import tempfile
import unittest
from pathlib import Path

from scripts.gfx803_release import (
    AdmissionError, REQUIRED, promote, update_lock, validate_candidate,
    validate_lock, write, load,
)


LOCK = {
    "schema_version": 1,
    "source_repository": "Schaka/rocm-gfx803",
    "source_branch": "main",
    "source_revision": "8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78",
    "rocm_version": "10.1.0",
    "image_repository": "ghcr.io/schaka/rocm-migraphx-ort-torch-builder",
    "image_digest": None,
}
CANDIDATE = {
    "schema_version": 1,
    "upstream_revision": LOCK["source_revision"],
    "rocm_version": "10.1.0",
    "image_ref": LOCK["image_repository"] + "@sha256:" + "a" * 64,
    "store_paths": {"rocm": "/nix/store/" + "a" * 32 + "-rocm-gfx803"},
    "state": "candidate",
}
HARDWARE = {"arch": "gfx803", "device": "RX 580", "kernel": "6.19",
            "driver": "amdgpu", "runner": "self-hosted-machine"}
RECEIPT = {"status": "pass", "log_sha256": "f" * 64,
           "command": "actual executed command"}


class ReleasePolicyTests(unittest.TestCase):
    def test_lock_and_noop(self):
        lock = copy.deepcopy(LOCK)
        validate_lock(lock)
        self.assertFalse(update_lock(lock, lock["source_revision"]))
        self.assertEqual(lock["image_digest"], None)

    def test_new_revision_invalidates_digest(self):
        lock = copy.deepcopy(LOCK)
        lock["image_digest"] = "sha256:" + "a" * 64
        self.assertTrue(update_lock(lock, "b" * 40))
        self.assertIsNone(lock["image_digest"])
        self.assertEqual(lock["state"], "source-pinned-image-unlocked")

    def test_invalid_revision_fails(self):
        with self.assertRaises(AdmissionError):
            update_lock(copy.deepcopy(LOCK), "latest")

    def test_import_can_be_candidate_but_cannot_promote(self):
        candidate = copy.deepcopy(CANDIDATE)
        self.assertEqual(validate_candidate(candidate, LOCK), [])
        with self.assertRaises(AdmissionError):
            promote(candidate, LOCK)

    def test_drift_and_tag_refs_fail(self):
        candidate = copy.deepcopy(CANDIDATE)
        candidate["upstream_revision"] = "0" * 40
        candidate["image_ref"] = LOCK["image_repository"] + ":latest-gfx803"
        errors = validate_candidate(candidate, LOCK)
        self.assertEqual(len(errors), 2)

    def test_partial_receipts_are_not_promoted(self):
        candidate = copy.deepcopy(CANDIDATE)
        candidate["hardware"] = HARDWARE
        candidate["evidence"] = {name: RECEIPT for name in REQUIRED[:-1]}
        with self.assertRaisesRegex(AdmissionError, "runtime_linkage"):
            promote(candidate, LOCK)

    def test_passing_receipts_scoped(self):
        candidate = copy.deepcopy(CANDIDATE)
        candidate["hardware"] = HARDWARE
        candidate["evidence"] = {name: copy.deepcopy(RECEIPT) for name in REQUIRED}
        accepted = promote(candidate, LOCK)
        self.assertEqual(accepted["state"], "accepted")
        self.assertFalse(accepted["official_amd_support"])
        self.assertEqual(CANDIDATE["state"], "candidate")

    def test_read_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "nested" / "candidate.json"
            write(p, CANDIDATE)
            self.assertEqual(load(p), CANDIDATE)


if __name__ == "__main__":
    unittest.main()
