# Nix-managed tooling and policy for the Schaka gfx803 build/distribution lane.
# No Nixpkgs ROCm libraries are injected: ROCm 10.1's SDK must be coherent.
{ pkgs }:
let
  python = pkgs.python312;
  sourceScripts = ../../scripts;
  sourceLockFile = ./upstream.json;
  upstream = builtins.fromJSON (builtins.readFile ./upstream.json);
  upstreamLock = pkgs.writeText "gfx803-schaka-upstream-lock.json"
    (builtins.readFile ./upstream.json);

  # These packages do not appear until an on-card admitted release manifest
  # is committed. Never manufacture store paths, and never substitute a tag.
  acceptedManifest = if builtins.pathExists ./accepted-release.json
    then builtins.fromJSON (builtins.readFile ./accepted-release.json)
    else null;
  acceptedBinaries = if acceptedManifest == null then {} else
    if acceptedManifest.state != "accepted" then
      throw "gfx803 accepted-release.json must have accepted state"
    else pkgs.lib.mapAttrs' (name: path:
      pkgs.lib.nameValuePair ("gfx803-" + name + "-binary")
        (builtins.fetchClosure {
          fromStore = "https://gfx803-rocm.cachix.org";
          fromPath = path;
          inputAddressed = true;
        })
    ) acceptedManifest.store_paths;

  importer = pkgs.writeShellApplication {
    name = "gfx803-import-schaka";
    runtimeInputs = with pkgs; [
      bash coreutils findutils gnugrep jq skopeo umoci nix python
    ];
    text = ''
      export GFX803_SCRIPTS_DIR="${sourceScripts}"
      export GFX803_SOURCE_LOCK="${sourceLockFile}"
      export PYTHONPATH="${sourceScripts}"
      exec ${pkgs.bash}/bin/bash ${sourceScripts}/import-schaka-oci-to-nix.sh "$@"
    '';
  };

  policy = pkgs.writeShellApplication {
    name = "gfx803-release-policy";
    runtimeInputs = [ python ];
    text = ''
      export GFX803_SOURCE_LOCK="${sourceLockFile}"
      export PYTHONPATH="${sourceScripts}"
      exec ${python}/bin/python ${sourceScripts}/gfx803_release.py "$@"
    '';
  };

  recorder = pkgs.writeShellApplication {
    name = "gfx803-capture-evidence";
    runtimeInputs = [ python ];
    text = ''
      export PYTHONPATH="${sourceScripts}"
      exec ${python}/bin/python ${sourceScripts}/gfx803_capture.py "$@"
    '';
  };

  # Optional downstream ComfyUI image canary. Keep Pillow out of ROCm SDK.
  pythonImages = pkgs.python312.withPackages (ps: [ ps.pillow ]);
  comfyuiImages = pkgs.writeShellApplication {
    name = "gfx803-comfyui-images";
    runtimeInputs = [ pythonImages ];
    text = ''
      exec ${pythonImages}/bin/python ${sourceScripts}/gfx803_comfyui_images.py "$@"
    '';
  };

  leechQkvVerifier = pkgs.writeShellApplication {
    name = "gfx803-verify-leech-qkv";
    runtimeInputs = [ python ];
    text = ''
      export PYTHONPATH="${sourceScripts}"
      exec ${python}/bin/python ${sourceScripts}/gfx803_leech_qkv_admission.py "$@"
    '';
  };

  auditor = pkgs.writeShellApplication {
    name = "gfx803-audit-closure";
    runtimeInputs = [ python pkgs.binutils ];
    text = ''
      exec ${python}/bin/python ${sourceScripts}/audit_gfx803_closure.py "$@"
    '';
  };

  # Bootstrap tools only: do not accidentally mix contemporary Nixpkgs ROCm
  # device-libs/LLVM with Schaka's release-coherent ROCm compiler SDK.
  bootstrapTools = [
    importer policy recorder auditor leechQkvVerifier python pkgs.git pkgs.jq pkgs.patchelf pkgs.file
    pkgs.binutils pkgs.skopeo pkgs.umoci pkgs.cachix pkgs.zstd
  ];

  bootstrapShell = pkgs.mkShellNoCC {
    packages = bootstrapTools;
    shellHook = ''
      export GFX803_UPSTREAM_REPO="${upstream.source_repository}"
      export GFX803_UPSTREAM_REV="${upstream.source_revision}"
      export GFX803_ROCM_VERSION="${upstream.rocm_version}"
      echo "gfx803 Nix OCI bootstrap; source pin: $GFX803_UPSTREAM_REV"
      echo "This is NOT the full native-from-source ROCm build SDK."
    '';
  };

  # The accepted release also supplies an SDK shell. This is still an imported
  # upstream SDK: the separate native-from-source derivations remain outstanding.
  releaseShells = if acceptedManifest == null then {} else
    let
      mm = pkgs.lib.concatStringsSep "." (
        pkgs.lib.take 2 (pkgs.lib.splitString "." acceptedManifest.rocm_version));
      sdk = "${acceptedBinaries.gfx803-rocm-binary}/core-${mm}";
      shim = "${acceptedBinaries.gfx803-rocm-binary}/lib/libgfx803_sgemm_shim.so";
    in {
      gfx803-sdk = pkgs.mkShellNoCC {
        packages = bootstrapTools;
        shellHook = ''
          export ROCM_PATH="${sdk}"
          export HIP_PATH="$ROCM_PATH"
          export PATH="$ROCM_PATH/bin:$PATH"
          # The original Schaka image REQUIRES this FP32 SGEMM shim. A raw
          # copied rocBLAS tree with WGM1 alone is not runtime equivalent.
          if [[ ! -f "${shim}" ]]; then
            echo "gfx803: accepted ROCm closure missing required FP32 SGEMM shim" >&2
            return 2
          fi
          export HSA_OVERRIDE_GFX_VERSION=8.0.3
          export ROC_ENABLE_PRE_VEGA=1
          export TORCH_BLAS_PREFER_HIPBLASLT=0
          export GFX803_SGEMM_SHIM_DISABLE=0
          export LD_PRELOAD="${shim}"
          echo "Accepted Schaka gfx803 SDK: $ROCM_PATH"
          echo "Runtime and compiler libraries must come from this same ROCm line."
        '';
      };
    };

  # CI needs no GPU and no network to validate source/promotion contracts.
  policyCheck = pkgs.runCommand "gfx803-release-policy-tests" {
    nativeBuildInputs = [ python pkgs.bash pkgs.binutils pkgs.coreutils ];
  } ''
    export HOME="$TMPDIR"
    cd ${../..}
    ${python}/bin/python -m unittest discover -s tests -p 'test_gfx803_*.py'
    touch "$out"
  '';
