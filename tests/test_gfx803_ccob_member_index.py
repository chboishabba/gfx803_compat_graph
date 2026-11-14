"""Regression: CCOB member offsets follow sizes, not accidental payload magic."""
import importlib.util
import hashlib
from pathlib import Path
import struct
import unittest

P=Path(__file__).resolve().parents[1]/"scripts"/"gfx803_ccob_member_index.py"
spec=importlib.util.spec_from_file_location("ccob",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def member(payload=b"x",version=3):
    if version==3:
        return b"CCOB"+struct.pack("<HHQQQ",3,1,32+len(payload),256,123)+payload
    return b"CCOB"+struct.pack("<HHIIQ",2,1,24+len(payload),256,123)+payload

class CCOBMembers(unittest.TestCase):
    def test_two_members_with_padding(self):
        first=member(b"hello")
        second=member(b"world")
        data=first+b"\0"*31+second+b"\0"*19
        r=m.index(data)
        self.assertEqual(r["member_count"],2)
        self.assertEqual(r["members"][1]["offset"],len(first)+31)
        self.assertEqual(r["members"][1]["gap_bytes_before"],31)
        self.assertEqual(r["trailing_padding_bytes"],19)
    def test_embedded_ccob_marker_is_not_next_member(self):
        # Even a valid-looking header inside compressed data cannot
        # terminate an authoritative outer member prematurely.
        nested=member(b"deep")
        first=member(b"garbage"+nested+b"suffix")
        data=first+b"\0"*5+member(b"final")
        r=m.index(data)
        self.assertEqual(r["member_count"],2)
        self.assertEqual(r["members"][1]["offset"],len(first)+5)
    def test_invalid_header_refused(self):
        invalid=b"CCOB"+struct.pack("<HHQQQ",3,1,999999,256,0)
        with self.assertRaisesRegex(ValueError,"nonzero"):
            m.index(invalid)
    def test_nonzero_gap_refused(self):
        with self.assertRaisesRegex(ValueError,"nonzero"):
            m.index(member(b"1")+b"!!!"+member(b"2"))
    def test_v2_supported(self):
        r=m.index(member(b"a",2))
        self.assertEqual(r["member_count"],1)
        self.assertEqual(r["members"][0]["version"],2)
    def test_hash_member(self):
        x=member(b"data")
        r=m.index(x)
        self.assertEqual(r["members"][0]["sha256"],hashlib.sha256(x).hexdigest())
    def test_compile(self):
        compile(P.read_text(),str(P),"exec")
if __name__=="__main__":unittest.main()
