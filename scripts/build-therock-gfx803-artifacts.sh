#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

THEROCK_REPO_URL="${THEROCK_REPO_URL:-https://github.com/lucbruni-amd/TheRock.git}"
THEROCK_REF="${THEROCK_REF:-3d4ad6093a0069876fbfff590bb56ddb340ae9c5}"
OUT_ROOT="${THEROCK_GFX803_OUT_ROOT:-$REPO_ROOT/artifacts/therock-gfx803}"
WORK_ROOT="${THEROCK_GFX803_WORK_ROOT:-$OUT_ROOT/work}"
SRC_ROOT="$WORK_ROOT/TheRock"
BUILD_DIR="$SRC_ROOT/build-gfx803"
VENV_DIR="$WORK_ROOT/venv"
DIST_ROOT="$OUT_ROOT/rocm"
MODE="full"
PREPARE_ONLY=0

usage() {
  cat <<'USAGE'
Usage: build-therock-gfx803-artifacts.sh [--prepare-only] [--core-only] [--full]

Build a modern gfx803/Polaris ROCm artifact from Luca Bruni's TheRock restoration
commit and materialize the resulting ROCm tree under artifacts/therock-gfx803/.

Defaults:
- source: https://github.com/lucbruni-amd/TheRock.git
- pinned restoration commit: 3d4ad6093a0069876fbfff590bb56ddb340ae9c5
- target family: gfx803-dgpu
- mode: full TheRock target with the upstream patch's explicit gfx8 exclusions
- output: artifacts/therock-gfx803/rocm

Options:
- --prepare-only  clone/pin sources and apply the gfx803 patch tag, but do not configure/build
- --core-only     build only TheRock core as a fast enumeration/HIP/OpenCL bring-up lane
- --full          build the full gfx803 target allowed by the restoration commit (default)

Environment overrides:
- THEROCK_REPO_URL
- THEROCK_REF
- THEROCK_GFX803_OUT_ROOT
- THEROCK_GFX803_WORK_ROOT
- MAX_JOBS
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) PREPARE_ONLY=1 ;;
    --core-only) MODE="core" ;;
    --full) MODE="full" ;;
    --help|-h) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

for tool in git cmake ninja python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: required tool not found: $tool" >&2
    exit 1
  fi
done

mkdir -p "$WORK_ROOT" "$OUT_ROOT/meta"

if [ ! -d "$SRC_ROOT/.git" ]; then
  git clone "$THEROCK_REPO_URL" "$SRC_ROOT"
else
  git -C "$SRC_ROOT" remote set-url origin "$THEROCK_REPO_URL"
  git -C "$SRC_ROOT" fetch --tags origin
fi

git -C "$SRC_ROOT" fetch origin "$THEROCK_REF" || true
git -C "$SRC_ROOT" checkout --detach "$THEROCK_REF"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$SRC_ROOT/requirements.txt"

(
  cd "$SRC_ROOT"
  python3 ./build_tools/fetch_sources.py --patch-tag gfx803
)

cat > "$OUT_ROOT/meta/source.env" <<EOF
lane=therock-gfx803
source_repo=$THEROCK_REPO_URL
source_ref=$THEROCK_REF
target_family=gfx803-dgpu
mode=$MODE
patch_tag=gfx803
created_at=$(date -Iseconds)
EOF

cat > "$OUT_ROOT/meta/unsupported_component_frontier.txt" <<'EOF'
# unsupported_component_frontier
# These are excluded by the pinned gfx803 restoration commit because they do
# not currently have a usable gfx8 kernel/support path in that TheRock lane.
hipBLASLt
hipSPARSELt
composable_kernel
rocWMMA
rocprofiler-compute
MIOpen
EOF

if [ "$PREPARE_ONLY" = "1" ]; then
  echo "Prepared pinned TheRock gfx803 source lane at $SRC_ROOT"
  echo "Metadata: $OUT_ROOT/meta/source.env"
  exit 0
fi

CMAKE_ARGS=(
  -B "$BUILD_DIR"
  -S "$SRC_ROOT"
  -GNinja
  -DTHEROCK_AMDGPU_FAMILIES=gfx803-dgpu
)
if [ "$MODE" = "core" ]; then
  CMAKE_ARGS+=(
    -DTHEROCK_ENABLE_ALL=OFF
    -DTHEROCK_ENABLE_CORE=ON
  )
fi

cmake "${CMAKE_ARGS[@]}"
MAX_JOBS="${MAX_JOBS:-$(nproc)}" ninja -C "$BUILD_DIR" -j "$MAX_JOBS"

if [ ! -d "$BUILD_DIR/dist/rocm" ]; then
  echo "ERROR: expected TheRock distribution not found: $BUILD_DIR/dist/rocm" >&2
  exit 1
fi

rm -rf "$DIST_ROOT"
mkdir -p "$DIST_ROOT"
cp -a "$BUILD_DIR/dist/rocm/." "$DIST_ROOT/"

ROCMINFO_STATUS="not-run"
CLINFO_STATUS="not-run"
if [ -x "$DIST_ROOT/bin/rocminfo" ]; then
  if LD_LIBRARY_PATH="$DIST_ROOT/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
      "$DIST_ROOT/bin/rocminfo" >"$OUT_ROOT/meta/rocminfo.txt" 2>&1; then
    ROCMINFO_STATUS="pass"
  else
    ROCMINFO_STATUS="fail"
  fi
fi

if command -v clinfo >/dev/null 2>&1 && [ -f "$DIST_ROOT/lib/opencl/libamdocl64.so" ]; then
  if LD_LIBRARY_PATH="$DIST_ROOT/lib:$DIST_ROOT/lib/opencl${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
      OCL_ICD_FILENAMES="$DIST_ROOT/lib/opencl/libamdocl64.so" \
      clinfo >"$OUT_ROOT/meta/clinfo.txt" 2>&1; then
    CLINFO_STATUS="pass"
  else
    CLINFO_STATUS="fail"
  fi
fi

cat > "$OUT_ROOT/meta/smoke.env" <<EOF
rocminfo=$ROCMINFO_STATUS
clinfo=$CLINFO_STATUS
EOF

cat <<EOF
TheRock gfx803 artifact materialized.
  source:   $THEROCK_REPO_URL@$THEROCK_REF
  mode:     $MODE
  artifact: $DIST_ROOT
  rocminfo: $ROCMINFO_STATUS
  clinfo:   $CLINFO_STATUS

Publish the artifact through the existing binary-cache path with:
  bash scripts/publish-ollama-and-extracted-artifacts-to-cachix.sh artifacts/therock-gfx803
EOF
