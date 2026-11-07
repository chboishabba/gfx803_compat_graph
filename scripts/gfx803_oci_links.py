#!/usr/bin/env python3
"""Stage selected Schaka OCI /opt trees for Nix without host absolute symlinks.

Resolve OCI symlinks INSIDE the extracted image root, not on the Nix build host.
This converts /etc/alternatives/rocm-* -> /opt/rocm/core-X.Y/... aliases
into relative in-tree paths. External dependencies remain explicitly reported,
not silently rewritten to the host filesystem. This is a staging operation,
NOT ELF relocation or an accepted closure.
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import shutil
from pathlib import Path, PurePosixPath


class ImageLinkError(ValueError):
    pass


def image_resolve(rootfs: Path, container_path: str, limit: int = 64) -> str:
    """Resolve all symlink components inside rootfs using container POSIX paths."""
    if not container_path.startswith("/"):
        raise ImageLinkError("expected absolute container path")
    current = posixpath.normpath(container_path)
    visited: set[str] = set()
    for _ in range(limit):
        if current in visited:
            raise ImageLinkError("symlink cycle at " + current)
        visited.add(current)
        pieces = PurePosixPath(current).parts[1:]
        rewritten = False
        for i in range(1, len(pieces) + 1):
            fragment = "/".join(pieces[:i])
            at = rootfs / fragment
            if not at.is_symlink():
                continue
            target = os.readlink(at)
            if target.startswith("/"):
                base = target
            else:
                base = posixpath.join("/", *pieces[:i-1], target)
            rest = "/".join(pieces[i:])
            current = posixpath.normpath(posixpath.join(base, rest))
            rewritten = True
            break
        if not rewritten:
            return current
    raise ImageLinkError("symlink resolution exceeded hop limit")


def stage_tree(rootfs: Path, tree: str, destination: Path,
               relocate_external: dict[str, str] | None = None) -> dict:
    if tree not in ("/opt/rocm", "/opt/venv"):
        raise ValueError("refuse non-allowlisted OCI subtree " + tree)
    rootfs = Path(rootfs).resolve(strict=True)
    source = rootfs / tree.lstrip("/")
    if not source.is_dir() or source.is_symlink():
        raise ValueError("missing real OCI source tree: " + str(source))
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("refuse to overwrite existing stage " + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    # The unpacked image and stage normally share scratch filesystem. Hardlink
    # immutable regular files instead of doubling a multi-GB ROCm SDK in scratch.
    # Only staged SYMLINKS are rewritten; no staged regular file is mutated.
    def hardlink_or_copy(src: str, dst: str) -> str:
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
        return dst

    shutil.copytree(source, destination, symlinks=True,
                    copy_function=hardlink_or_copy)
    external = relocate_external or {}
    staged_external: dict[str, Path] = {}
    for container_tree, relative_destination in external.items():
        if tree != "/opt/venv" or container_tree != "/root/.local/share/uv/python":
            raise ValueError("refuse non-allowlisted external OCI tree " + container_tree)
        rel = PurePosixPath(relative_destination)
        if rel.is_absolute() or ".." in rel.parts or relative_destination in ("", "."):
            raise ValueError("unsafe external relocation destination " + relative_destination)
        external_source = rootfs / container_tree.lstrip("/")
        if not external_source.is_dir() or external_source.is_symlink():
            raise ValueError("missing real external OCI tree: " + str(external_source))
        external_destination = destination / relative_destination
        if external_destination.exists() or external_destination.is_symlink():
            raise ValueError("refuse to overwrite external stage " + str(external_destination))
        shutil.copytree(external_source, external_destination, symlinks=True,
                        copy_function=hardlink_or_copy)
        staged_external[container_tree] = external_destination
    replaced, retained, unresolved = [], [], []
    for folder, dirnames, filenames in os.walk(destination, followlinks=False):
        for name in sorted(dirnames + filenames):
            link = Path(folder) / name
            if not link.is_symlink():
                continue
            original = os.readlink(link)
            relative = link.relative_to(destination).as_posix()
            container_link = posixpath.join(tree, relative)
            if original.startswith("/"):
                target = original
            else:
                target = posixpath.join(posixpath.dirname(container_link), original)
            try:
                resolved = image_resolve(rootfs, target)
            except ImageLinkError as exc:
                unresolved.append({"link": relative, "target": original,
                                   "reason": str(exc)})
                continue
            image_target = rootfs / resolved.lstrip("/")
            if not image_target.exists():
                unresolved.append({"link": relative, "target": original,
                                   "resolved": resolved, "reason": "missing-image-target"})
                continue
            if resolved == tree or resolved.startswith(tree + "/"):
                subtree_target = destination / posixpath.relpath(resolved, tree)
                new_target = os.path.relpath(subtree_target, start=link.parent)
                if original != new_target:
                    link.unlink()
                    link.symlink_to(new_target, target_is_directory=image_target.is_dir())
                    replaced.append({"link": relative, "from": original, "to": new_target})
                else:
                    retained.append(relative)
            else:
                external_target = next(
                    ((root_path, staged) for root_path, staged in staged_external.items()
                     if resolved == root_path or resolved.startswith(root_path + "/")), None)
                if external_target is None:
                    unresolved.append({"link": relative, "target": original,
                                       "resolved": resolved, "reason": "outside-selected-tree"})
                    continue
                root_path, staged = external_target
                relocated_target = staged / posixpath.relpath(resolved, root_path)
                if not relocated_target.exists():
                    unresolved.append({"link": relative, "target": original,
                                       "resolved": resolved, "reason": "missing-external-stage-target"})
                    continue
                new_target = os.path.relpath(relocated_target, start=link.parent)
                link.unlink()
                link.symlink_to(new_target, target_is_directory=relocated_target.is_dir())
                replaced.append({"link": relative, "from": original, "to": new_target,
                                 "external_source": root_path})
    return {"schema_version": 1, "source": tree,
            "stage": str(destination), "rewritten": replaced,
            "retained_relative": retained, "unresolved": unresolved,
            "relocated_external_trees": sorted(staged_external),
            "all_links_relocated": len(unresolved) == 0,
            "elf_relocation": "not-verified",
            "runtime_linkage": "not-verified"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rootfs", required=True)
    p.add_argument("--tree", choices=("/opt/rocm", "/opt/venv"), required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--relocate-external", action="append", default=[], metavar="SOURCE=DEST",
                   help="allowlisted in-image external tree to copy and rewrite")
    p.add_argument("--strict", action="store_true",
                   help="fail if any OCI links escape selected subtree or dangle")
    args = p.parse_args()
    mappings = {}
    for item in args.relocate_external:
        if item.count("=") != 1:
            p.error("--relocate-external requires SOURCE=DEST")
        source, destination = item.split("=", 1)
        mappings[source] = destination
    report = stage_tree(Path(args.rootfs), args.tree, Path(args.out), mappings)
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(f"{args.tree}: {len(report['rewritten'])} links rewritten; "
          f"{len(report['unresolved'])} unresolved; report={target}")
    if args.strict and report["unresolved"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
