"""CPU-only T1.09-10 / K2.07-08 integration and fail-closed evidence tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    path=ROOT/"scripts"/(name+".py")
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

hsaco=load("gfx803_mbtopk_hsaco_metadata")
src=load("gfx803_mbtopk_retained_source_audit")
kfd=load("gfx803_kfd_nonmes_source_audit")
trace=load("gfx803_kfd_safehost_trace_plan")
join=load("gfx803_t109_k207_final_join")

class HSACO(unittest.TestCase):
    def test_machine_spelling_variants(self):
        self.assertTrue(hsaco.detect_header("Machine: AMD GPU\nFlags: gfx803")["amdgpu_machine_reported"])
        self.assertTrue(hsaco.detect_header("Machine: AMDGPU\nFlags: 0")["amdgpu_machine_reported"])
        self.assertFalse(hsaco.detect_header("Machine: Advanced Micro Devices X86-64\n")["amdgpu_machine_reported"])
    def test_kernel_yaml_fields_preserved(self):
        text="- .name: _Z12mbtopkKernelv\n  .sgpr_count: 42\n  .vgpr_count: 31\n  .group_segment_fixed_size: 1024\n- .name: other\n  .sgpr_count: 2\n"
        x=hsaco.parse_kernels(text)
        self.assertEqual(len(x),2)
        self.assertEqual(x[0]["fields"]["vgpr_count"],"31")
        self.assertEqual(x[1]["name"],"other")
    def test_hsaco_identity_gates_before_tools(self):
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)/"test.hsaco"
            f.write_bytes(b"not the real GPU code")
            with self.assertRaisesRegex(ValueError,"SHA mismatch"):
                hsaco.analyze(f,{"unbundled_output":{"sha256":"0"*64,"size_bytes":f.stat().st_size}})
    def test_elf_machine_from_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)/"test.hsaco"
            blob=bytearray(64)
            blob[:4]=b"\x7fELF"
            struct.pack_into("<H",blob,18,224)
            f.write_bytes(blob)
            receipt={"unbundled_output":{"sha256":hashlib.sha256(blob).hexdigest(),"size_bytes":64},
                     "gfx803_candidates":["hip-amdgcn-amd-amdhsa--gfx803"]}
            def fake_run(argv,**_):
                if "-h" in argv:
                    s="Machine: AMD GPU\nFlags: 0x0 gfx803"
                elif "-WS" in argv:s=" [ 1] .text PROGBITS 000 000040 000020 00 AX 0 0 16"
                else:s=""
                return {"status":"ok","stdout":s,"matching_lines":[],"truncated":False}
            with patch.object(hsaco,"run",side_effect=fake_run),\
                 patch.object(hsaco.shutil,"which",return_value="/bin/readelf"),\
                 patch.object(hsaco,"find_tool",return_value=None):
                r=hsaco.analyze(f,receipt)
            self.assertTrue(r["identity_verified"])
            self.assertTrue(r["header"]["machine_verified_from_elf_header"])
            self.assertIsNone(r["actual_incident_kernel"])
    def test_parse_sections(self):
        s=" [ 1] .note PROGBITS 0000000000000000 00000040 00000100 00 A 0 0 4"
        self.assertEqual(hsaco.parse_sections(s)[0]["size_bytes"],256)

class RetainedSource(unittest.TestCase):
    def test_verify_hash_and_find_launch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"TensorTopK.hip"
            p.write_text("bool should_use_multiblock(int n) {\n return n>1;\n}\n"
                         "void mbtopk(int rows) { dim3 grid(rows); hipLaunchKernelGGL(k,grid,1); }\n")
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            ref={"t1_04_static_candidate":{"retained_pre_review_source":{"sha256":h}}}
            r=src.audit(p,ref)
            self.assertEqual(r["sha256"],h)
            self.assertTrue(r["function_spans"])
            self.assertFalse(r["source_binary_build_link_proven"])
            self.assertGreater(r["matching_line_count"],0)
            ref["t1_04_static_candidate"]["retained_pre_review_source"]["sha256"]="bad"
            with self.assertRaisesRegex(ValueError,"SHA mismatch"):src.audit(p,ref)
    def test_log_contains_hash_not_proof(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"build.log"
            p.write_text("sha_src sha_elf clang++ TensorTopK.hip")
            r=src.inspect_log(p,"sha_src","sha_elf")
            self.assertTrue(r["source_hash_literal_found"])
            self.assertEqual(r["build_link_verdict"],"not-proven")

class KFD(unittest.TestCase):
    def test_fence_path_source_and_no_errno(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"kfd_device_queue_manager.c"
            p.write_text('int amdkfd_fence_wait_timeout(void) { return 1; }\n'
                         'void unmap_queues_cpsch(void) { /* unsuccessful queues preemption */ }\n')
            report=kfd.assemble([kfd.scan(p)],{"reference_source":{"revision":"v7.3"},
                        "source_package_exact_match":False})
            self.assertTrue(report["reference_log_site_found"])
            self.assertTrue(report["fence_function_name_found"])
            self.assertIsNone(report["incident_return_code"])
            self.assertFalse(report["exact_cachyos_source_match"])

class SafeTrace(unittest.TestCase):
    def test_default_plan_inert_and_closed(self):
        r=trace.verdict({})
        self.assertFalse(r["eligible_for_operator_review"])
        self.assertFalse(r["trace_armed"])
        self.assertEqual(len(r["missing_or_false_criteria"]),6)
        text=trace.generate()
        self.assertIn("kretprobe:amdkfd_fence_wait_timeout",text)
        self.assertIn("retval",text)
    def test_explicit_secondary_host_fields(self):
        x={key:True for key in ("separate_host","non_display_gpu",
              "independent_remote_control","durable_out_of_band_logs",
              "kernel_debug_source_match","rollback_recovery_plan")}
        r=trace.verdict(x)
        self.assertTrue(r["eligible_for_operator_review"])
        self.assertFalse(r["trace_armed"])

class Evidence(unittest.TestCase):
    def fixtures(self):
        orig={"t1_04_static_candidate":{"retained_pre_review_source":{"sha256":"src"},
             "binary":{"sha256":"elf","build_id":"bid"}}}
        container={"gfx803_candidates":["hip-amdgcn-amd-amdhsa--gfx803"],
            "sha256":"fatbin",
            "unbundled_output":{"sha256":"hsaco","size_bytes":16},
            "target_occurrences":{"hip-amdgcn-amd-amdhsa--gfx803":219}}
        hs={"mode":"offline-hsaco-metadata","sha256":"hsaco","size_bytes":16,
             "identity_verified":True,"metadata_kernel_count_parsed":0,
             "topk_kernel_blocks":[]}
        source={"sha256":"src","source_verified":True}
        old={"gpu_rerun":False,"gates":{"K2.06":{"status":"reference-source-mapped"}}}
        elf={"sha256":"elf","build_id":"bid","symbols_total_matches":6045,
             "extracted_fatbin":[{"sha256":"fatbin"}]}
        return orig,container,hs,source,old,elf
    def test_full_join_keeps_open_causal_gates(self):
        r=join.join(*self.fixtures(),trace=trace.verdict({}))
        self.assertEqual(r["gates"]["T1.08"]["bundle_occurrences"],219)
        self.assertEqual(r["gates"]["T1.05"]["host_symbol_count"],6045)
        self.assertEqual(r["gates"]["K2.05"]["status"],"open")
        self.assertEqual(r["gates"]["T1.07"]["status"],"open")
        self.assertEqual(r["gates"]["release"]["status"],"blocked")
        self.assertEqual(r["gpu_runs"],0)
    def test_join_rejects_fatbin_mismatch(self):
        f=list(self.fixtures())
        f[1]["sha256"]="wrong"
        with self.assertRaisesRegex(ValueError,"fatbin SHA linkage"):
            join.join(*f)
    def test_join_rejects_hsaco_mismatch(self):
        f=list(self.fixtures())
        f[2]["sha256"]="wrong"
        with self.assertRaisesRegex(ValueError,"HSACO identity"):
            join.join(*f)
    def test_join_rejects_source_mismatch(self):
        f=list(self.fixtures())
        f[3]["sha256"]="wrong"
        with self.assertRaisesRegex(ValueError,"retained source SHA"):
            join.join(*f)
    def test_join_rejects_trace_claiming_armed(self):
        f=list(self.fixtures())
        with self.assertRaisesRegex(ValueError,"cannot be admitted"):
            join.join(*f,trace={"mode":"INERT-TRACE-PLAN-ONLY","trace_armed":True})
    def test_all_new_sources_compile(self):
        for name in ("gfx803_mbtopk_hsaco_metadata",
                     "gfx803_mbtopk_retained_source_audit",
                     "gfx803_kfd_nonmes_source_audit",
                     "gfx803_kfd_safehost_trace_plan",
                     "gfx803_t109_k207_final_join"):
            p=ROOT/"scripts"/(name+".py")
            compile(p.read_text(),str(p),"exec")

if __name__=="__main__": unittest.main()
