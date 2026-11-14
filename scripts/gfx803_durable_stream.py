#!/usr/bin/env python3
"""Durably store stream lines before a forced reboot, no GPU operations.

For manual bpftrace output only; stdout line-by-line + per-line fsync. The
input process must be started separately, never by this program. Refuses
existing files to protect original evidence. No buffering if -u is used.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys


def record(stream, path: Path, *, echo: bool = True) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("x", encoding="utf-8", buffering=1) as out:
        for line in stream:
            out.write(line)
            out.flush()
            os.fsync(out.fileno())
            count += 1
            if echo:
                print(line, end="", flush=True)
    return count


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        record(sys.stdin, args.out)
    except (OSError, UnicodeError) as exc:
        p.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
