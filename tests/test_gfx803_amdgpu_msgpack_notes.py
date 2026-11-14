"""Offline MessagePack AMDGPU code object note decoder contracts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

P=Path(__file__).resolve().parents[1]/"scripts"/"gfx803_amdgpu_msgpack_notes.py"
spec=importlib.util.spec_from_file_location("amdgpu_notes",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def pack_string(s):
    b=s.encode()
    if len(b)<32:return bytes([0xa0|len(b)])+b
    return b"\xd9"+bytes([len(b)])+b

def pack_value(v):
    if isinstance(v,str):return pack_string(v)
    if isinstance(v,bool):return b"\xc3" if v else b"\xc2"
    if isinstance(v,int) and 0<=v<=127:return bytes([v])
    if isinstance(v,int):return b"\xd2"+struct.pack(">i",v)
    if isinstance(v,list):
        return bytes([0x90|len(v)])+b"".join(map(pack_value,v))
    if isinstance(v,dict):
        return bytes([0x80|len(v)])+b"".join(
            pack_value(k)+pack_value(x) for k,x in v.items())
    raise ValueError(v)

def synthetic_elf(meta):
    desc=pack_value(meta)
    name=b"AMDGPU\0"
    note=struct.pack("<III",len(name),len(desc),32)
    note+=name+b"\0"*((-len(name))%4)
    note+=desc+b"\0"*((-len(desc))%4)
    base=128
    data=bytearray(base+len(note))
    data[:4]=b"\x7fELF";data[4]=2;data[5]=1
    struct.pack_into("<H",data,18,224)
    struct.pack_into("<Q",data,32,64)
    struct.pack_into("<H",data,54,56)
    struct.pack_into("<H",data,56,1)
    struct.pack_into("<I",data,64,4)
    struct.pack_into("<Q",data,64+8,base)
    struct.pack_into("<Q",data,64+32,len(note))
    data[base:]=note
    return bytes(data)

class MessagePackTests(unittest.TestCase):
    def test_msgpack_nested_kernel_metadata(self):
        meta={"amdhsa.kernels":[{".name":"mbtopk_f32",
              ".vgpr_count":32,".sgpr_count":64,
              ".group_segment_fixed_size":1024}]}
        blob=pack_value(meta)
        parsed=m.MsgPack(blob)
        result=parsed.decode()
        self.assertEqual(parsed.pos,len(blob))
        self.assertEqual(result,meta)
        kernels=m.kernels_from_notes([{"metadata":result}])
        self.assertEqual(kernels[0]["properties"][".vgpr_count"],32)
        self.assertTrue(kernels[0]["topk_name_match"])
    def test_elf_note_header_and_msgpack(self):
        blob=synthetic_elf({"amdhsa.kernels":[{".name":"gather"}]})
        found=m.notes(blob)
        self.assertEqual(len(found),1)
        self.assertTrue(found[0]["msgpack_decoded"])
        self.assertEqual(m.kernels_from_notes(found)[0]["name"],"gather")
    def test_wrong_elf_machine_refused(self):
        data=bytearray(synthetic_elf({}))
        struct.pack_into("<H",data,18,62)
        with self.assertRaisesRegex(ValueError,"AMDGPU"):m.notes(bytes(data))
    def test_bad_msgpack_fails_closed(self):
        with self.assertRaisesRegex(m.DecodeError,"truncated"):
            m.MsgPack(b"\xd9\x10a").decode()
        with self.assertRaisesRegex(m.DecodeError,"unsupported"):
            m.MsgPack(b"\xc1").decode()
    def test_hash_gate(self):
        data=synthetic_elf({"amdhsa.kernels":[{".name":"example"}]})
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)/"foo.hsaco"
            f.write_bytes(data)
            rec={"unbundled_output":{"sha256":hashlib.sha256(data).hexdigest(),
                 "size_bytes":len(data)}}
            r=m.analyze(f,rec)
            self.assertEqual(r["metadata_kernel_count"],1)
            self.assertFalse(r["incident_runtime_selected"])
            rec["unbundled_output"]["sha256"]="wrong"
            with self.assertRaisesRegex(ValueError,"SHA/size mismatch"):
                m.analyze(f,rec)
    def test_no_metadata_is_not_negative_proof(self):
        data=synthetic_elf({"ordinary":"unrelated"})
        self.assertEqual(m.kernels_from_notes(m.notes(data)),[])
    def test_compile(self):
        compile(P.read_text(),str(P),"exec")

if __name__=="__main__":unittest.main()
