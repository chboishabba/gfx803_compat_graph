"""CPU-only tests of GFX8 VM_CONTEXT1 fault register bit fields."""
from pathlib import Path
import importlib.util
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gfx803_gmc8_vm_fault_decode.py"
SPEC = importlib.util.spec_from_file_location("gfx8_fault_decode", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VmFaultDecodeTests(unittest.TestCase):
    def test_real_november_kWin_fault(self):
        r = MODULE.decode(0x0E0C4001, 0x54433300)
        self.assertEqual(r["vmid"], 7)
        self.assertEqual(r["protections_bits"], 1)
        self.assertEqual(r["access"], "read")
        self.assertEqual(r["memory_client_ascii"], "TC3.")
        self.assertFalse(r["unique_pte_cause_inferable"])

    def test_second_bitfield_is_not_an_enum(self):
        r = MODULE.decode(0x0E0C4008, 0x54433300)
        self.assertEqual(r["protections_bits"], 8)
        self.assertFalse(r["unique_pte_cause_inferable"])

    def test_access_and_vmid_fields(self):
        r = MODULE.decode((5 << 25) | (1 << 24) | 0x21)
        self.assertEqual(r["vmid"], 5)
        self.assertEqual(r["access"], "write")
        self.assertEqual(r["protections_bits"], 0x21)

    def test_reject_non_32_bit_inputs(self):
        for status in (-1, 0x100000000):
            with self.assertRaises(ValueError):
                MODULE.decode(status)
        with self.assertRaises(ValueError):
            MODULE.decode(1, -1)


if __name__ == "__main__":
    unittest.main()
