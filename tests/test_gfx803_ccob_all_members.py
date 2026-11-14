"""T1.13-14 CPU-only CCOB enumeration/decoder regression contracts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]/"scripts"
def load(n):
    p=ROOT/(n+".py")
    s=importlib.util.spec_from_file_location(n,p)
    m=importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
ix=load("gfx803_ccob_member_index")
members=load("gfx803_ccob_all_members_topk")

def ccob(payload=b"payload"):
    return b"CCOB"+struct.pack("<HHQQQ",3,1,32+len(payload),256,123)+payload

class MemberAttribution(unittest.TestCase):
    def test_empty_and_unknown_codeobject_do_not_claim_kernel(self):
        decoder=load("gfx803_amdgpu_msgpack_notes")
        r=members.summarize(b"not an ELF",decoder)
        self.assertFalse(r["elf_amdgpu"])
        self.assertEqual(r["topk_named"],[])
    def test_per_member_input_mismatch_is_failclosed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fat=root/"fatbin";fat.write_bytes(ccob())
            idx=ix.index(fat.read_bytes())
            idx["members"][0]["sha256"]="incorrect"
            tool=root/"bundler";tool.write_text("")
            with self.assertRaisesRegex(ValueError,"member SHA mismatch"):
                members.analyze(fat,idx,tool,root/"out.json")
    def test_fake_bundler_no_gpu_calls(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fat=root/"fatbin";fat.write_bytes(ccob()+b"\0"*32+ccob(b"two"))
            idx=ix.index(fat.read_bytes())
            tool=root/"bundler";tool.write_text("")
            def fake_run(argv,timeout=60):
                if "--list" in argv:
                    return {"exit":0,"stdout":"hip-amdgcn-amd-amdhsa--gfx803\n","stderr":""}
                # A deliberately fake object file; this must remain unknown,
                # not be interpreted as a real compiled GPU kernel.
                for a in argv:
                    if a.startswith("--output="):
                        Path(a.split("=",1)[1]).write_bytes(b"not_an_elf")
                return {"exit":0,"stdout":"","stderr":""}
            with patch.object(members,"run",side_effect=fake_run):
                report=members.analyze(fat,idx,tool,root/"result.json")
            self.assertTrue(report["complete"])
            self.assertEqual(report["inspected_ccob_members"],2)
            self.assertEqual(report["matched_topk_members"],[])
            self.assertEqual(report["results"][0]["status"],"non-elf-or-unsupported-codeobject")
    def test_development_limit_cannot_be_full_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fat=root/"fatbin";fat.write_bytes(ccob()+b"\0"*3+ccob())
            idx=ix.index(fat.read_bytes())
            tool=root/"bundler";tool.write_text("")
            with patch.object(members,"run",return_value={"exit":1,"stdout":"","stderr":"unsupported"}):
                report=members.analyze(fat,idx,tool,root/"out.json",limit=1)
            self.assertFalse(report["complete"])
            self.assertEqual(report["inspected_ccob_members"],1)
    def test_compile(self):
        for n in ("gfx803_ccob_member_index","gfx803_ccob_all_members_topk"):
            p=ROOT/(n+".py");compile(p.read_text(),str(p),"exec")
if __name__=="__main__":unittest.main()
