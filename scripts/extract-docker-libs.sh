#!/usr/bin/env bash
# extract-docker-libs.sh
# Extracts the complete ROCm 6.4 userspace from a known-good image into lib-compat/
# so they can be used on the host via LD_LIBRARY_PATH (no Docker required).
#
# Run this once. After it completes, source scripts/polaris-env.sh.
# Usage: GFX803_COMPAT_IMAGE=itir:latest bash scripts/extract-docker-libs.sh [dest-dir]

set -euo pipefail

IMAGE="${GFX803_COMPAT_IMAGE:-itir:latest}"
DEST="${1:-lib-compat}"
mkdir -p "$DEST"

echo "=== Extracting ROCm 6.4 Polaris compat libs from $IMAGE ==="
echo "Destination: $DEST"
echo ""

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Local image $IMAGE not found. Pulling it now..."
  docker pull "$IMAGE"
fi

# Use the docker image to find and copy everything PyTorch needs at runtime.
# We ask the container to:
#  1. Start the venv
#  2. Run python to find torch's own lib dependencies via ldd
#  3. Copy everything from /opt/rocm that isn't a system lib
docker run --rm --entrypoint "" -v "$(pwd)/$DEST:/mnt" "$IMAGE" sh -c '
  VENV=/Whisper-WebUI/venv
  TORCH_LIB=$VENV/lib/python3.10/site-packages/torch/lib

  # --- Core ROCm runtime (the "gfx803 unlock" layer) ---
  for f in /opt/rocm/lib/libhsa-runtime64.so*; do cp "$f" /mnt/ 2>/dev/null || true; done
  for f in /opt/rocm/lib/libamdhip64.so*; do cp "$f" /mnt/ 2>/dev/null || true; done
  for f in /opt/rocm/lib/libhiprtc*.so*; do cp "$f" /mnt/ 2>/dev/null || true; done
  for f in /opt/rocm/lib/librocm-core.so*; do cp "$f" /mnt/ 2>/dev/null || true; done
  for f in /opt/rocm/lib/librocprofiler-register.so*; do cp "$f" /mnt/ 2>/dev/null || true; done
  for f in /opt/rocm-6.4.1/lib/librocprofiler-register.so*; do cp "$f" /mnt/ 2>/dev/null || true; done

  # --- MIOpen (convolution — the solver we are testing) ---
  for f in /opt/rocm/lib/libMIOpen.so*; do cp "$f" /mnt/ 2>/dev/null || true; done

  # --- rocBLAS (GEMM — GemmFwdRest lives here) ---
  for f in /opt/rocm/lib/librocblas.so*; do cp "$f" /mnt/ 2>/dev/null || true; done
  for f in /opt/rocm/lib/libhipblas.so*; do cp "$f" /mnt/ 2>/dev/null || true; done

  # --- AMD code object manager (needed for JIT kernel loading) ---
  for f in /opt/rocm/lib/libamd_comgr.so*; do cp "$f" /mnt/ 2>/dev/null || true; done

  # --- amdgpu specific DRM ---
  for f in /opt/amdgpu/lib/x86_64-linux-gnu/libdrm*.so*; do cp "$f" /mnt/ 2>/dev/null || true; done

  # --- System runtime deps (elfutils, numa) ---
  for f in /usr/lib/x86_64-linux-gnu/libelf.so*; do cp "$f" /mnt/ 2>/dev/null || true; done
  for f in /usr/lib/x86_64-linux-gnu/libnuma.so*; do cp "$f" /mnt/ 2>/dev/null || true; done
  for f in /usr/lib/x86_64-linux-gnu/libomp.so* /usr/lib/libomp.so*; do cp "$f" /mnt/ 2>/dev/null || true; done

  # --- CTranslate2 runtime sidecar for WhisperX / Whisper-WebUI ---
  for f in /opt/conda/lib/libctranslate2.so* /opt/conda/envs/*/lib/libctranslate2.so*; do
    cp "$f" /mnt/ 2>/dev/null || true
  done

  # --- Torch internal HIP/ROCm libs (already linked into torch but sometimes needed) ---
  for f in $TORCH_LIB/libamdhip64.so* $TORCH_LIB/librocblas.so* $TORCH_LIB/libMIOpen.so*; do
    cp "$f" /mnt/ 2>/dev/null || true
  done

  # --- Fix: create versioned symlinks for anything missing ---
  cd /mnt
  for lib in libhsa-runtime64 libamdhip64 libhiprtc libhiprtc-builtins librocm-core libMIOpen librocblas libhipblas libamd_comgr librocprofiler-register libctranslate2; do
    # find the highest version file
    versioned=$(ls ${lib}.so.* 2>/dev/null | grep -v -E "^\.|^$" | sort -V | tail -1 || true)
    if [ -n "$versioned" ]; then
      major=$(echo "$versioned" | sed "s/${lib}.so.//;s/\..*//")
      ln -sf "$versioned" "${lib}.so.${major}" 2>/dev/null || true
      ln -sf "$versioned" "${lib}.so" 2>/dev/null || true
    fi
  done

  if [ -f libomp.so ] && [ ! -e libomp.so.5 ]; then
    ln -sf libomp.so libomp.so.5 2>/dev/null || true
  fi

  echo "ok"
  ls /mnt/ | sort
'

echo ""
echo "=== Contents of $DEST/ ($(ls "$DEST" | wc -l) files) ==="
ls -lh "$DEST/"

echo ""
echo "=== ROCm version in $IMAGE ==="
docker run --rm --entrypoint "" "$IMAGE" cat /opt/rocm/.info/version 2>/dev/null || echo "unknown"

echo ""
echo "Done! Now run:"
echo "  source scripts/polaris-env.sh"
