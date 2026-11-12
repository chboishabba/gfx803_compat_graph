"""Offline source ownership and output parsing for Schaka GEMM/Triton probes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/gfx803_schaka_reuse_assay.py"
spec=importlib.util.spec_from_file_location("gfx803_schaka_reuse_assay",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class SchakaSourceAssayTests(unittest.TestCase):
    def test_fp16_numeric_contract(self):
        result=m.parse("fp16-gemm","5",0,
                       b'{"i": 5, "kind": "mm", "err": 0.0002, "scale": 1.5, "ok": true}\nF16SWEEP cases=1 wrong=0\n')
        self.assertEqual(result["status"],"source-verified-pass")
        self.assertEqual(result["upstream"]["i"],5)
        self.assertIn("0.02",result["numeric_contract"])

    def test_not_pass_on_wrong_case_or_numeric_failure(self):
        self.assertEqual(m.parse("fp16-gemm","5",0,b'{"i": 7, "ok": true}\n')["status"],
                         "unparseable")
        self.assertEqual(m.parse("fp16-gemm","5",1,b'{"i": 5, "ok": false}\n')["status"],
                         "source-reported-fail")

    def test_triton_execution_is_not_numerical_pass(self):
        result=m.parse("triton-dot","fp16",0,
                       b'TRITONDOT {"dtype":"fp16","max_err":12345.0,"ok":true}\n')
        self.assertEqual(result["status"],"numeric-unqualified")
        self.assertEqual(result["upstream"]["max_err"],12345.0)
        self.assertNotEqual(result["status"],"source-verified-pass")
        self.assertEqual(m.parse("triton-dot","i8",1,
             b'TRITONDOT {"dtype":"i8","ok":false}\n')["status"],"source-reported-fail")

    def test_selected_source_contracts(self):
        self.assertEqual(len(m.SCRIPTS),2)
        self.assertEqual(m.PIN,"8fdcf7b1305d0cfc6fc8c1fc7b1bfb5f73494e78")
        with self.assertRaises(ValueError):
            m.checks(Path("/bin/python3"),Path("/opt/rocm"))

    def test_exact_pin_sources_observed(self):
        # Synthetic AST of the upstream case registry, not GPU execution.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            p=root/m.SCRIPTS["triton-dot"]
            p.parent.mkdir(parents=True)
            p.write_text('DTYPES = {"fp16": None,"bf16": None,"fp32": None,"i8": None}\n')
            _,ids,_=m.inputs(root,"triton-dot")
            self.assertEqual(ids,["bf16","fp16","fp32","i8"])

    def test_code_compiles(self):
        compile(SCRIPT.read_text(),str(SCRIPT),"exec")

if __name__=="__main__":unittest.main()
