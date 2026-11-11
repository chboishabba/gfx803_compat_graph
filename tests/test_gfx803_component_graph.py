import copy
import unittest

from scripts.gfx803_component_graph import (
    COMPONENTS, PIN_SOURCES, impacted_components, parse_pins, source_manifest,
)

PINS = {name: "a" * 40 for name in PIN_SOURCES}


class PinnedComponentGraphTests(unittest.TestCase):
    def test_parses_schaka_eight_pins(self):
        line = " ".join(name + "=" + sha for name, sha in PINS.items())
        self.assertEqual(parse_pins(line), PINS)

    def test_rejects_missing_duplicate_and_moving_ref(self):
        tokens = [name + "=" + sha for name, sha in PINS.items()]
        with self.assertRaisesRegex(ValueError, "expected 8"):
            parse_pins(" ".join(tokens[:-1]))
        with self.assertRaises(ValueError):
            parse_pins(" ".join(tokens[:-1] + [tokens[0]]))
        tokens[0] = list(PIN_SOURCES)[0] + "=main"
        with self.assertRaisesRegex(ValueError, "exact commit SHA"):
            parse_pins(" ".join(tokens))
        with self.assertRaises(ValueError):
            parse_pins("unrecorded")

    def test_no_source_change_rebuilds_nothing(self):
        self.assertEqual(impacted_components(PINS, PINS), [])

    def test_rocm_libraries_pin_invalidates_downstream_but_not_triton(self):
        latest = dict(PINS, ROCM_LIBRARIES_REF="b" * 40)
        rebuild = impacted_components(PINS, latest)
        self.assertEqual(rebuild, [
            "rocblas", "miopen", "rocsolver", "migraphx", "pytorch",
            "torchvision", "torchaudio", "ort", "vllm", "final",
        ])
        self.assertNotIn("rocr-clr", rebuild)
        self.assertNotIn("triton", rebuild)

    def test_vision_pin_only_invalidates_final_and_vision(self):
        latest = dict(PINS, TORCHVISION_REF="b" * 40)
        self.assertEqual(impacted_components(PINS, latest),
                         ["torchvision", "final"])

    def test_triton_pin_only_invalidates_triton_and_final(self):
        latest = dict(PINS, TRITON_REF="b" * 40)
        self.assertEqual(impacted_components(PINS, latest),
                         ["triton", "final"])

    def test_cannot_invent_build_or_reproducibility_receipt(self):
        m = source_manifest(PINS, "c" * 40)
        self.assertEqual(m["state"], "source-graph-only-not-native-build")
        self.assertEqual(m["sources"]["ROCM_SYSTEMS_REF"]["rev"], "a" * 40)
        self.assertEqual(set(m["components"]), set(COMPONENTS))


if __name__ == "__main__":
    unittest.main()
