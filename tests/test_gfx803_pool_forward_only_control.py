"""Offline controls for documented MIOpen forward-only workspace derivative."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/gfx803_pool_forward_only_control.py"
spec=importlib.util.spec_from_file_location("gfx803_pool_forward_only_control",SRC)
# Runner imports sibling original-binary module: add only the local scripts
# path, never importing torch/ROCm or touching GPU.
import sys
sys.path.insert(0,str(ROOT/"scripts"))
try:
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
finally:
    sys.path.pop(0)

class ForwardOnlyTests(unittest.TestCase):
    def test_changes_both_flag_and_workspace_together(self):
        source=('static bool run_one() {\n'+mod.WORKSPACE_OLD+
                '\nreturn miopenPoolingForward(handle, poolDesc, &a, xDesc, d_x, '
                '&b, yDesc, '+mod.CALL_OLD+'\n}')
        result=mod.derivative(source)
        self.assertIn(mod.CALL_NEW,result)
        self.assertNotIn(mod.CALL_OLD,result)
        self.assertIn("do_backward=false" if False else "forward-only MIOpen contract",result)
        self.assertNotIn("miopenPoolingGetWorkSpaceSizeV2",result)
        self.assertEqual(result.count("nullptr, 0"),1)
        self.assertEqual(result.split("static bool run_one()",1)[0],
                         source.split("static bool run_one()",1)[0])

    def test_fails_on_unmatched_or_multiple_calls(self):
        with self.assertRaises(ValueError):mod.derivative("some unrelated source")
        with self.assertRaises(ValueError):
            mod.derivative(mod.WORKSPACE_OLD+"\n"+mod.CALL_OLD+"\n"+mod.CALL_OLD)

    def test_module_compiles(self):
        compile(SRC.read_text(),str(SRC),"exec")

if __name__=="__main__":unittest.main()
