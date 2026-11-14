"""CPU-only T1.05 regressions: exact ELF gate, parser and source-scaling claims."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import hashlib

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    p=ROOT/"scripts"/(name+".py")
    spec=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
elf=load("gfx803_mbtopk_elf_attribution")
fat=load("gfx803_mbtopk_fatbin_scan")

class TopkElfTests(unittest.TestCase):
    def test_topk_symbols_are_not_dispatch(self):
        txt=("Symbol table '.symtab' contains 4 entries:\n"
             "  1: 0000000000001000 128 FUNC GLOBAL DEFAULT 13 mbtopk_float_kernel\n"
             "  2: 0000000000002000  64 FUNC LOCAL DEFAULT 13 unrelated\n")
        x=elf.parse_symbols(txt)
        self.assertEqual(len(x),1)
        self.assertEqual(x[0]["address"],"0000000000001000")
        self.assertEqual(x[0]["name"],"mbtopk_float_kernel")
    def test_offload_section_from_readelf(self):
        txt=" [42] .hip_fatbin PROGBITS 0000000000001000 00002000 00003000 00 A 0 0 8"
        s=elf.parse_sections(txt)
        self.assertEqual(s[0]["file_offset"],0x2000)
        self.assertEqual(s[0]["size_bytes"],0x3000)
    def test_plain_rodata_is_not_an_offload_bundle(self):
        txt=" [13] .rodata PROGBITS 0000000000001000 00002000 00003000 00 A 0 0 8"
        self.assertEqual(elf.parse_sections(txt), [])
    def test_buildid(self):
        self.assertEqual(elf.parse_build_id("Build ID: 392FEE76"),"392fee76")
        self.assertIsNone(elf.parse_build_id("no build"))
    def test_binary_identity_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"libtorch_hip.so"
            p.write_bytes(b"wrong library")
            receipt={"t1_04_static_candidate":{"binary":{"sha256":"bad","build_id":"bad"}}}
            with self.assertRaisesRegex(ValueError,"SHA differs"):
                elf.audit(p,receipt,None,None)
    def test_resource_case_scaling(self):
        one=elf.shape_bounds(1,151936,50)
        many=elf.shape_bounds(32,151936,50)
        self.assertEqual(many["input_bytes_f32_min"],one["input_bytes_f32_min"]*32)
        self.assertEqual(many["full_sort_indices_bytes_min"],32*one["full_sort_indices_bytes_min"])
    def test_streamed_symbol_inventory_is_explicitly_filtered(self):
        # The real HIP ELF has a very large complete symbol table.  The audit
        # must retain matching candidate lines without silently retaining only
        # an arbitrary prefix of that table.
        self.assertIn("matching-symbol", elf.invoke_matching_lines.__doc__)

class FatbinTests(unittest.TestCase):
    def synthetic_elf(self):
        # Minimal ELF64 LE AMDGPU with 1 valid section header, no payload.
        b=bytearray(128)
        b[:4]=b"\x7fELF";b[4]=2;b[5]=1
        struct.pack_into("<H",b,16,1)
        struct.pack_into("<H",b,18,224)
        struct.pack_into("<Q",b,40,64)
        struct.pack_into("<H",b,52,64)
        struct.pack_into("<H",b,58,64)
        struct.pack_into("<H",b,60,1)
        return bytes(b)
    def test_embedded_amdgpu_detected(self):
        data=b"PREFIX"+self.synthetic_elf()+b"SUFFIX"
        r=fat.inspect(data)
        self.assertEqual(len(r["embedded_amdgpu_elf_candidates"]),1)
        self.assertEqual(r["embedded_amdgpu_elf_candidates"][0]["offset"],6)
        self.assertIsNone(r["actual_dispatched_hsaco"])
    def test_other_machine_rejected(self):
        b=bytearray(self.synthetic_elf())
        struct.pack_into("<H",b,18,62)
        self.assertEqual(fat.inspect(bytes(b))["embedded_amdgpu_elf_candidates"],[])
    def test_out_of_range_section_rejected(self):
        b=bytearray(self.synthetic_elf())
        struct.pack_into("<I",b,64+4,1)
        struct.pack_into("<Q",b,64+24,100000)
        struct.pack_into("<Q",b,64+32,100)
        self.assertEqual(fat.inspect(bytes(b))["embedded_amdgpu_elf_candidates"],[])
    def test_source_scan_is_honest(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"TensorTopK.hip"
            src.write_text("mbtopk\nshould_use_multiblock\n")
            r=elf.source_scan(src)
            self.assertFalse(r["source_binary_build_link_proven"])
    def test_compiles(self):
        for name in ("gfx803_mbtopk_elf_attribution","gfx803_mbtopk_fatbin_scan"):
            p=ROOT/"scripts"/(name+".py")
            compile(p.read_text(),str(p),"exec")

if __name__=="__main__":unittest.main()
