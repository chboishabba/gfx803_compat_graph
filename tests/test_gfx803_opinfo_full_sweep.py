"""No GPU required: full-corpus OpInfo sweep integrity, resume and fault tests."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/"scripts"
spec=importlib.util.spec_from_file_location("gfx803_opinfo_full_sweep",SCRIPTS/"gfx803_opinfo_full_sweep.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FullOpInfoSweepContractTests(unittest.TestCase):
    def fixture(self):
        ids=[f"test/test_ops.py::TestCommonCUDA::test_compare_cpu_case{i}_cuda_float32"
             for i in range(1774)]
        return {"schema":1,"status":"collected","selected":ids,
                "collected_total":1774,"cases":{i:{"status":"unassayed"} for i in ids},
                "provenance":{"source":"pinned","python_wrapper":"wrapper","rocm_root":"store"}}

    def test_accepts_exact_all_nodes(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"collection.json"
            source.write_text(json.dumps(self.fixture()))
            data,raw=mod.load_collection(source)
            state=mod.new_matrix(data,raw)
            self.assertEqual(mod.counts(state)["unassayed"],1774)
            self.assertFalse(state["gpu_validated"])
            self.assertFalse(state["release_admitted"])
            self.assertEqual(state["collection_sha256"],mod.digest(raw))

    def test_collection_dedup_and_missing_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"collection.json"
            broken=self.fixture()
            broken["selected"]=broken["selected"][:-1]
            p.write_text(json.dumps(broken))
            with self.assertRaises(ValueError):mod.load_collection(p)

    def test_resume_refuses_source_hash_change(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"collection.json"
            p.write_text(json.dumps(self.fixture()))
            collection,raw=mod.load_collection(p)
            state=mod.new_matrix(collection,raw)
            mod.validate_resume(state,collection,raw)
            with self.assertRaises(ValueError):
                mod.validate_resume(state,collection,raw+b" ")

    def test_failure_retained_and_unassayed_not_pass(self):
        d=self.fixture()
        state=mod.new_matrix(d,json.dumps(d).encode())
        state["cases"][state["selected"][0]]={"status":"fault"}
        state["cases"][state["selected"][1]]={"status":"pass"}
        counts=mod.counts(state)
        self.assertEqual(counts["fault"],1)
        self.assertEqual(counts["pass"],1)
        self.assertEqual(counts["unassayed"],1772)

    def test_recovery_acknowledgement_is_bound_to_existing_hazard(self):
        d=self.fixture()
        state=mod.new_matrix(d,json.dumps(d).encode())
        first,second=state["selected"][:2]
        state["cases"][first]={"status":"interrupted"}
        self.assertEqual(mod.unacknowledged_hazards(state),[first])
        state["recovery_acknowledged_hazards"]=[first]
        self.assertEqual(mod.unacknowledged_hazards(state),[])
        state["cases"][second]={"status":"fault"}
        self.assertEqual(mod.unacknowledged_hazards(state),[second])

    def test_code_compiles(self):
        file=SCRIPTS/"gfx803_opinfo_full_sweep.py"
        compile(file.read_text(),str(file),"exec")

if __name__=="__main__":unittest.main()
