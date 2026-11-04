#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

CURRENT_REPO_URL="${THEROCK_REPO_URL:-https://github.com/ROCm/TheRock.git}"
CURRENT_REF="${THEROCK_REF:-4213e176e29199c5dea5b54513bc3b1d36d91ca9}"
LUCA_REPO_URL="https://github.com/lucbruni-amd/TheRock.git"
LUCA_REF="3d4ad6093a0069876fbfff590bb56ddb340ae9c5"
LUCA_PATCH1_BLOB="538d1c6c9a4a8d3a4e56574ecf5ebe7e2bb8a2af"
LUCA_PATCH2_BLOB="a1eb4e7fd6de3d665eda334e9e53db07622283a0"
LUCA_PATCH1_URL="https://raw.githubusercontent.com/lucbruni-amd/TheRock/${LUCA_REF}/patches/gfx803/rocm-systems/0001-rocr-Restore-legacy-doorbell-support-for-gfx8-Polari.patch"
LUCA_PATCH2_URL="https://raw.githubusercontent.com/lucbruni-amd/TheRock/${LUCA_REF}/patches/gfx803/rocm-systems/0002-clr-Enable-OpenCL-support-for-gfx8-Polaris-GPUs.patch"
CUSTOM_TARGET_SOURCE="$REPO_ROOT/patches/therock-gfx803/therock_custom_amdgpu_targets.cmake"
CURRENT_AGENT_PATCH="$REPO_ROOT/patches/therock-gfx803/current/0000-rocr-readmit-doorbell-type1.patch"

SOURCE_MODE="current"
MODE="full"
PREPARE_ONLY=0

usage() {
  cat <<'USAGE'
Usage: build-therock-gfx803-artifacts.sh [--prepare-only] [--core-only] [--full] [--reference-luca]

Build a modern gfx803/Polaris ROCm artifact using current ROCm/TheRock plus an
explicit gfx803 restoration patch set. Luca Bruni's March 2026 fork remains an
independent known-restored reference lane, not the primary modern source.

Primary defaults:
- source: https://github.com/ROCm/TheRock.git
- pinned current source: 4213e176e29199c5dea5b54513bc3b1d36d91ca9
- target registration: repo-owned therock_custom_amdgpu_targets.cmake
- runtime restoration: current type-1 admission patch + pinned Luca queue/CLR patches
- target family: gfx803-dgpu
- output: artifacts/therock-gfx803/

Reference lane:
- --reference-luca uses lucbruni-amd/TheRock@3d4ad6093... and its native
  --patch-tag gfx803 path, writing artifacts/therock-gfx803-reference-luca/.

Options:
- --prepare-only   clone/pin/fetch sources and prove patch applicability, but do not build
- --core-only      build TheRock core runtime first for enumeration bring-up
- --full           build the full gfx803 target allowed by the current exclusion frontier
- --reference-luca build the independently hardware-verified March reference lane

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
    --reference-luca) SOURCE_MODE="reference-luca" ;;
    --help|-h) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [ "$SOURCE_MODE" = "reference-luca" ]; then
  SOURCE_REPO_URL="$LUCA_REPO_URL"
  SOURCE_REF="$LUCA_REF"
  DEFAULT_OUT_ROOT="$REPO_ROOT/artifacts/therock-gfx803-reference-luca"
else
  SOURCE_REPO_URL="$CURRENT_REPO_URL"
  SOURCE_REF="$CURRENT_REF"
  DEFAULT_OUT_ROOT="$REPO_ROOT/artifacts/therock-gfx803"
fi

OUT_ROOT="${THEROCK_GFX803_OUT_ROOT:-$DEFAULT_OUT_ROOT}"
WORK_ROOT="${THEROCK_GFX803_WORK_ROOT:-$OUT_ROOT/work}"
SRC_ROOT="$WORK_ROOT/TheRock"
BUILD_DIR="$SRC_ROOT/build-gfx803"
VENV_DIR="$WORK_ROOT/venv"
DIST_ROOT="$OUT_ROOT/rocm"
PATCH_CACHE="$WORK_ROOT/reference-patches"

