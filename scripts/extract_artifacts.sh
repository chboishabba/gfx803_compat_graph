#!/usr/bin/env bash
set -euo pipefail

IMAGE="$1"
TAG="$2"
OUTDIR="$3"
if [[ "$OUTDIR" = /* ]]; then
  OUTDIR_ABS="$OUTDIR"
else
  OUTDIR_ABS="$(pwd)/$OUTDIR"
fi

mkdir -p "$OUTDIR_ABS"

echo "Extracting artifacts from $IMAGE:$TAG to $OUTDIR..."

cleanup_host_dir_contents() {
  local host_dir="$1"

  mkdir -p "$host_dir"

  if rm -rf "${host_dir:?}/"* 2>/dev/null; then
    return 0
  fi

  echo "Host cleanup for $host_dir failed; retrying via container helper..." >&2
  docker run --rm \
    -v "$host_dir:/work" \
    --entrypoint "" \
    "$IMAGE:$TAG" \
    bash -lc 'rm -rf /work/*'
}

extract_dir_from_container() {
  local image_path="$1"
  local host_dir="$2"

  if ! docker run --rm --entrypoint "" "$IMAGE:$TAG" sh -lc "[ -d '$image_path' ]" >/dev/null 2>&1; then
    return 0
  fi

  mkdir -p "$host_dir"
  cleanup_host_dir_contents "$host_dir"

  docker run --rm --entrypoint "" "$IMAGE:$TAG" sh -lc "cd '$image_path' && tar -cf - ." \
    | tar --no-same-owner --no-same-permissions -C "$host_dir" -xpf -
}

extract_dir_from_container "/ComfyUI/venv" "$OUTDIR_ABS/docker-venv/venv"
extract_dir_from_container "/opt/venv" "$OUTDIR_ABS/docker-venv/venv"
extract_dir_from_container "/opt/conda" "$OUTDIR_ABS/docker-venv/conda-python"

docker run --rm \
  -v "$OUTDIR_ABS:/out" \
  --entrypoint "" \
  "$IMAGE:$TAG" \
  bash -lc '
    set -euo pipefail

    mkdir -p /out/rocblas-library
    mkdir -p /out/miopen-db
    mkdir -p /out/lib-compat
    mkdir -p /out/docker-venv
    mkdir -p /out/meta

    for d in \
      /opt/rocm/lib/rocblas/library \
      /opt/rocm-*/lib/rocblas/library
    do
      if [ -d "$d" ]; then
        cp -av "$d"/. /out/rocblas-library/
        break
      fi
    done

    for d in \
      /opt/rocm/share/miopen/db \
      /opt/rocm-*/share/miopen/db
    do
      if [ -d "$d" ]; then
        cp -av "$d"/. /out/miopen-db/
        break
      fi
    done

    for f in \
      /opt/rocm/lib/libhsa-runtime64.so* \
      /opt/rocm/lib/libamdhip64.so* \
      /opt/rocm/lib/libhiprtc.so* \
      /opt/rocm/lib/libhiprtc-builtins.so* \
      /opt/rocm/lib/libMIOpen.so* \
      /opt/rocm/lib/librocblas.so* \
      /opt/rocm/lib/libamd_comgr.so* \
      /opt/rocm/lib/librocm-core.so* \
      /opt/rocm/lib/libhipblaslt.so* \
      /opt/rocm/lib/libhipblas.so* \
      /opt/rocm/lib/libhipsparse.so* \
      /opt/rocm/lib/libhipsolver.so* \
      /opt/rocm/lib/librocsolver.so* \
      /opt/rocm/lib/librocsparse.so* \
      /opt/rocm/lib/libroctx64.so* \
      /opt/rocm/lib/libhipfft.so* \
      /opt/rocm/lib/libhiprand.so* \
      /opt/rocm/lib/librccl.so* \
      /opt/rocm/lib/librocfft.so* \
      /opt/rocm/lib/librocrand.so* \
      /opt/rocm/lib/libroctracer64.so* \
      /opt/rocm/lib/librocm_smi64.so* \
      /opt/rocm/lib/librocprofiler-register.so* \
      /opt/rocm/magma/lib/libmagma.so*
    do
      cp -aLv "$f" /out/lib-compat/ 2>/dev/null || true
    done

    for f in \
      /usr/lib/x86_64-linux-gnu/libelf.so* \
      /usr/lib/x86_64-linux-gnu/libnuma.so* \
      /opt/amdgpu/lib/x86_64-linux-gnu/libdrm*.so* \
      /usr/lib/x86_64-linux-gnu/libopenblas.so* \
      /usr/lib/x86_64-linux-gnu/openblas-pthread/libopenblas.so*
    do
      cp -aLv "$f" /out/lib-compat/ 2>/dev/null || true
    done

    cd /out/lib-compat
    normalize_compat_link() {
      local lib="$1"
      local versioned
      versioned=$(ls ${lib}.so.* 2>/dev/null | sort -V | tail -1 || true)
      if [ -n "$versioned" ]; then
        local major
        major=$(echo "$versioned" | sed "s/${lib}.so.//;s/\..*//")
        ln -sf "$versioned" "${lib}.so.${major}" 2>/dev/null || true
        ln -sf "$versioned" "${lib}.so" 2>/dev/null || true
      fi
    }

    clear_execstack_flag() {
      local lib="$1"
      python - "$lib" <<'"'"'PY'"'"'
import struct
import sys

path = sys.argv[1]
PT_GNU_STACK = 0x6474E551
PF_X = 0x1

with open(path, "r+b") as f:
    ident = f.read(16)
    if ident[:4] != b"\x7fELF" or ident[4] != 2 or ident[5] != 1:
        sys.exit(0)

    f.seek(32)
    e_phoff = struct.unpack("<Q", f.read(8))[0]
    f.seek(54)
    e_phentsize = struct.unpack("<H", f.read(2))[0]
    e_phnum = struct.unpack("<H", f.read(2))[0]

    for idx in range(e_phnum):
        off = e_phoff + idx * e_phentsize
        f.seek(off)
        p_type = struct.unpack("<I", f.read(4))[0]
        p_flags_off = off + 4
        p_flags = struct.unpack("<I", f.read(4))[0]
        if p_type == PT_GNU_STACK and (p_flags & PF_X):
            f.seek(p_flags_off)
            f.write(struct.pack("<I", p_flags & ~PF_X))
            break
PY
    }

    for lib in \
      libhsa-runtime64 \
      libamdhip64 \
      libhiprtc \
      libhiprtc-builtins \
      librocm-core \
      libMIOpen \
      librocblas \
      libamd_comgr \
      libhipblaslt \
      libhipblas \
      libhipsparse \
      libhipsolver \
      librocsolver \
      librocsparse \
      libroctx64 \
      libhipfft \
      libhiprand \
      librccl \
      libmagma \
      librocfft \
      librocrand \
      libroctracer64 \
      librocm_smi64 \
      librocprofiler-register \
      libopenblas \
      libnuma \
      libelf
    do
      normalize_compat_link "$lib"
    done

    for lib in libamdhip64.so.* libhiprtc.so.* libhiprtc-builtins.so.*; do
      [ -e "$lib" ] || continue
      clear_execstack_flag "$lib"
    done

    mkdir -p /out/lib-compat/rocblas
    ln -sfn ../../rocblas-library /out/lib-compat/rocblas/library

    {
      echo "IMAGE='"$IMAGE:$TAG"'"
      echo "DATE=$(date -Iseconds)"
      echo "UNAME=$(uname -a)"
      echo "ROCM_DIRS:"
      ls -d /opt/rocm* 2>/dev/null || true
      echo
      echo "rocBLAS library files:"
      find /out/rocblas-library -maxdepth 2 -type f | sort || true
      echo
      echo "MIOpen db files:"
      find /out/miopen-db -maxdepth 2 -type f | sort || true
      echo
      echo "compat libs:"
      find /out/lib-compat -maxdepth 1 -type f | sort || true
      echo
      echo "python env roots:"
      ls -d /out/docker-venv/* 2>/dev/null || true
    } > /out/meta/info.txt
  '

echo "Done! Check $OUTDIR_ABS/meta/info.txt for details."
