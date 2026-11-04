#!/usr/bin/env python3
"""Fail-closed source tracking and evidence-controlled promotion for gfx803.

This is release *policy*, not a replacement for the project's GPU test suites.
A passing build/import or a Schaka hardware report is never a local GPU receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Support both direct CLI invocation and imports from unit tests.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.gfx803_component_graph import parse_pins

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
STORE = re.compile(r"^/nix/store/[0-9a-z]{32}-[A-Za-z0-9+._?=-]+$")
REQUIRED = (
    "gpu_enumeration", "kernel_dispatch", "numerical_correctness",
    "repeatability", "sustained_load", "runtime_linkage",
    "source_provenance",
)
# Application/workload support must never be inferred from a passing core SDK.
# Claiming an additional capability makes its on-device log gate mandatory.
CAPABILITY_GATES = {
    "comfyui_images": ("comfyui_image",),
    "whisperx_long_run": ("async_hang_regression",),
    "ollama_gpu": ("ollama_gpu_inference",),
}
OPTIONAL = tuple(x for values in CAPABILITY_GATES.values() for x in values)


class AdmissionError(ValueError):
    pass


def load(path: str | Path) -> dict:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise AdmissionError("Expected a JSON object")
    return obj


def write(path: str | Path, obj: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_lock(lock: dict) -> None:
    if lock.get("schema_version") != 1:
        raise AdmissionError("source lock schema_version must be 1")
    if lock.get("source_repository") != "Schaka/rocm-gfx803":
        raise AdmissionError("unexpected source repository")
    if lock.get("source_branch") != "main":
        raise AdmissionError("unexpected source branch")
    if not SHA.fullmatch(str(lock.get("source_revision", ""))):
        raise AdmissionError("source revision must be a full commit SHA")
    if lock.get("image_repository") != "ghcr.io/schaka/rocm-migraphx-ort-torch-builder":
        raise AdmissionError("unexpected OCI repository")
    if not re.fullmatch(r"[0-9]+[.][0-9]+[.][0-9]+", str(lock.get("rocm_version", ""))):
        raise AdmissionError("source lock requires full X.Y.Z ROCm version")
    digest = lock.get("image_digest")
    if digest is not None and not DIGEST.fullmatch(str(digest)):
        raise AdmissionError("source lock image digest must be null or sha256")



def update_lock(lock: dict, revision: str) -> bool:
    validate_lock(lock)
    if not SHA.fullmatch(revision):
        raise AdmissionError("candidate revision must be exactly 40 lowercase hex digits")
    changed = revision != lock["source_revision"]
    if changed:
        lock["source_revision"] = revision
        # Source changes invalidate any prior image digest and admission.
        lock["image_digest"] = None
        lock["state"] = "source-pinned-image-unlocked"
    return changed


def lock_image(lock: dict, digest: str, inspection: dict) -> bool:
    """Bind the selected source revision to an independently inspected OCI digest.

    The OCI labels are a publisher assertion, not reproducible-build proof.
    Promotion separately requires actual provenance/hardware evidence.
    """
    validate_lock(lock)
    if not DIGEST.fullmatch(digest):
        raise AdmissionError("image digest must be sha256 of immutable OCI manifest")
    if inspection.get("Digest") != digest:
        raise AdmissionError("OCI inspect digest does not match selected image")
    labels = inspection.get("Labels") or {}
    mm = ".".join(lock["rocm_version"].split(".")[:2])
    expected = {
        "io.rocm.gfx803.source-rev": lock["source_revision"],
        "io.rocm.gfx803.line": "rocm" + mm,
        "io.rocm.gfx803.stage": "final",
    }
    for name, want in expected.items():
        if labels.get(name) != want:
            raise AdmissionError("OCI label mismatch: " + name)
    try:
        parse_pins(labels.get("io.rocm.gfx803.pins", ""))
    except ValueError as exc:
        raise AdmissionError("OCI component pins are not complete source SHAs: " + str(exc)) from exc
    old = lock.get("image_digest")
    if old is not None and old != digest:
        raise AdmissionError("source revision is already bound to a different image digest")
    lock["image_digest"] = digest
    lock["state"] = "source-and-image-pinned"
    return old != digest


def validate_candidate(candidate: dict, lock: dict, require_evidence: bool = False,
                       *, evidence_root: Path | None = None) -> list[str]:
    validate_lock(lock)
    problems = []
    if candidate.get("schema_version") != 1:
        problems.append("candidate schema_version must be 1")
    if candidate.get("upstream_revision") != lock["source_revision"]:
        problems.append("candidate source revision does not match lock")
    if candidate.get("rocm_version") != lock["rocm_version"]:
        problems.append("candidate ROCm release does not match lock")
    ref = candidate.get("image_ref", "")
    prefix = lock["image_repository"] + "@"
    if not (isinstance(ref, str) and ref.startswith(prefix)
            and DIGEST.fullmatch(ref[len(prefix):])):
        problems.append("image_ref must be immutable sha256 digest in selected GHCR repo")
    selected_digest = lock.get("image_digest")
    if selected_digest is not None and isinstance(ref, str) and \
            ref != prefix + selected_digest:
        problems.append("candidate image digest differs from checked-in lock")
    if require_evidence and selected_digest is None:
        problems.append("cannot promote with an unlocked OCI image digest")
    packages = candidate.get("store_paths", {})
    if not isinstance(packages, dict) or "rocm" not in packages:
        problems.append("store_paths.rocm missing")
    elif any(not STORE.fullmatch(str(value)) for value in packages.values()):
        problems.append("all store paths must be canonical /nix/store paths")
    if require_evidence:
        provenance = candidate.get("provenance", {})
        if not isinstance(provenance, dict):
            provenance = {}
        if provenance.get("upstream_commit_correspondence") != "verified":
            problems.append("source revision vs image correspondence not verified")
        if provenance.get("runtime_relocation") != "verified":
            problems.append("imported runtime relocation not verified")
        hardware = candidate.get("hardware", {})
        if not isinstance(hardware, dict) or hardware.get("arch") != "gfx803":
            problems.append("hardware.arch must be gfx803")
        for field in ("device", "kernel", "driver", "runner"):
            if not str(hardware.get(field, "")).strip():
                problems.append("missing hardware." + field)
        evidence = candidate.get("evidence", {})
        if not isinstance(evidence, dict):
            evidence = {}
        capabilities = candidate.get("claimed_capabilities", [])
        if (not isinstance(capabilities, list)
                or any(not isinstance(x, str) or x not in CAPABILITY_GATES
                       for x in capabilities)
                or len(capabilities) != len(set(capabilities))):
            problems.append("claimed_capabilities must be a unique list of supported names")
            capabilities = []
        required_receipts = list(REQUIRED)
        for claim in capabilities:
            required_receipts.extend(CAPABILITY_GATES[claim])
        for check in required_receipts:
            receipt = evidence.get(check, {})
            if not isinstance(receipt, dict) or receipt.get("status") != "pass":
                problems.append(check + ": no passing receipt")
                continue
            if not DIGEST.fullmatch("sha256:" + str(receipt.get("log_sha256", ""))):
                problems.append(check + ": missing sha256 of original evidence log")
            if not str(receipt.get("command", "")).strip():
                problems.append(check + ": missing executed command")
            if evidence_root is not None:
                rel = Path(str(receipt.get("log_path", "")))
                base = Path(evidence_root).resolve()
                log = (base / rel).resolve()
                if (not rel.parts or rel.is_absolute() or ".." in rel.parts
                        or not log.is_relative_to(base) or not log.is_file()):
                    problems.append(check + ": missing or escaping retained log")
                else:
                    digest = hashlib.sha256()
                    with log.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(chunk)
                    if digest.hexdigest() != receipt.get("log_sha256"):
                        problems.append(check + ": log sha256 mismatch")
        if candidate.get("state") not in ("candidate", "validated"):
            problems.append("candidate must not be marked accepted before promotion")
    return problems


def promote(candidate: dict, lock: dict, *, evidence_root: Path) -> dict:
    problems = validate_candidate(candidate, lock, require_evidence=True,
                                  evidence_root=evidence_root)
    if problems:
        raise AdmissionError("; ".join(problems))
    result = dict(candidate)
    result["state"] = "accepted"
    # Freeze the full source lock with each accepted release. Later candidate
    # updates must not invalidate rollback or re-publication of this release.
    result["release_source_lock"] = dict(lock)
    result["admission_scope"] = "tested-gfx803-hardware-and-declared-checks"
    # No automatic official-AMD-support or universal-correctness claim.
    result["official_amd_support"] = False
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lock", default="nix/gfx803/upstream.json")
    sub = ap.add_subparsers(dest="command", required=True)

    up = sub.add_parser("update-source", help="propose new Schaka commit, invalidate old digest")
    up.add_argument("--revision", required=True)
    candidate = sub.add_parser("check-candidate", help="validate candidate fields")
    candidate.add_argument("--manifest", required=True)
    candidate.add_argument("--strict", action="store_true")
    candidate.add_argument("--evidence-root", help="Required when --strict; real retained logs")
    img = sub.add_parser("lock-image", help="bind release to an inspected immutable image")
    img.add_argument("--digest", required=True, help="sha256 digest from skopeo inspect")
    img.add_argument("--inspect", required=True, help="JSON from skopeo inspect")
    promotion = sub.add_parser("promote", help="write accepted release only after GPU receipts")
    promotion.add_argument("--manifest", required=True)
    promotion.add_argument("--out", required=True)
    promotion.add_argument("--evidence-root", required=True,
                           help="Directory containing retained test logs used to verify sha256")

    args = ap.parse_args()
    try:
        lock = load(args.lock)
        validate_lock(lock)
        if args.command == "lock-image":
            changed = lock_image(lock, args.digest, load(args.inspect))
            if changed:
                write(args.lock, lock)
            print("image-digest-pinned" if changed else "image-digest-already-pinned")
        elif args.command == "update-source":
            changed = update_lock(lock, args.revision)
            if changed:
                write(args.lock, lock)
            print("changed" if changed else "unchanged")
        elif args.command == "check-candidate":
            if args.strict and not args.evidence_root:
                raise AdmissionError("--strict requires --evidence-root for real log checks")
            problems = validate_candidate(
                load(args.manifest), lock, args.strict,
                evidence_root=Path(args.evidence_root) if args.evidence_root else None)
            if problems:
                raise AdmissionError("; ".join(problems))
            print("candidate schema accepted; GPU admission not implied")
        elif args.command == "promote":
            accepted = promote(load(args.manifest), lock,
                               evidence_root=Path(args.evidence_root))
            write(args.out, accepted)
            print("accepted release manifest written to " + args.out)
    except (AdmissionError, ValueError, OSError) as exc:
        ap.exit(2, "NOT ADMITTED: " + str(exc) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