REQUIRED_TOOLS=(git cmake ninja python3)
if [ "$SOURCE_MODE" = "current" ]; then
  REQUIRED_TOOLS+=(curl)
fi
for tool in "${REQUIRED_TOOLS[@]}"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: required tool not found: $tool" >&2
    exit 1
  fi
done

mkdir -p "$WORK_ROOT" "$OUT_ROOT/meta" "$PATCH_CACHE"

if [ ! -d "$SRC_ROOT/.git" ]; then
  git clone "$SOURCE_REPO_URL" "$SRC_ROOT"
else
  git -C "$SRC_ROOT" remote set-url origin "$SOURCE_REPO_URL"
  git -C "$SRC_ROOT" fetch --tags origin
fi

git -C "$SRC_ROOT" fetch origin "$SOURCE_REF" || true
git -C "$SRC_ROOT" checkout --detach "$SOURCE_REF"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$SRC_ROOT/requirements.txt"

verify_git_blob() {
  local path="$1"
  local expected="$2"
  local actual
  actual="$(git hash-object "$path")"
  if [ "$actual" != "$expected" ]; then
    echo "ERROR: pinned patch blob mismatch for $path" >&2
    echo "  expected: $expected" >&2
    echo "  actual:   $actual" >&2
    exit 1
  fi
}

if [ "$SOURCE_MODE" = "reference-luca" ]; then
  (
    cd "$SRC_ROOT"
    python3 ./build_tools/fetch_sources.py --patch-tag gfx803
  )
  PATCH_STRATEGY="luca-native-patch-tag"
else
  if [ ! -f "$CUSTOM_TARGET_SOURCE" ]; then
    echo "ERROR: custom target registration missing: $CUSTOM_TARGET_SOURCE" >&2
    exit 1
  fi
  if [ ! -f "$CURRENT_AGENT_PATCH" ]; then
    echo "ERROR: current agent admission patch missing: $CURRENT_AGENT_PATCH" >&2
    exit 1
  fi

  (
    cd "$SRC_ROOT"
    python3 ./build_tools/fetch_sources.py
  )

  # TheRock deliberately supports this optional out-of-tree target extension.
  cp "$CUSTOM_TARGET_SOURCE" "$SRC_ROOT/cmake/therock_custom_amdgpu_targets.cmake"

  ROCM_SYSTEMS_ROOT="$SRC_ROOT/rocm-systems"
  if [ ! -d "$ROCM_SYSTEMS_ROOT/.git" ]; then
    echo "ERROR: rocm-systems submodule not materialized: $ROCM_SYSTEMS_ROOT" >&2
    exit 1
  fi

  # This workspace is disposable/rebuildable. Return the submodule to the exact
  # source pin before proving/applying our patch sequence on every run.
  git -C "$ROCM_SYSTEMS_ROOT" reset --hard HEAD
  git -C "$ROCM_SYSTEMS_ROOT" clean -fd

  PATCH1="$PATCH_CACHE/0001-luca-legacy-doorbell.patch"
  PATCH2="$PATCH_CACHE/0002-luca-clr-gfx8.patch"
  curl -fsSL "$LUCA_PATCH1_URL" -o "$PATCH1"
  curl -fsSL "$LUCA_PATCH2_URL" -o "$PATCH2"
  verify_git_blob "$PATCH1" "$LUCA_PATCH1_BLOB"
  verify_git_blob "$PATCH2" "$LUCA_PATCH2_BLOB"

  # Keep AMD's 2026 graceful-skip behavior for genuinely unsupported types,
  # but re-admit DoorbellType 1 once the queue implementation exists again.
  git -C "$ROCM_SYSTEMS_ROOT" apply --check "$CURRENT_AGENT_PATCH"
  git -C "$ROCM_SYSTEMS_ROOT" apply "$CURRENT_AGENT_PATCH"

  # Reuse Luca's tested queue implementation, excluding its older constructor
  # hunk because the current source now has the more precise type-1 admission
  # patch above.
  AGENT_PATH="projects/rocr-runtime/runtime/hsa-runtime/core/runtime/amd_gpu_agent.cpp"
  git -C "$ROCM_SYSTEMS_ROOT" apply --check --exclude="$AGENT_PATH" "$PATCH1"
  git -C "$ROCM_SYSTEMS_ROOT" apply --exclude="$AGENT_PATH" "$PATCH1"

  # CLR's gfx8 policy block and image-query fallback are an independent seam.
  git -C "$ROCM_SYSTEMS_ROOT" apply --check "$PATCH2"
  git -C "$ROCM_SYSTEMS_ROOT" apply "$PATCH2"

  PATCH_STRATEGY="current-upstream+custom-target+type1-admission+luca-queue+clr"
