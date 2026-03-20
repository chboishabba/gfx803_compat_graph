#!/usr/bin/env bash
# extract-ollama-reference-artifacts.sh
# Extract the minimum Ollama reference artifact set from
# robertrosenbusch/rocm6_gfx803_ollama:6.4.3_0.11.5.
#
# Includes:
# - Ollama runtime binary and build-time ROCm discovery patch files
# - build/lib/ollama runtime plugins used by the GPU path
# - the minimal observed ROCm 6.4.3 shared objects for gfx803
# - tiny rocBLAS/MIOpen helper files used by the same image

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

IMAGE="${OLLAMA_IMAGE:-robertrosenbusch/rocm6_gfx803_ollama}"
TAG="${OLLAMA_TAG:-6.4.3_0.11.5}"
FULL_IMAGE="${OLLAMA_IMAGE_TAG:-$IMAGE:$TAG}"

OUTDIR_ABS="${OLLAMA_OUTDIR:-$REPO_ROOT/artifacts/ollama_reference}"
ROCM_DIR="/opt/rocm-6.4.3"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker binary not found in PATH." >&2
  exit 1
fi

if ! docker image inspect "$FULL_IMAGE" >/dev/null 2>&1; then
  echo "Image $FULL_IMAGE not found locally; pulling..."
  docker pull "$FULL_IMAGE"
fi

mkdir -p "$OUTDIR_ABS"/{ollama-bin,rocm-6.4.3/lib,rocm-6.4.3/lib/rocblas/library,rocm-6.4.3/share/miopen/db,opt/amdgpu/lib/x86_64-linux-gnu,meta}

echo "Extracting from $FULL_IMAGE into $OUTDIR_ABS"

docker run --rm --entrypoint "" \
  --volume "$OUTDIR_ABS:/out" \
  "$FULL_IMAGE" sh -lc '
set -e

OUT=/out
ROCM_DIR='"'"'"$ROCM_DIR"'"'"'

mkdir -p "$OUT/ollama-bin" \
  "$OUT/rocm-6.4.3/lib" \
  "$OUT/rocm-6.4.3/lib/rocblas/library" \
  "$OUT/rocm-6.4.3/share/miopen/db" \
  "$OUT/opt/amdgpu/lib/x86_64-linux-gnu" \
  "$OUT/ollama-bin/build/lib/ollama" \
  "$OUT/ollama-bin/discover" \
  "$OUT/meta"

cp -a /ollama/ollama "$OUT/ollama-bin/"
cp -a /ollama/build/lib/ollama/*.so* "$OUT/ollama-bin/build/lib/ollama/"
cp -a /ollama/discover/gpu.go "$OUT/ollama-bin/discover/"
cp -a /ollama/CMakeLists.txt "$OUT/ollama-bin/"

for lib in \
  libamdhip64.so* \
  libhsa-runtime64.so* \
  libhipblas.so* \
  librocblas.so* \
  librocsolver.so* \
  libhipblaslt.so* \
  libroctx64.so* \
  librocprofiler-register.so* \
  librocfft.so* \
  librocsparse.so* \
  librocblas.* \
  ; do
  cp -a "$ROCM_DIR/lib/$lib" "$OUT/rocm-6.4.3/lib/" 2>/dev/null || true
done

cp -a "$ROCM_DIR/share/rocblas/library/"*gfx803* "$OUT/rocm-6.4.3/lib/rocblas/library/" 2>/dev/null || true
cp -a "$ROCM_DIR/share/miopen/db/"*gfx803* "$OUT/rocm-6.4.3/share/miopen/db/" 2>/dev/null || true

for drm_glob in \
  /opt/amdgpu/lib/x86_64-linux-gnu/libdrm.so* \
  /opt/amdgpu/lib/x86_64-linux-gnu/libdrm_amdgpu.so* \
  /opt/amdgpu/lib/x86_64-linux-gnu/libdrm_radeon.so* \
  ; do
  cp -a $drm_glob "$OUT/opt/amdgpu/lib/x86_64-linux-gnu/" 2>/dev/null || true
done

ldd /ollama/build/lib/ollama/libggml-hip.so > "$OUT/meta/libggml-hip.ldd.txt"
ldd /ollama/ollama > "$OUT/meta/ollama.ldd.txt"

cat "$ROCM_DIR/lib/libamdhip64.so*" >/dev/null 2>&1 || true
'

if [ ! -f "$OUTDIR_ABS/ollama-bin/ollama" ]; then
  echo "ERROR: Extraction failed to copy Ollama binary." >&2
  exit 1
fi

if [ ! -f "$OUTDIR_ABS/ollama-bin/build/lib/ollama/libggml-hip.so" ]; then
  echo "ERROR: Expected libggml-hip.so was not copied." >&2
  exit 1
fi

if [ ! -f "$OUTDIR_ABS/opt/amdgpu/lib/x86_64-linux-gnu/libdrm_amdgpu.so.1" ]; then
  echo "ERROR: Expected AMDGPU libdrm runtime was not copied." >&2
  exit 1
fi

cat > "$OUTDIR_ABS/meta/extract-manifest.txt" <<EOF
image=$FULL_IMAGE
extracted_at=$(date -Iseconds)
outdir=$OUTDIR_ABS
ollama_binary=$OUTDIR_ABS/ollama-bin/ollama
host_rocm_dir=$OUTDIR_ABS/rocm-6.4.3
cpu_elf_deps=$OUTDIR_ABS/meta/ollama.ldd.txt
hip_elf_deps=$OUTDIR_ABS/meta/libggml-hip.ldd.txt
EOF

cat <<EOF
Done.

Artifacts:
- $OUTDIR_ABS/ollama-bin/ollama
- $OUTDIR_ABS/ollama-bin/build/lib/ollama/*.so
- $OUTDIR_ABS/ollama-bin/discover/gpu.go
- $OUTDIR_ABS/ollama-bin/CMakeLists.txt
- $OUTDIR_ABS/rocm-6.4.3/lib/*.so
- $OUTDIR_ABS/rocm-6.4.3/lib/rocblas/library/*gfx803*
- $OUTDIR_ABS/rocm-6.4.3/share/miopen/db/*gfx803*
- $OUTDIR_ABS/opt/amdgpu/lib/x86_64-linux-gnu/libdrm*.so*

Run-time deps written to:
- $OUTDIR_ABS/meta/ollama.ldd.txt
- $OUTDIR_ABS/meta/libggml-hip.ldd.txt
EOF