in
{
  packages = ({
    gfx803-schaka-upstream-lock = upstreamLock;
    gfx803-schaka-import = importer;
    gfx803-release-policy = policy;
    gfx803-verify-leech-qkv = leechQkvVerifier;
    gfx803-capture-evidence = recorder;
    gfx803-comfyui-images = comfyuiImages;
    gfx803-audit-closure = auditor;
  } // acceptedBinaries);
  devShells = ({
    gfx803-oci-build = bootstrapShell;
  } // releaseShells);
  checks = {
    gfx803-release-policy = policyCheck;
  };
  apps = {
    gfx803-schaka-import = {
      type = "app";
      program = "${importer}/bin/gfx803-import-schaka";
    };
    gfx803-release-policy = {
      type = "app";
      program = "${policy}/bin/gfx803-release-policy";
    };
    gfx803-verify-leech-qkv = {
      type = "app";
      program = "${leechQkvVerifier}/bin/gfx803-verify-leech-qkv";
    };
    gfx803-capture-evidence = {
      type = "app";
      program = "${recorder}/bin/gfx803-capture-evidence";
    };
    gfx803-comfyui-images = {
      type = "app";
      program = "${comfyuiImages}/bin/gfx803-comfyui-images";
    };
    gfx803-audit-closure = {
      type = "app";
      program = "${auditor}/bin/gfx803-audit-closure";
    };
  };
}
