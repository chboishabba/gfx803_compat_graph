import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from gfx803_opinfo_replay_join import join, MATRIX_SHA, SOURCE_PIN

class ReplayJoin(unittest.TestCase):
    def doc(self,outcome="upstream-skipped"):
        return dict(schema=1,mode="replay",original_matrix_sha256=MATRIX_SHA,
                    audit_sha256="audit",pytorch_source=SOURCE_PIN,
                    selected_nodes=["a"],cases={"a":dict(status="replayed",
                    runtime_outcome=outcome,skip_reason="actual reason")})
    def test_duplicate_not_double_counted(self):
        d=self.doc()
        result=join(["a","b"],"audit",[("one",d),("two",d)])
        self.assertEqual(result["resolved_count"],1)
        self.assertEqual(result["unresolved_nodes"],["b"])
    def test_conflict_not_promoted(self):
        result=join(["a"],"audit",[("one",self.doc()),("two",self.doc("executed-passed"))])
        self.assertEqual(result["unresolved_count"],1)
    def test_identity_refusal(self):
        with self.assertRaises(ValueError):
            join(["a"],"other",[("one",self.doc())])
    def test_missing_reason(self):
        d=self.doc()
        del d["cases"]["a"]["skip_reason"]
        self.assertEqual(join(["a"],"audit",[("one",d)])["resolved_count"],0)
