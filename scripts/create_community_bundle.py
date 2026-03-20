#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path



def parse_args():
    parser = argparse.ArgumentParser(description="Create a community benchmark submission bundle.")
    parser.add_argument("--record-file", required=True, help="JSONL result file from run_benchmark_matrix.py")
    parser.add_argument("--record-id", required=True, help="record_id to package")
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--prompt-file")
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--extra-log", action="append", default=[])
    return parser.parse_args()


def main():
    args = parse_args()
    record = None
    for line in Path(args.record_file).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        candidate = json.loads(line)
        if candidate.get("record_id") == args.record_id:
            record = candidate
            break
    if record is None:
        raise SystemExit(f"record_id not found: {args.record_id}")

    bundle_dir = Path(args.bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = bundle_dir / "artifacts"
    artifact_dir.mkdir(exist_ok=True)

    copied = []
    seen = set()
    for path_str in [record.get("artifacts", {}).get("log_file"), *args.image, *args.extra_log]:
        if not path_str:
            continue
        src = Path(path_str)
        if not src.exists():
            continue
        if src.resolve() in seen:
            continue
        seen.add(src.resolve())
        dst = artifact_dir / src.name
        shutil.copy2(src, dst)
        copied.append(str(dst.relative_to(bundle_dir)))

    manifest = {
        "bundle_version": "0.1.0",
        "workflow_id": args.workflow_id,
        "record": record,
        "copied_artifacts": copied,
    }
    if args.prompt_file:
        manifest["prompt_file"] = Path(args.prompt_file).read_text(encoding="utf-8")

    (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"bundle_dir": str(bundle_dir), "record_id": args.record_id, "copied_artifacts": copied}, indent=2))


if __name__ == "__main__":
    main()
