import unittest

from stack_inventory import (
    merge_inventory_into_manifest,
    parse_rocminfo_agents,
    parse_readelf_dynamic,
    parse_strings_gpu_targets,
)


class StackInventoryTests(unittest.TestCase):
    def test_parse_readelf_dynamic_extracts_soname_and_needed(self):
        text = """
 0x000000000000000e (SONAME)             Library soname: [libamdhip64.so.7]
 0x0000000000000001 (NEEDED)             Shared library: [libhsa-runtime64.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libstdc++.so.6]
"""
        result = parse_readelf_dynamic(text)
        self.assertEqual(result["soname"], "libamdhip64.so.7")
        self.assertEqual(result["needed"], ["libhsa-runtime64.so.1", "libstdc++.so.6"])

    def test_parse_strings_gpu_targets_deduplicates_targets(self):
        text = "gfx803\namdgcn-amd-amdhsa--gfx803\ngfx900\ngfx803\n"
        self.assertEqual(parse_strings_gpu_targets(text), ["gfx803", "gfx900"])

    def test_parse_rocminfo_agents_keeps_device_identity_and_topology(self):
        text = """
*******
Agent 2
*******
  Name:                    gfx803
  Uuid:                    GPU-AAA
  Marketing Name:          Radeon RX 580
  Vendor Name:             AMD
  Feature:                 KERNEL_DISPATCH
  Node:                    1
  Device Type:             GPU
  Chip ID:                 26591(0x67df)
  BDFID:                   256
  Compute Unit:            36
*******
Agent 3
*******
  Name:                    gfx803
  Uuid:                    GPU-BBB
  Marketing Name:          Radeon Vega 8
  Vendor Name:             AMD
  Feature:                 KERNEL_DISPATCH
  Node:                    2
  Device Type:             GPU
  Chip ID:                 5597(0x15dd)
  BDFID:                   1024
  Compute Unit:            8
"""
        agents = parse_rocminfo_agents(text)
        self.assertEqual(len(agents), 2)
        self.assertEqual(agents[0]["name"], "gfx803")
        self.assertEqual(agents[0]["marketing_name"], "Radeon RX 580")
        self.assertEqual(agents[0]["chip_id"], "26591(0x67df)")
        self.assertEqual(agents[0]["bdfid"], "256")
        self.assertEqual(agents[1]["marketing_name"], "Radeon Vega 8")

    def test_merge_inventory_preserves_existing_manifest_and_adds_coordinates(self):
        manifest = {
            "release_id": "rocm10-ref",
            "stack_id": "gfx803",
            "patch_set": ["legacy-doorbell"],
        }
        inventory = {
            "components": {"libamdhip64.so.7": {"sha256": "abc"}},
            "targets": ["gfx803"],
            "topology": {"agents": [{"name": "gfx803"}]},
            "inventory_evidence": {"elf_inventory": "paid", "topology": "paid"},
        }
        merged = merge_inventory_into_manifest(manifest, inventory)
        self.assertEqual(merged["release_id"], "rocm10-ref")
        self.assertEqual(merged["components"]["libamdhip64.so.7"]["sha256"], "abc")
        self.assertEqual(merged["targets"], ["gfx803"])
        self.assertEqual(merged["topology"]["agents"][0]["name"], "gfx803")
        self.assertEqual(merged["evidence"]["elf_inventory"], "paid")


if __name__ == "__main__":
    unittest.main()
