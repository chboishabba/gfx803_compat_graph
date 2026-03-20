{
  description = "gfx803 ROCm compatibility environment";

  nixConfig = {
    extra-substituters = [ "https://gfx803-rocm.cachix.org" ];
    extra-trusted-public-keys = [ "gfx803-rocm.cachix.org-1:UTaIREqPZa9yjY7hiMBYG556OrGR6WEhWPjqX4Us3us=" ];
  };

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
  let
    system = "x86_64-linux";

    pkgs = import nixpkgs {
      inherit system;
      config = {
        allowUnfree = true;
        rocmSupport = true;
      };
    };

    # Polaris compatibility environment
    gfx803Env = ''
      export HSA_OVERRIDE_GFX_VERSION=8.0.3
      export ROC_ENABLE_PRE_VEGA=1

      export PYTORCH_ROCM_ARCH=gfx803
      export ROCM_ARCH=gfx803

      export TORCH_BLAS_PREFER_HIPBLASLT=0

      export MIOPEN_DEBUG_CONV_WINOGRAD=0
      export MIOPEN_DEBUG_CONV_FFT=0

      # Fix for ENOMEM on some Polaris cards
      export HSA_ENABLE_SDMA=0
    '';

  in {

    devShells.${system} = {

      # ----------------------------------------
      # ROCm base environment
      # replaces Docker rocm base image
      # ----------------------------------------
      base = pkgs.mkShell {

        buildInputs = with pkgs; [
          rocmPackages.clr
          rocmPackages.rocblas
          rocmPackages.hipblas
          rocmPackages.miopen
          rocmPackages.rocm-smi

          rocmPackages.rocminfo

          clang
          cmake
          git
          python312
          
          libdrm
          numactl
          pciutils
        ];

        shellHook = ''
          ${gfx803Env}
          export LD_LIBRARY_PATH="${pkgs.libdrm}/lib:${pkgs.numactl}/lib:${pkgs.pciutils}/lib:$LD_LIBRARY_PATH"

          echo "gfx803 ROCm base shell"
          echo "Try: rocminfo"
        '';
      };

      # ----------------------------------------
      # PyTorch development shell
      # replaces Docker pytorch image
      # ----------------------------------------
      pytorch = pkgs.mkShell {

        buildInputs = with pkgs; [
          python312

          python312Packages.pip
          python312Packages.numpy

          python312Packages.torch
          python312Packages.torchvision
          python312Packages.torchaudio

          rocmPackages.clr
          rocmPackages.miopen
          rocmPackages.rocblas

          rocmPackages.rocminfo
          rocmPackages.rocm-smi
          
          libdrm
          numactl
          pciutils
        ];

        shellHook = ''
          ${gfx803Env}
          export LD_LIBRARY_PATH="${pkgs.libdrm}/lib:${pkgs.numactl}/lib:${pkgs.pciutils}/lib:$LD_LIBRARY_PATH"

          echo "gfx803 PyTorch shell"
          python - <<EOF
import torch
print("PyTorch:", torch.__version__)
print("HIP available:", torch.cuda.is_available())
EOF
        '';
      };

      # ----------------------------------------
      # Drift CI testing shell
      # feeder for compatibility atlas
      # ----------------------------------------
      drift = pkgs.mkShell {

        buildInputs = with pkgs; [
          python312
          python312Packages.numpy
          python312Packages.torch

          rocmPackages.clr
          rocmPackages.miopen
          rocmPackages.rocblas
          rocmPackages.rocminfo
          rocmPackages.rocm-smi
          rocmPackages.rocprofiler
          rocmPackages.roctracer

          jq
          libdrm
          numactl
          pciutils
        ];

        shellHook = ''
          ${gfx803Env}
          export LD_LIBRARY_PATH="${pkgs.libdrm}/lib:${pkgs.numactl}/lib:${pkgs.pciutils}/lib:$LD_LIBRARY_PATH"

          export DRIFT_RESULTS_DIR=$PWD/out
          mkdir -p $DRIFT_RESULTS_DIR

          echo "gfx803 drift testing shell"
          echo "Run: run-drift-matrix"
          
          # Add scripts to PATH so they are easy to run
          export PATH="$PWD/scripts:$PATH"
        '';
      };
    };

    apps.${system} = {
      drift-matrix = {
        type = "app";
        program = "${pkgs.writeShellScript "drift-matrix" ''
          exec ${pkgs.bash}/bin/bash scripts/run-drift-matrix
        ''}";
      };

      update-graph = {
        type = "app";
        program = "${pkgs.writeShellScript "update-graph" ''
          exec ${pkgs.python312}/bin/python scripts/update_graph.py
        ''}";
      };
    };

  };
}
