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


def audit_roots(roots: list[Path], *, readelf: str | None = None,
                provider_roots: list[Path] | None = None) -> dict:
    roots = [Path(root).resolve() for root in roots]
    if not roots or any(not root.is_dir() for root in roots):
        raise ValueError("Each --root must be an existing directory")
    provider_roots = [Path(p).resolve() for p in (provider_roots or [])]
    if any(not root.is_dir() for root in provider_roots):
        raise ValueError("Every --provider-root must be an existing directory")
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
    provided_names: set[str] = set()
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
                    elif item.is_file():
                        provided_names.add(item.name)
                    continue
                if not item.is_file():
                    continue
                files += 1
                provided_names.add(item.name)
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
    # A packaged Nix runtime may explicitly carry dependency providers outside
    # its selected /opt/rocm and venv roots (e.g. Nix glibc, libdrm).
    # These must be DECLARED paths, never borrowed silently from /usr/lib.
    for provider in provider_roots:
        for folder, _, filenames in os.walk(provider, followlinks=False):
            for filename in filenames:
                item = Path(folder) / filename
                if not item.is_file():
                    continue
                provided_names.add(filename)
                with item.open("rb") as fd:
                    if fd.read(4) != b"\x7fELF":
                        continue
                proc = subprocess.run([readelf, "-d", str(item)], text=True,
                                      capture_output=True, check=False)
                if proc.returncode == 0:
                    provided_names.update(parse_dynamic(proc.stdout).get("SONAME", []))
    provided_names.update(sonames)
    unresolved = sorted(name for name in needed if name not in provided_names)
    for name in unresolved:
        kind = "missing-rocm-soname" if ROCM_LIB.match(name) else "missing-dt-needed"
        hazards.append({"kind": kind, "soname": name,
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
        "unresolved_dt_needed_count": len(unresolved),
        "provider_roots": [str(p) for p in provider_roots],
        "hazards": hazards,
        "passed_static_screen": len(hazards) == 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", action="append", required=True,
                    help="Nix-imported ROCm/venv root (repeat to audit together)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--provider-root", action="append", default=[],
                    help="Explicit Nix dependency roots (e.g. glibc/libdrm), not host /usr/lib")
    args = ap.parse_args()
    report = audit_roots([Path(r) for r in args.root],
                         provider_roots=[Path(p) for p in args.provider_root])
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
