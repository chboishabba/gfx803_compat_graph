"""Offline contracts for KFD/TopK source and evidence harvest scripts."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    file=ROOT/"scripts"/(name+".py")
    spec=importlib.util.spec_from_file_location(name,file)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

incident=load("gfx803_kfd_incident_offline_audit")
trace=load("gfx803_kfd_trace_boundary")
topk=load("gfx803_topk_binary_offline_audit")
join=load("gfx803_kfd_topk_evidence_join")
binary=load("gfx803_kfd_binary_branch_audit")

class IncidentAudit(unittest.TestCase):
    def test_log_event_order_and_case(self):
        data=("12:39:28 Failed to quiesce KFD\n"
              "12:39:29 ring kiq_0.2.1.0 test failed (-110)\n"
              "12:39:29 unsuccessful queues preemption\n")
        out=incident.journal_events(data)
        self.assertEqual(out["quiesce"]["first"]["line"],1)
        self.assertEqual(out["kiq"]["first"]["line"],2)
        self.assertEqual(out["preemption"]["count"],1)
        self.assertIsNone(out["kcq"]["first"])
    def test_current_boot_param_not_historical(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/"uni_mes").write_text("1")
            r=incident.module_parameter("uni_mes",root=root)
            self.assertEqual(r["value"],"1")
            self.assertEqual(r["scope"],"postboot-only")
    def test_no_false_incident_selection(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"incident.log"
            p.write_text("unsuccessful queues preemption\nFailed to quiesce KFD\n")
            out=incident.analyze(p,{"journal_sha256":incident.digest(p)})
            self.assertIsNone(out["actual_incident_branch"])
            self.assertIsNone(out["actual_evict_return"])
            self.assertTrue(out["matches_receipt_hash"])

class TraceBoundary(unittest.TestCase):
    def test_compiler_suffix_and_independent_branches(self):
        kall=("00000000 t evict_process_queues_cpsch\n"
              "00000000 t unmap_queues_cpsch\n"
              "00000000 t remove_queue_mes_on_reset_option.constprop.0\n"
              "00000000 t reset_queues_mes\n")
        chosen=trace.choose_available(trace.symbols(kall))
        self.assertEqual(len(chosen),4)
        self.assertIn(("mes","remove_queue_mes_on_reset_option.constprop.0"),chosen)
        self.assertEqual(trace.inventory(kall,None)["unresolved"],[])
    def test_ambiguous_symbol_is_not_accepted(self):
        names={"evict_process_queues_cpsch","evict_process_queues_cpsch.isra.0"}
        chosen=trace.choose_available(names)
        self.assertFalse(any(label=="evict" for label,_ in chosen))
    def test_no_tracefs_modification_in_inventory(self):
        r=trace.inventory("",None)
        self.assertIsNone(r["trace_root"])
        self.assertEqual(len(r["unresolved"]),4)

class TopKStatic(unittest.TestCase):
    def test_resource_scaling_and_no_runtime_claim(self):
        a=topk.case_resource(1,151936,50,4)
        b=topk.case_resource(32,151936,50,4)
        self.assertEqual(b["input_bytes_min"],32*a["input_bytes_min"])
        self.assertIn("not measured",b["limitation"])
    def test_wheel_inventory_and_hash(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/"torch-test.whl"
            with zipfile.ZipFile(f,"w") as z:
                z.writestr("torch/lib/libtorch_hip.so",b"gfx803/topk")
                z.writestr("torch/lib/libtorch_cpu.so",b"unrelated-host-code")
            r=topk.manifest(f)
            self.assertEqual(r["kind"],"wheel")
            self.assertEqual(r["libs"][0]["sha256"],
                hashlib.sha256(b"gfx803/topk").hexdigest())
            self.assertIsNone(r["libs"][1]["sha256"])
            self.assertIn("libtorch_hip.so",r["hash_scope"])
    def test_source_features_are_not_asserted_as_gpu_proof(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/"TensorTopK.cpp"
            f.write_text('GFX803_TOPK_SORT_FALLBACK_PATCH\n'
                         'isGPUArch({"gfx803"})\n'
                         'bool should_use_sort(Tensor t) { return true; }\n')
            r=topk.source_audit(f)
            self.assertTrue(r["arch_helper"])
            self.assertTrue(r["marker"])
            self.assertFalse(r["manual_gcn_arch"])
    def test_join_refuses_bad_hash_and_does_not_promote_log_wording(self):
        old = {"mode":"read-only","matches_receipt_hash":True,
               "incident_journal_sha256":"sha",
               "actual_incident_branch":None,"actual_evict_return":None,
               "first_log_events":{"quiesce":{"first":{"record":"Failed to quiesce KFD"}},
                 "preemption":{"first":{"record":"unsuccessful queues preemption"}}}}
        probe={"probes":[],"unresolved":[]}
        wheel={"mode":"static-only","incident":{"first_dispatched_kernel":None}}
        result=join.report(old,probe,wheel,{"journal_sha256":"sha"})
        self.assertEqual(result["gates"]["K2.05"]["status"],"open")
        self.assertEqual(result["gates"]["T1"]["status"],"open")
        self.assertEqual(result["gates"]["release"]["status"],"blocked")
        with self.assertRaises(ValueError):
            join.report(old,probe,wheel,{"journal_sha256":"wrong"})

    def test_disassembly_parser_preserves_both_calls_without_claiming_execution(self):
        asm = "\n".join((
            " 0010: e8 00 00 00 00 call 0 <unmap_queues_cpsch>",
            " 0020: e8 00 00 00 00 call 0 <remove_queue_mes>",
            " 0030: 75 01 jne 0x40",
        ))
        result=binary.dissect(asm)
        self.assertEqual(len(result["named_call_sites"]),2)
        self.assertEqual(len(result["conditional_jumps"]),1)
        self.assertIn("no incident-time",result["warning"])

    def test_source_and_binary_join_keep_incident_open(self):
        old={"mode":"read-only","matches_receipt_hash":True,
             "incident_journal_sha256":"sha","actual_incident_branch":None,
             "actual_evict_return":None,"first_log_events":{}}
        trace={"probes":[],"unresolved":[]}
        topk={"mode":"static-only","incident":{"first_dispatched_kernel":None}}
        attribution={"k2_06_reference_attribution":{"reference_source":
                       {"exact_cachyos_package_match":False}},
                     "t1_04_static_candidate":{"binary":
                       {"sha256":"hipsha","build_id":"hipbid"}}}
        elf={"mode":"offline-binary","sha256":"hipsha",
             "build_id":"hipbid","offload_sections":[{"name":".hip_fatbin"}]}
        r=join.report(old,trace,topk,{"journal_sha256":"sha"},attribution,elf)
        self.assertEqual(r["gates"]["K2.06"]["status"],"reference-source-mapped")
        self.assertEqual(r["gates"]["T1.04"]["candidate"],"mbtopk")
        self.assertIsNone(r["gates"]["T1.05"]["actual_executed_hsaco"])
        self.assertEqual(r["gates"]["release"]["status"],"blocked")
        elf["build_id"]="unmatched"
        with self.assertRaisesRegex(ValueError,"identity mismatch"):
            join.report(old,trace,topk,{"journal_sha256":"sha"},attribution,elf)

    def test_compile_all_sources(self):
        for name in ("gfx803_kfd_incident_offline_audit",
                     "gfx803_kfd_trace_boundary",
                     "gfx803_topk_binary_offline_audit",
                     "gfx803_kfd_topk_evidence_join",
                     "gfx803_kfd_binary_branch_audit"):
            path=ROOT/"scripts"/(name+".py")
            compile(path.read_text(),str(path),"exec")

if __name__=="__main__":unittest.main()
