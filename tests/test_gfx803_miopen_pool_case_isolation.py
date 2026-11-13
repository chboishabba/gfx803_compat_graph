"""CPU-only tests for source-preserving gfx803 MIOpen pooling fault isolation."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/gfx803_miopen_pool_case_isolation.py"
spec=importlib.util.spec_from_file_location("gfx803_miopen_pool_case_isolation",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class PoolIsolationTests(unittest.TestCase):
    def original(self):
        return """#include "common.hpp"
static bool run_one(int a, int b, int c, int d, int e, int f, int g, int h) { return true; }
int main() {
    miopenPoolingMode_t modes[] = {miopenPoolingMax, miopenPoolingAverage, miopenPoolingAverageInclusive};
    struct Case { int C,H,W,kh,kw,stride,pad; };
    Case cases[] = {
""" + "\n".join("        {8, %d,%d, 2,2, 2, 0},"%(16+2*i,16+2*i) for i in range(14)) + """
    };
    int total=0, wrong=0;
""" + m.OLD + """
    fflush(stdout);
    fprintf(stderr, "SUMMARY: %d cases tested, %d WRONG", total, wrong);
    return wrong>0 ? 1 : 0;
}"""

    def test_exact_42_source_cases(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"pool_sweep.cpp"
            path.write_text(self.original())
            output,rows=m.transformed(path)
            self.assertEqual(len(rows),14)
            self.assertIn("GFX803_POOL_CASE_BEGIN",output)
            self.assertIn("if (index++ != selected) continue;",output)
            self.assertEqual(output.split("int main() {",1)[0],
                             self.original().split("int main() {",1)[0])
            self.assertNotIn(m.OLD,output)

    def test_halts_on_missing_and_ambiguous_source(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"pool_sweep.cpp"
            path.write_text(self.original().replace(m.OLD,""))
            with self.assertRaises(ValueError):m.transformed(path)

    def test_exact_single_case_result(self):
        good=b"GFX803_POOL_CASE_BEGIN index=17 mode=1\nmode=AVG cos=1.00000  OK\n"
        foot=b"SUMMARY: 1 cases tested, 0 WRONG\n"
        self.assertEqual(m.assess(17,0,good,foot)["status"],"pass")
        self.assertEqual(m.assess(17,0,good.replace(b"17",b"18"),foot)["status"],
                         "invalid-result")
        self.assertEqual(m.assess(17,0,good,b"")["status"],"invalid-result")
        self.assertEqual(m.assess(17,1,good,b"SUMMARY: 1 cases tested, 1 WRONG")["status"],
                         "numeric-fail")
        self.assertEqual(m.assess(17,-11,b"",b"")["status"],"fault")
        self.assertEqual(m.assess(17,None,b"",b"")["status"],"timeout")

    def test_source_compiles(self):
        compile(SCRIPT.read_text(),str(SCRIPT),"exec")

    def test_auto_recovery_uses_fresh_resume_invocation(self):
        args=m.recovery_argv([str(SCRIPT),"--build","--execute","--auto-recover"])
        self.assertNotIn("--build",args)
        self.assertEqual(args.count("--resume"),1)
        self.assertEqual(args.count("--execute"),1)
        self.assertEqual(args.count("--recovered-after-fault"),1)
        env=m.recovery_env()
        self.assertEqual(env["PYTHONNOUSERSITE"],"1")
        self.assertNotIn("LD_PRELOAD",env)

    def test_main_parses_build_timeout_and_batch_size(self):
        # Argument validation must reach source pinning instead of treating
        # argparse attribute names as Python subtraction expressions.
        with self.assertRaises(SystemExit) as stopped:
            m.main(["--source","/missing","--rocm-prefix","/missing",
                    "--hipcc","/missing","--out","/missing-out",
                    "--build-timeout","1","--batch-size","1"])
        self.assertEqual(stopped.exception.code,2)

if __name__=="__main__":unittest.main()
