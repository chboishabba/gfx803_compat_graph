"""CPU-only metadata-scoped AMDGPU ISA inspection contract."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

P=Path(__file__).resolve().parents[1]/"scripts"/"gfx803_mbtopk_kernel_disasm.py"
spec=importlib.util.spec_from_file_location("disasm",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class DisassemblyTests(unittest.TestCase):
    def sample(self,d):
        f=Path(d)/"candidate.hsaco"
        f.write_bytes(b"offline-code-object")
        return f,{"mode":"offline-amdgpu-msgpack-note",
                  "hsaco_sha256":hashlib.sha256(f.read_bytes()).hexdigest(),
                  "hsaco_size_bytes":f.stat().st_size,
                  "kernels":[{"name":"mbtopk",
                              "properties":{".symbol":"_Zmbtopk_isa"}}]}
    def test_no_kernel_defaults_to_blocked_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            f,receipt=self.sample(d)
            r=m.disassemble(f,receipt,None,None)
            self.assertIn("no-kernel-selected",r["status"])
            self.assertFalse(r["actual_incident_execution"])
            self.assertEqual(r["available_metadata_symbols"],["_Zmbtopk_isa"])
    def test_reject_unknown_kernel_without_disassembly(self):
        with tempfile.TemporaryDirectory() as d:
            f,receipt=self.sample(d)
            with self.assertRaisesRegex(ValueError,"not in decoded"):
                m.disassemble(f,receipt,"invented_kernel",None)
    def test_reject_corrupted_hash(self):
        with tempfile.TemporaryDirectory() as d:
            f,receipt=self.sample(d)
            receipt["hsaco_sha256"]="00"
            with self.assertRaisesRegex(ValueError,"integrity"):
                m.disassemble(f,receipt,None,None)
    def test_instruction_classification_is_not_causal(self):
        asm="\ns_barrier\ns_waitcnt vmcnt(0)\nflat_load_dword\nflat_store_dword\ns_cbranch_scc0\ns_endpgm\n"
        counts=m.instruction_kinds(asm)
        self.assertEqual(counts["s_barrier"],1)
        self.assertEqual(counts["s_waitcnt"],1)
        self.assertEqual(counts["global_load"],1)
        self.assertEqual(counts["global_store"],1)
        self.assertEqual(counts["branch"],1)
    def test_compiles(self):
        compile(P.read_text(),str(P),"exec")
if __name__=="__main__":unittest.main()
