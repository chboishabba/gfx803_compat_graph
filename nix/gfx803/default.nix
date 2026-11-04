# Nix-managed tooling and policy for the Schaka gfx803 build/distribution lane.
# No Nixpkgs ROCm libraries are injected: ROCm 10.1's SDK must be coherent.
{ pkgs }:
let
  python = pkgs.python312;
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
      exec ${pkgs.bash}/bin/bash ${../../scripts/import-schaka-oci-to-nix.sh} "$@"
    '';
  };

  policy = pkgs.writeShellApplication {
    name = "gfx803-release-policy";
    runtimeInputs = [ python ];
    text = ''
      exec ${python}/bin/python ${../../scripts/gfx803_release.py} "$@"
    '';
  };

  recorder = pkgs.writeShellApplication {
    name = "gfx803-capture-evidence";
    runtimeInputs = [ python ];
    text = ''
      exec ${python}/bin/python ${../../scripts/gfx803_capture.py} "$@"
    '';
  };

  # Optional downstream ComfyUI image canary. Keep Pillow out of ROCm SDK.
  pythonImages = pkgs.python312.withPackages (ps: [ ps.pillow ]);
  comfyuiImages = pkgs.writeShellApplication {
    name = "gfx803-comfyui-images";
    runtimeInputs = [ pythonImages ];
    text = ''
      exec ${pythonImages}/bin/python ${../../scripts/gfx803_comfyui_images.py} "$@"
    '';
  };

  auditor = pkgs.writeShellApplication {
    name = "gfx803-audit-closure";
    runtimeInputs = [ python pkgs.binutils ];
    text = ''
      exec ${python}/bin/python ${../../scripts/audit_gfx803_closure.py} "$@"
    '';
  };

  # Bootstrap tools only: do not accidentally mix contemporary Nixpkgs ROCm
  # device-libs/LLVM with Schaka's release-coherent ROCm compiler SDK.
  bootstrapTools = [
    importer policy recorder auditor python pkgs.git pkgs.jq pkgs.patchelf pkgs.file
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
    in {
      gfx803-sdk = pkgs.mkShellNoCC {
        packages = bootstrapTools;
        shellHook = ''
          export ROCM_PATH="${sdk}"
          export HIP_PATH="$ROCM_PATH"
          export PATH="$ROCM_PATH/bin:$PATH"
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
