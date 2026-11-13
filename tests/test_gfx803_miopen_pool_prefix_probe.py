"""Offline invariants for MIOpen pooling shared-process prefix ladder."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/gfx803_miopen_pool_prefix_probe.py"
spec=importlib.util.spec_from_file_location("gfx803_miopen_pool_prefix_probe",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class PrefixProbeTests(unittest.TestCase):
    def test_source_preserves_original_run_one(self):
        original='''#include "common.hpp"
static bool run_one(int mode,int C,int H,int W,int kh,int kw,int stride,int pad) {return true;}
int main() {
''' + m.OLD + '''
    return 0;
}
'''
        patched=m.derived(original.replace(
            'int main() {',
            'int main() {\n    miopenPoolingMode_t modes[] = {miopenPoolingMax, miopenPoolingAverage, miopenPoolingAverageInclusive};'))
        self.assertEqual(patched.split("int main() {")[0],
                         original.split("int main() {")[0])
        self.assertIn("POOL_BEGIN index=",patched)
        self.assertIn("POOL_END index=",patched)

    def test_prefix_pass_requires_all_ordered_case_markers(self):
        out=b"POOL_BEGIN index=0 prefix=2 mode=0\nPOOL_END index=0\nPOOL_BEGIN index=1 prefix=2 mode=0\nPOOL_END index=1\n"
        err=b"SUMMARY: 2 cases tested, 0 WRONG\n"
        self.assertEqual(m.classify(2,0,out,err)["status"],"passed")
        self.assertEqual(m.classify(3,0,out,err)["status"],"invalid-result")
        self.assertEqual(m.classify(2,0,out,err.replace(b"2 cases",b"1 cases"))["status"],
                         "invalid-result")
        self.assertEqual(m.classify(2,1,out,err)["status"],"numeric-fail")

    def test_faults_and_missing_tail_evidence(self):
        data=b"POOL_BEGIN index=0 prefix=42 mode=0\n"
        self.assertEqual(m.classify(42,-11,data,b"")["status"],"fault")
        self.assertEqual(m.classify(42,None,data,b"")["status"],"timeout")
        self.assertEqual(m.classify(42,1,data,b"")["last_started_index"],0)
        self.assertEqual(m.classify(42,1,data,b"")["status"],"fault")

    def test_syntax(self):
        compile(SRC.read_text(),str(SRC),"exec")

if __name__=="__main__":unittest.main()
