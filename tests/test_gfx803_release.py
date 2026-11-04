import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.gfx803_component_graph import PIN_SOURCES
from scripts.gfx803_release import (
    AdmissionError, REQUIRED, promote, update_lock, lock_image, validate_candidate,
    validate_lock, write, load,
)


PINS = " ".join(name + "=" + ("a" * 40) for name in PIN_SOURCES)
LOCK = {
    "schema_version": 1,
    "source_repository": "Schaka/rocm-gfx803",
    "source_branch": "main",
    "source_revision": "8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78",
    "rocm_version": "10.1.0",
    "image_repository": "ghcr.io/schaka/rocm-migraphx-ort-torch-builder",
    "image_digest": "sha256:" + "a" * 64,
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
        self.assertEqual(lock["image_digest"], "sha256:" + "a" * 64)

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
            promote(candidate, LOCK, evidence_root=Path('.'))

    def test_drift_and_tag_refs_fail(self):
        candidate = copy.deepcopy(CANDIDATE)
        candidate["upstream_revision"] = "0" * 40
        candidate["image_ref"] = LOCK["image_repository"] + ":latest-gfx803"
        errors = validate_candidate(candidate, LOCK)
        # Source mismatch, invalid floating tag and locked OCI digest mismatch.
        self.assertEqual(len(errors), 3)

    def test_unverified_source_cannot_promote_even_with_green_gpu_receipts(self):
        candidate = copy.deepcopy(CANDIDATE)
        candidate["hardware"] = HARDWARE
        candidate["evidence"] = {name: RECEIPT for name in REQUIRED}
        with self.assertRaisesRegex(AdmissionError, "correspondence"):
            promote(candidate, LOCK, evidence_root=Path('.'))

    def test_partial_receipts_are_not_promoted(self):
        candidate = copy.deepcopy(CANDIDATE)
        candidate["hardware"] = HARDWARE
        candidate["evidence"] = {name: RECEIPT for name in REQUIRED if name != "runtime_linkage"}
        with self.assertRaisesRegex(AdmissionError, "runtime_linkage"):
            promote(candidate, LOCK, evidence_root=Path('.'))

    def test_passing_receipts_scoped(self):
        candidate = copy.deepcopy(CANDIDATE)
        candidate["provenance"] = {
            "upstream_commit_correspondence": "verified",
            "runtime_relocation": "verified",
        }
        candidate["hardware"] = HARDWARE
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            candidate["evidence"] = {}
            for name in REQUIRED:
                content = (name + ": passed on real device\\n").encode()
                (logs / (name + ".log")).write_bytes(content)
                candidate["evidence"][name] = {
                    "status": "pass",
                    "command": "actual executed command",
                    "log_path": name + ".log",
                    "log_sha256": hashlib.sha256(content).hexdigest(),
                }
            accepted = promote(candidate, LOCK, evidence_root=logs)
            self.assertEqual(accepted["state"], "accepted")
            self.assertFalse(accepted["official_amd_support"])
            self.assertEqual(accepted["release_source_lock"]["source_revision"], LOCK["source_revision"])
            self.assertEqual(CANDIDATE["state"], "candidate")
            candidate["evidence"]["gpu_enumeration"]["log_sha256"] = "f" * 64
            with self.assertRaisesRegex(AdmissionError, "sha256 mismatch"):
                promote(candidate, LOCK, evidence_root=logs)

    def test_read_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "nested" / "candidate.json"
            write(p, CANDIDATE)
            self.assertEqual(load(p), CANDIDATE)

    def test_lock_image_rejects_mismatched_publisher_labels(self):
        inspection = {"Digest": "sha256:" + "b" * 64,
                      "Labels": {"io.rocm.gfx803.source-rev": LOCK["source_revision"],
                                 "io.rocm.gfx803.line": "rocm10.1",
                                 "io.rocm.gfx803.stage": "final",
                                 "io.rocm.gfx803.pins": PINS}}
        unlocked = copy.deepcopy(LOCK)
        unlocked["image_digest"] = None
        with self.assertRaisesRegex(AdmissionError, "inspect digest"):
            lock_image(unlocked, "sha256:" + "a" * 64, inspection)
        inspection["Digest"] = "sha256:" + "a" * 64
        inspection["Labels"]["io.rocm.gfx803.source-rev"] = "f" * 40
        with self.assertRaisesRegex(AdmissionError, "source-rev"):
            lock_image(unlocked, "sha256:" + "a" * 64, inspection)
        inspection["Labels"]["io.rocm.gfx803.source-rev"] = LOCK["source_revision"]
        self.assertTrue(lock_image(unlocked, "sha256:" + "a" * 64, inspection))
        self.assertEqual(unlocked["state"], "source-and-image-pinned")
        self.assertFalse(lock_image(unlocked, "sha256:" + "a" * 64, inspection))
        with self.assertRaisesRegex(AdmissionError, "already bound"):
            lock_image(unlocked, "sha256:" + "b" * 64,
                       dict(inspection, Digest="sha256:" + "b" * 64))

    def test_unlocked_image_cannot_promote_even_with_evidence(self):
        unlocked = copy.deepcopy(LOCK)
        unlocked["image_digest"] = None
        candidate = copy.deepcopy(CANDIDATE)
        self.assertEqual(validate_candidate(candidate, unlocked), [])
        self.assertIn("cannot promote with an unlocked OCI image digest",
                      validate_candidate(candidate, unlocked, require_evidence=True))

    def test_candidate_digest_must_match_pinned_lock(self):
        candidate = copy.deepcopy(CANDIDATE)
        candidate["image_ref"] = LOCK["image_repository"] + "@sha256:" + "b" * 64
        self.assertTrue(any("digest differs" in e for e in
                            validate_candidate(candidate, LOCK)))


if __name__ == "__main__":
    unittest.main()