fi

ROCM_SYSTEMS_SHA="unknown"
if [ -d "$SRC_ROOT/rocm-systems/.git" ] || [ -f "$SRC_ROOT/rocm-systems/.git" ]; then
  ROCM_SYSTEMS_SHA="$(git -C "$SRC_ROOT/rocm-systems" rev-parse HEAD)"
fi

cat > "$OUT_ROOT/meta/source.env" <<EOF
lane=therock-gfx803
source_mode=$SOURCE_MODE
source_repo=$SOURCE_REPO_URL
source_ref=$SOURCE_REF
rocm_systems_ref=$ROCM_SYSTEMS_SHA
target_family=gfx803-dgpu
mode=$MODE
patch_strategy=$PATCH_STRATEGY
luca_reference_repo=$LUCA_REPO_URL
luca_reference_ref=$LUCA_REF
luca_patch1_blob=$LUCA_PATCH1_BLOB
luca_patch2_blob=$LUCA_PATCH2_BLOB
promotion_goal=official AMD support / Release Ready
created_at=$(date -Iseconds)
EOF

cat > "$OUT_ROOT/meta/unsupported_component_frontier.txt" <<'EOF'
# initial_exclusion_frontier
# This list follows the known-restored March reference target. Each exclusion is
# debt to classify, not a claim that gfx803 can never support the component.
hipBLASLt
hipSPARSELt
composable_kernel
rocWMMA
rocprofiler-compute
MIOpen
EOF

cat > "$OUT_ROOT/meta/promotion.env" <<'EOF'
source_prepared=pass
patch_applicability=pass
build=not-run
rocminfo_enumeration=not-run
opencl_enumeration=not-run
hip_kernel=not-run
library_smoke=not-run
numerical_correctness=not-run
async_stability=not-run
amd_build_passing=unpaid
amd_sanity_tested=unpaid
amd_release_ready=unpaid
EOF

if [ "$PREPARE_ONLY" = "1" ]; then
  echo "Prepared gfx803 source lane at $SRC_ROOT"
  echo "Source mode: $SOURCE_MODE"
  echo "Patch strategy: $PATCH_STRATEGY"
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
sed -i 's/^build=not-run$/build=pass/' "$OUT_ROOT/meta/promotion.env"

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

sed -i "s/^rocminfo_enumeration=not-run$/rocminfo_enumeration=$ROCMINFO_STATUS/" "$OUT_ROOT/meta/promotion.env"
sed -i "s/^opencl_enumeration=not-run$/opencl_enumeration=$CLINFO_STATUS/" "$OUT_ROOT/meta/promotion.env"

cat > "$OUT_ROOT/meta/smoke.env" <<EOF
rocminfo=$ROCMINFO_STATUS
clinfo=$CLINFO_STATUS
EOF

cat <<EOF
TheRock gfx803 artifact materialized.
  source:         $SOURCE_REPO_URL@$SOURCE_REF
  source mode:    $SOURCE_MODE
  patch strategy: $PATCH_STRATEGY
  mode:           $MODE
  artifact:       $DIST_ROOT
  rocminfo:       $ROCMINFO_STATUS
  clinfo:         $CLINFO_STATUS

Promotion remains query-indexed. A produced build is not yet numerical,
async-stable, or AMD Release Ready.

Publish the artifact through the existing binary-cache path with:
  bash scripts/publish-ollama-and-extracted-artifacts-to-cachix.sh "$OUT_ROOT"
EOF
