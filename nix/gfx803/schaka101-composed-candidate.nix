# Build a candidate-only immutable overlay with pinned Schaka ROCm and Torch.
# Validate runtime/wheel with gfx803_101_release_assembly.py before building.
{ pkgs ? import <nixpkgs> {}
, rocmStore
, venvStore
, wheelStore
}:
let
  assertStore = s:
    if builtins.match "/nix/store/[0-9a-z]{32}-[A-Za-z0-9+._?=-]+" s == null
    then throw "expected canonical immutable Nix store path"
    else builtins.storePath s;
  rocm = assertStore rocmStore;
  venv = assertStore venvStore;
  wheel = assertStore wheelStore;
  expectedWheel =
    "/nix/store/0l9bysk6xfx9dsndx9diwqf44x0h6zf2-torch-2.14.0-gfx803-topk-sort-fallback-20261110";
in
assert wheelStore == expectedWheel;
pkgs.runCommand "gfx803-schaka101-torch-candidate-overlay" {
  nativeBuildInputs = [ pkgs.unzip pkgs.coreutils pkgs.findutils ];
} ''
  set -euo pipefail
  mkdir -p "$out/torch-site" "$out/bin" "$out/share/gfx803"
  # Cachix restores this fixed-output wheel as a single Nix store file,
  # whereas a local build artifact is a directory containing the .whl.  Both
  # forms are content-addressed by wheelStore; normalize only the lookup.
  if test -f "${wheel}"; then
    wheelFile="${wheel}"
  else
    find "${wheel}" -type f -name '*.whl' > "$TMPDIR/wheel-list"
    test "$(wc -l < "$TMPDIR/wheel-list")" -eq 1 || {
      echo "require one wheel file in the pinned wheel store" >&2
      exit 1
    }
    wheelFile="$(cat "$TMPDIR/wheel-list")"
  fi
  printf '%s  %s\n' '0968548982ba69858d2dfe4ec0090ef1ce41ed610f0f9b3b9f38aebe0f0319eb' "$wheelFile" | sha256sum -c -
  unzip -q "$wheelFile" -d "$out/torch-site"
  test -f "$out/torch-site/torch/__init__.py"
  test -d "${rocm}/core-10.1/lib"
  test -f "${rocm}/lib/libgfx803_sgemm_shim.so"
  test -x "${venv}/bin/python"
  ln -s "${rocm}" "$out/rocm"
  ln -s "${venv}" "$out/original-venv"
  ln -s "${wheel}" "$out/pinned-wheel"
  cat > "$out/bin/gfx803-schaka101-python" <<EOF
#!${pkgs.bash}/bin/bash
set -euo pipefail
export PYTHONNOUSERSITE=1
export PYTHONPATH="$out/torch-site"
export LD_LIBRARY_PATH="${rocm}/lib:${rocm}/core-10.1/lib"
export LD_PRELOAD="${rocm}/lib/libgfx803_sgemm_shim.so"
exec "${venv}/bin/python" "\$@"
EOF
  chmod 0555 "$out/bin/gfx803-schaka101-python"
  printf '%s\n' 'CANDIDATE ONLY — NOT ADMITTED FOR CACHIX RELEASE OR UNRESTRICTED TRAINING' > "$out/share/gfx803/ADMISSION"
''
