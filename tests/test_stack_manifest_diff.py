import unittest

from stack_manifest_diff import diff_manifests, render_markdown


class StackManifestDiffTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            "release_id": "old",
            "stack_id": "gfx803",
            "components": {
                "rocm-systems": "aaa111",
                "rocblas": "6.4.4",
            },
            "targets": ["gfx803"],
            "patch_set": ["legacy-doorbell", "old-workaround"],
            "benchmark_summary": {
                "statuses": {
                    "enumeration": "pass",
                    "leech": "partial",
                    "whisperx": "crash",
                }
            },
            "evidence": {
                "build": "paid",
                "enumeration": "paid",
                "numerical_correctness": "unpaid",
                "reset_safety": "unpaid",
            },
        }
        self.after = {
            "release_id": "new",
            "stack_id": "gfx803",
            "components": {
                "rocm-systems": "bbb222",
                "rocblas": "6.4.4",
                "miopen": "3.5.0",
            },
            "targets": ["gfx803", "gfx900"],
            "patch_set": ["legacy-doorbell", "d2h-staged-copy"],
            "benchmark_summary": {
                "statuses": {
                    "enumeration": "pass",
                    "leech": "pass",
                    "whisperx": "hang",
                    "comfyui": "partial",
                }
            },
            "evidence": {
                "build": "paid",
                "enumeration": "paid",
                "numerical_correctness": "partial",
                "reset_safety": "unpaid",
            },
        }

    def test_diff_tracks_source_patch_and_target_changes(self):
        delta = diff_manifests(self.before, self.after)
        self.assertEqual(
            delta["component_changes"],
            [
                {"component": "miopen", "before": None, "after": "3.5.0"},
                {"component": "rocm-systems", "before": "aaa111", "after": "bbb222"},
            ],
        )
        self.assertEqual(delta["patch_changes"], {
            "added": ["d2h-staged-copy"],
            "removed": ["old-workaround"],
        })
        self.assertEqual(delta["target_changes"], {"added": ["gfx900"], "removed": []})

    def test_diff_separates_promotions_regressions_and_new_observations(self):
        delta = diff_manifests(self.before, self.after)
        self.assertEqual(delta["benchmark_changes"]["promotions"], [
            {"record": "leech", "before": "partial", "after": "pass"},
            {"record": "whisperx", "before": "crash", "after": "hang"},
        ])
        self.assertEqual(delta["benchmark_changes"]["regressions"], [])
        self.assertEqual(delta["benchmark_changes"]["added"], [
            {"record": "comfyui", "status": "partial"}
        ])

    def test_diff_keeps_evidence_payment_distinct_from_behavior(self):
        delta = diff_manifests(self.before, self.after)
        self.assertEqual(delta["evidence_changes"], [
            {"claim": "numerical_correctness", "before": "unpaid", "after": "partial"}
        ])
        self.assertEqual(delta["unpaid_evidence"], ["reset_safety"])

    def test_markdown_is_update_note_not_raw_json_dump(self):
        markdown = render_markdown(diff_manifests(self.before, self.after))
        self.assertIn("# gfx803 update: old → new", markdown)
        self.assertIn("## Component/source deltas", markdown)
        self.assertIn("`rocm-systems`: `aaa111` → `bbb222`", markdown)
        self.assertIn("## Validation promotions", markdown)
        self.assertIn("`leech`: partial → pass", markdown)
        self.assertIn("## Evidence still unpaid", markdown)
        self.assertIn("reset_safety", markdown)
        self.assertNotIn("AMD support", markdown)

    def test_missing_optional_sections_are_backward_compatible(self):
        delta = diff_manifests(
            {"release_id": "a", "stack_id": "old"},
            {"release_id": "b", "stack_id": "old"},
        )
        self.assertEqual(delta["component_changes"], [])
        self.assertEqual(delta["patch_changes"], {"added": [], "removed": []})
        self.assertEqual(delta["benchmark_changes"]["promotions"], [])
        self.assertEqual(delta["unpaid_evidence"], [])


if __name__ == "__main__":
    unittest.main()
