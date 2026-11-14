"""CPU-only CCOB / Clang offload-bundle recognition contracts."""
import importlib.util
import struct
from pathlib import Path
import tempfile
import unittest

P=Path(__file__).resolve().parents[1]/"scripts"/"gfx803_mbtopk_offload_container_audit.py"
spec=importlib.util.spec_from_file_location("bundle",P)
bundle=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)

class OffloadInspectionTests(unittest.TestCase):
    def test_ccob_v3_bounded_header(self):
        raw=b"CCOB"+struct.pack("<HHQQQ",3,1,92,400,123)
        r=bundle.classify(raw+b"\x00"*(92-len(raw)),92)
        self.assertEqual(r["kind"],"ccob")
        self.assertEqual(r["declared_uncompressed_bytes"],400)
        self.assertTrue(r["declared_size_matches"])
    def test_ccob_does_not_guess_compression_method(self):
        r=bundle.classify(b"CCOB"+struct.pack("<HH",3,42),8)
        self.assertEqual(r["compression_method_code"],42)
        self.assertNotIn("zstd",r)
    def test_clang_header_with_two_targets(self):
        magic=bundle.BUNDLE_MAGIC
        targets=["host-x86_64-unknown-linux-gnu-","hipv4-amdgcn-amd-amdhsa--gfx803"]
        head=magic+struct.pack("<Q",len(targets))
        cursor=len(head)
        # Header will end before the payload.
        for t in targets:
            ident=t.encode()
            head+=struct.pack("<QQQ",512+cursor,8,len(ident))+ident
            cursor=len(head)
        r=bundle.classify(head+b"\0"*1000,len(head)+1000)
        self.assertEqual(r["kind"],"clang-uncompressed-bundle")
        self.assertEqual(r["status"],"parsed-header")
        self.assertEqual(len(r["entries"]),2)
        self.assertIn("gfx803",r["entries"][1]["target"])
    def test_out_of_range_bundles_refused(self):
        magic=bundle.BUNDLE_MAGIC
        raw=magic+struct.pack("<Q",1)+struct.pack("<QQQ",9999999,100,3)+b"hip"
        r=bundle.classify(raw, len(raw))
        self.assertEqual(r["status"],"invalid-entry-range")
    def test_elf_or_unknown_not_conflated(self):
        self.assertEqual(bundle.classify(b"\x7fELF"+b"\0"*64,68)["kind"],"direct-elf")
        self.assertEqual(bundle.classify(b"other",5)["kind"],"unknown")
    def test_target_list_fails_closed_to_single_gfx803(self):
        lines="hip-amdgcn-amd-amdhsa--gfx803\nhip-amdgcn-amd-amdhsa--gfx803\nhipv4-amdgcn-amd-amdhsa--gfx900\n"
        out=bundle.target_lines(lines)
        self.assertEqual(len(out),3)
        self.assertEqual(bundle.unique_targets(out), [
            "hip-amdgcn-amd-amdhsa--gfx803", "hipv4-amdgcn-amd-amdhsa--gfx900"])
    def test_readonly_classification_and_output_gate(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/"fatbin.bin"
            f.write_bytes(b"CCOB"+struct.pack("<HHQQQ",3,1,32,100,0))
            d=bundle.audit(f,None,None)
            self.assertEqual(d["header"]["kind"],"ccob")
            self.assertIsNone(d["incident_executed_kernel"])
            with self.assertRaisesRegex(ValueError,"requires --bundler"):
                bundle.audit(f,None,Path(t)/"gfx803.hsaco")
    def test_compile(self):
        compile(P.read_text(),str(P),"exec")
if __name__=="__main__":unittest.main()
