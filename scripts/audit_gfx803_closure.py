#!/usr/bin/env python3
"""Static gfx803 OCI-import closure audit; not a substitute for device tests."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

DYNAMIC = re.compile(r"\((NEEDED|SONAME|RUNPATH|RPATH)\).*?\[([^\]]+)\]")
ROCM_LIB = re.compile(r"^(lib(hsa-runtime64|amdhip64|hiprtc|rocblas|MIOpen|hipblas|hipblaslt|rocsolver|amd_comgr|LLVM).*)\.so", re.I)


def parse_dynamic(text: str) -> dict:
    values: dict[str, list[str]] = defaultdict(list)
    for key, value in DYNAMIC.findall(text):
        values[key].append(value)
    return dict(values)


def audit_roots(roots: list[Path], *, readelf: str | None = None) -> dict:
    roots = [Path(root).resolve() for root in roots]
    if not roots or any(not root.is_dir() for root in roots):
        raise ValueError("Each --root must be an existing directory")
    readelf = readelf or shutil.which("readelf")
    if not readelf:
        raise ValueError("readelf is required for ELF linkage audit")

    files = 0
    elf_files = 0
    total_bytes = 0
    needed: dict[str, list[str]] = defaultdict(list)
    sonames: dict[str, list[str]] = defaultdict(list)
    hazards: list[dict] = []
    dynamic_elf = []
    for root in roots:
        for folder, dirnames, filenames in os.walk(root, followlinks=False):
            # Symlinked directories must also be checked.
            for name in sorted(dirnames + filenames):
                item = Path(folder) / name
                label = str(item)
                if item.is_symlink():
                    target = os.readlink(item)
                    if os.path.isabs(target):
                        hazards.append({"kind": "absolute-symlink", "path": label,
                                        "target": target})
                    if not item.exists():
                        hazards.append({"kind": "dangling-symlink", "path": label,
                                        "target": target})
                    continue
                if not item.is_file():
                    continue
                files += 1
                total_bytes += item.stat().st_size
                with item.open("rb") as fh:
                    if fh.read(4) != b"\x7fELF":
                        continue
                elf_files += 1
                proc = subprocess.run(
                    [readelf, "-d", label], text=True, capture_output=True,
                    check=False,
                )
                if proc.returncode != 0:
                    hazards.append({"kind": "readelf-error", "path": label,
                                    "detail": proc.stderr[:250]})
                    continue
                dyn = parse_dynamic(proc.stdout)
                dynamic_elf.append(label)
                for s in dyn.get("SONAME", []):
                    sonames[s].append(label)
                for s in dyn.get("NEEDED", []):
                    needed[s].append(label)
                for kind in ("RPATH", "RUNPATH"):
                    for path in dyn.get(kind, []):
                        for segment in path.split(":"):
                            if segment.startswith(("/opt/rocm", "/usr/local", "/usr/lib")):
                                hazards.append({"kind": "foreign-rpath", "path": label,
                                                "target": segment})

    if elf_files == 0:
        hazards.append({"kind": "no-elf-files",
                        "detail": "Static audit cannot pass an empty/non-ELF tree"})

    for name, paths in sorted(sonames.items()):
        if len(paths) > 1:
            hazards.append({"kind": "duplicate-soname", "soname": name,
                            "paths": sorted(paths)})
    # Don't assume all host libraries should reside inside /opt/rocm.
    # Specifically flag unresolved ROCm ABI libraries, which must never be
    # silently supplied by a different ROCm release on the host.
    unresolved_rocm = sorted(
        name for name in needed if ROCM_LIB.match(name) and name not in sonames
    )
    for name in unresolved_rocm:
        hazards.append({"kind": "missing-rocm-soname", "soname": name,
                        "consumers": sorted(needed[name])[:10]})

    return {
        "schema_version": 1,
        "audit_type": "static-elf-only",
        "admission": "not-established-by-static-audit",
        "roots": [str(root) for root in roots],
        "file_count": files,
        "elf_count": elf_files,
        "total_file_bytes": total_bytes,
        "soname_count": len(sonames),
        "dt_needed_count": len(needed),
        "hazards": hazards,
        "passed_static_screen": len(hazards) == 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", action="append", required=True,
                    help="Nix-imported ROCm/venv root (repeat to audit together)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    report = audit_roots([Path(r) for r in args.root])
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")
    print(f"{len(report['hazards'])} static linkage hazards; output {path}")
    if args.strict and report["hazards"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
