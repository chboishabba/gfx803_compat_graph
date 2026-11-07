import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.gfx803_oci_runtime_contract import (
    REQUIRED_IMAGE_ENV, RuntimeEnvironmentError, inspect_runtime,
)


def image():
    return {"Env": [key + "=" + val for key, val in REQUIRED_IMAGE_ENV.items()]}


class OciRuntimeContractTests(unittest.TestCase):
    def test_exact_schaka_preload_is_required_and_relocated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shim = root / "lib/libgfx803_sgemm_shim.so"
            shim.parent.mkdir()
            shim.write_bytes(b"fixture")
            (root / "lib/librocm-openblas.so.0.3").write_bytes(b"fixture")
            (root / "lib/libopenblas.so.0").symlink_to("librocm-openblas.so.0.3")
            report = inspect_runtime(image(), rocm_stage=root,
                                     rocm_store="/nix/store/" + "a"*32 + "-rocm")
            self.assertEqual(
                report["shim_nix_preload_path"],
                "/nix/store/" + "a"*32 + "-rocm/lib/libgfx803_sgemm_shim.so")
            self.assertTrue(report["shim_staged_file_observed"])
            self.assertEqual(report["gpu_numerical_parity"], "unverified")

    def test_missing_ld_preload_fails(self):
        obj = image()
        obj["Env"] = [x for x in obj["Env"] if not x.startswith("LD_PRELOAD=")]
        with self.assertRaisesRegex(RuntimeEnvironmentError, "LD_PRELOAD"):
            inspect_runtime(obj)

    def test_foreign_preload_is_not_accepted_as_equivalent(self):
        obj = image()
        obj["Env"] = [x.replace("/opt/rocm/lib/libgfx803_sgemm_shim.so",
                               "/tmp/rogue.so") for x in obj["Env"]]
        with self.assertRaisesRegex(RuntimeEnvironmentError, "LD_PRELOAD"):
            inspect_runtime(obj)

    def test_shim_disabled_in_image_is_rejected(self):
        obj = image()
        obj["Env"].append("GFX803_SGEMM_SHIM_DISABLE=1")
        with self.assertRaisesRegex(RuntimeEnvironmentError, "disables"):
            inspect_runtime(obj)

    def test_missing_staged_preload_library_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(RuntimeEnvironmentError, "lacks"):
                inspect_runtime(image(), rocm_stage=Path(td))

    def test_preload_symlink_cannot_escape_selected_staging_tree(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "stage"
            shim = root / "lib/libgfx803_sgemm_shim.so"
            shim.parent.mkdir(parents=True)
            external = Path(td) / "foreign.so"
            external.write_bytes(b"fixture")
            shim.symlink_to(external)
            with self.assertRaisesRegex(RuntimeEnvironmentError, "escapes"):
                inspect_runtime(image(), rocm_stage=root)

    def test_duplicate_or_missing_env_declines(self):
        obj = image()
        obj["Env"].append("LD_PRELOAD=/elsewhere.so")
        with self.assertRaisesRegex(RuntimeEnvironmentError, "duplicate"):
            inspect_runtime(obj)
        with self.assertRaisesRegex(RuntimeEnvironmentError, "Env list"):
            inspect_runtime({})


if __name__ == "__main__":
    unittest.main()
