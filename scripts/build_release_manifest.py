#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Build a release manifest from benchmark results.")
    parser.add_argument("--results", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--stack-id", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--patch-set", action="append", default=[])
    parser.add_argument("--install-note", action="append", default=[])
    return parser.parse_args()


def main():
    args = parse_args()
    rows = []
    for line in Path(args.results).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))

    manifest = {
        "release_id": args.release_id,
        "stack_id": args.stack_id,
        "patch_set": args.patch_set,
        "benchmark_summary": {
            "record_count": len(rows),
            "statuses": {row["record_id"]: row["status"] for row in rows},
            "max_drift_by_profile": {
                row["profile"]: row.get("metrics", {}).get("max_drift", 0.0) for row in rows
            },
        },
        "install_notes": args.install_note,
        "records": rows,
    }
    Path(args.out).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
