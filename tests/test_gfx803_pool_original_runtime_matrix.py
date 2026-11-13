"""Offline regression tests for exact-binary pooling controls and KFD doorbell diagnosis."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def module(name):
    src=ROOT/"scripts"/(name+".py")
    spec=importlib.util.spec_from_file_location(name,src)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

pool=module("gfx803_pool_original_runtime_matrix")
kfd=module("gfx803_kfd_doorbell_audit")

class OriginalPoolDiagnostics(unittest.TestCase):
    def test_expected_controls_not_confused_with_kernel_patch(self):
        self.assertEqual(list(pool.CONTROLS)[0],"baseline")
        self.assertEqual(pool.CONTROLS["serialize"]["AMD_SERIALIZE_KERNEL"],"3")
        self.assertEqual(pool.CONTROLS["fragment-off"]["HSA_DISABLE_FRAGMENT_ALLOCATOR"],"1")
        self.assertEqual(pool.CONTROLS["sdma-off"]["HSA_ENABLE_SDMA"],"0")
        self.assertEqual(pool.CONTROLS["irq-poll"]["HSA_ENABLE_INTERRUPT"],"0")
        self.assertNotIn("hqd_sdma_get_doorbell",str(pool.CONTROLS))

    def test_original_full_42_case_numeric_contract(self):
        self.assertEqual(pool.classify(0,b"",b"SUMMARY: 42 cases tested, 0 WRONG")["status"],"pass")
        self.assertEqual(pool.classify(0,b"",b"SUMMARY: 41 cases tested, 0 WRONG")["status"],"missing-summary")
        self.assertEqual(pool.classify(1,b"",b"SUMMARY: 42 cases tested, 1 WRONG")["status"],"numeric-fail")
        self.assertEqual(pool.classify(-11,b"",b"")["status"],"fault")
        self.assertEqual(pool.classify(None,b"",b"")["status"],"timeout")
        self.assertEqual(pool.classify(0,b"",b"")["status"],"missing-summary")

    def test_kfd_audit_distinguishes_vm_fault_from_doorbell(self):
        self.assertTrue(kfd.PATTERNS["gpu_vm_fault"].search("GPU page not present"))
        self.assertTrue(kfd.PATTERNS["sdma_or_doorbell"].search("hqd_sdma_get_doorbell"))
        self.assertFalse(kfd.PATTERNS["sdma_or_doorbell"].search("GPU page not present"))
        self.assertEqual(len(kfd.PATCHES),2)

    def test_historical_whisperx_reset_signature_is_separate(self):
        evidence="ring gfx timeout, GPU reset begin, BACO reset, VRAM is lost due to GPU reset"
        self.assertTrue(kfd.PATTERNS["whisperx_reset_wave"].search(evidence))
        self.assertFalse(kfd.PATTERNS["sdma_or_doorbell"].search(evidence))
        self.assertTrue(kfd.PATTERNS["gpu_vm_fault"].search("VM fault page not present"))
        self.assertFalse(kfd.PATTERNS["whisperx_reset_wave"].search("VM fault page not present"))

    def test_source_callback_audit_not_proof_of_running_kernel(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a=root/"drivers/gpu/drm/amd/amdgpu"
            a.mkdir(parents=True)
            for suffix in ("v7","v8"):
                (a/f"amdgpu_amdkfd_gfx_{suffix}.c").write_text(
                    "static uint32_t kgd_hqd_sdma_get_doorbell(void) {return 0;}\n"
                    ".hqd_sdma_get_doorbell = kgd_hqd_sdma_get_doorbell,\n")
            result=kfd.kernel_source_check(root)
            self.assertEqual(result["status"],"source-callbacks-present")
            self.assertFalse(result["patch_presence_verified"])

    def test_scripts_compile(self):
        for name in ("gfx803_pool_original_runtime_matrix","gfx803_kfd_doorbell_audit"):
            src=ROOT/"scripts"/(name+".py")
            compile(src.read_text(),str(src),"exec")

if __name__=="__main__":unittest.main()
