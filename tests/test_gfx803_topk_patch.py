import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/pytorch/gfx803-disable-warptopk.patch"
SORT_PATCH = ROOT / "patches/pytorch/gfx803-topk-sort-fallback.patch"
VERIFY = ROOT / "scripts/verify-schaka-pytorch-topk-patch.sh"


class Gfx803TopKPatchContractTests(unittest.TestCase):
    def test_warp_patch_is_architecture_scoped(self):
        text = PATCH.read_text(encoding="utf-8")
        diff = text.split("diff --git", 1)[1]
        self.assertIn("bool should_use_warp_topk", text)
        self.assertIn("properties->gcnArchName", diff)
        self.assertIn('constexpr char gfx803[] = "gfx803"', diff)
        self.assertIn("return false;", diff)
        self.assertIn("sbtopk", diff)
        self.assertNotIn("torch.sort", diff)

    def test_sort_patch_is_architecture_scoped_and_uses_existing_dispatch(self):
        text = SORT_PATCH.read_text(encoding="utf-8")
        diff = text.split("diff --git", 1)[1]
        self.assertIn("bool should_use_sort", text)
        self.assertIn("<ATen/detail/CUDAHooksInterface.h>", diff)
        self.assertIn('getCUDAHooks().isGPUArch({"gfx803"})', diff)
        self.assertIn("GFX803_TOPK_SORT_FALLBACK_PATCH", diff)
        self.assertNotIn("properties->gcnArchName", diff)
        self.assertNotIn("std::strncmp", diff)
        self.assertIn("return true;", diff)
        self.assertIn("kBool", diff)
        self.assertNotIn("torch.sort", diff)

    def test_verifier_requires_exact_pytorch_revision_and_non_mutating_check(self):
        text = VERIFY.read_text(encoding="utf-8")
        self.assertIn("d70fd61bab718a3d49b053efa8058efc0566b2b0", text)
        self.assertIn("git -C \"$SOURCE\" apply --check", text)
        self.assertIn("$WARP_PATCH", text)
        self.assertIn("$SORT_PATCH", text)
        self.assertNotIn("git -C \"$SOURCE\" apply \"$PATCH_FILE\"", text)


if __name__ == "__main__":
    unittest.main()
