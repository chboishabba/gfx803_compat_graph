#!/usr/bin/env bash
set -euo pipefail

A="$1"
B="$2"

echo "=== FILE LIST DIFF ==="
diff -qr "$A" "$B" || true

echo
echo "=== SHA256 COMPARISON ==="
find "$A" -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/a.sha
find "$B" -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/b.sha

# Helper to filter the path out so we can diff the actual sha256 sums matching by relative path
awk '{print $1, substr($2, length(A)+2)}' A="$A" /tmp/a.sha > /tmp/a_clean.sha
awk '{print $1, substr($2, length(B)+2)}' B="$B" /tmp/b.sha > /tmp/b_clean.sha

echo "Comparing file hashes..."
diff -u /tmp/a_clean.sha /tmp/b_clean.sha || echo "Differences found."
