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

    whisperxWebUIRepo = "/home/c/Documents/code/ITIR-suite/WhisperX-WebUI";

    whisperxWebUICommonInputs = with pkgs; [
      bash
      coreutils
      curl
      ffmpeg
      findutils
      git
      gnugrep
      gawk
      jq
      libsndfile
      pkg-config
      portaudio
      python312
      rubberband
      which
      rocmPackages.clr
      rocmPackages.rocblas
      rocmPackages.hipblas
      rocmPackages.miopen
      rocmPackages.rocminfo
      rocmPackages.rocm-smi
    ];

    startWhisperxWebuiGfx803 = pkgs.writeShellApplication {
      name = "start-whisperx-webui-gfx803";
      runtimeInputs = whisperxWebUICommonInputs;
      text = ''
        set -euo pipefail

        export GFX803_COMPAT_ROOT="''${GFX803_COMPAT_ROOT:-$PWD}"
        export WEBUI_ROOT="''${WEBUI_ROOT:-${whisperxWebUIRepo}}"
        export EXTRACTED_OUTDIR="''${EXTRACTED_OUTDIR:-$GFX803_COMPAT_ROOT}"
        export JOBLIB_MULTIPROCESSING="''${JOBLIB_MULTIPROCESSING:-0}"
        export HIP_LAUNCH_BLOCKING="''${HIP_LAUNCH_BLOCKING:-1}"
        export XDG_CACHE_HOME="''${XDG_CACHE_HOME:-$WEBUI_ROOT/.cache}"
        export TORCH_HOME="''${TORCH_HOME:-$WEBUI_ROOT/.cache/torch}"
        export HF_HOME="''${HF_HOME:-$WEBUI_ROOT/.cache/huggingface}"
        export HUGGINGFACE_HUB_CACHE="''${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}"
        mkdir -p "$XDG_CACHE_HOME" "$TORCH_HOME" "$HF_HOME" "$WEBUI_ROOT/models" "$WEBUI_ROOT/outputs"

        if [[ ! -x "$GFX803_COMPAT_ROOT/scripts/host-docker-python.sh" ]]; then
          echo "ERROR: expected compatibility wrapper at $GFX803_COMPAT_ROOT/scripts/host-docker-python.sh" >&2
          exit 1
        fi

        if [[ ! -d "$EXTRACTED_OUTDIR/lib-compat" || ! -d "$EXTRACTED_OUTDIR/docker-venv" ]]; then
          echo "ERROR: missing extracted runtime under $EXTRACTED_OUTDIR" >&2
          echo "Expected lib-compat/ and docker-venv/ from the gfx803 compatibility path." >&2
          exit 1
        fi

        cd "$WEBUI_ROOT"
        exec bash "$GFX803_COMPAT_ROOT/scripts/host-docker-python.sh" "$WEBUI_ROOT/app.py" "$@"
      '';
    };

    bootstrapWhisperxWebuiSilero = pkgs.writeShellApplication {
      name = "bootstrap-whisperx-webui-silero-cache";
      runtimeInputs = with pkgs; [ bash coreutils git gnugrep ];
      text = ''
        set -euo pipefail

        export GFX803_COMPAT_ROOT="''${GFX803_COMPAT_ROOT:-$PWD}"
        export WEBUI_ROOT="''${WEBUI_ROOT:-${whisperxWebUIRepo}}"
        export TORCH_HOME="''${TORCH_HOME:-$WEBUI_ROOT/.cache/torch}"
        mkdir -p "$TORCH_HOME"

        exec bash "$GFX803_COMPAT_ROOT/scripts/bootstrap-silero-vad-cache.sh"
      '';
    };

    verifyWhisperxWebuiRuntime = pkgs.writeShellApplication {
      name = "verify-whisperx-webui-gfx803-runtime";
      runtimeInputs = whisperxWebUICommonInputs;
      text = ''
        set -euo pipefail

        export GFX803_COMPAT_ROOT="''${GFX803_COMPAT_ROOT:-$PWD}"
        export EXTRACTED_OUTDIR="''${EXTRACTED_OUTDIR:-$GFX803_COMPAT_ROOT}"

        echo "== compatibility root =="
        echo "$GFX803_COMPAT_ROOT"
        echo
        echo "== WhisperX-WebUI root =="
        echo "''${WEBUI_ROOT:-${whisperxWebUIRepo}}"
        echo
        echo "== extracted runtime =="
        ls -ld "$EXTRACTED_OUTDIR/lib-compat" "$EXTRACTED_OUTDIR/docker-venv"
        echo
        echo "== GPU visibility =="
        rocminfo | sed -n '1,40p' || true
        echo
        echo "== quick torch probe =="
        bash "$GFX803_COMPAT_ROOT/scripts/host-docker-python.sh" -c 'import torch; print("torch", torch.__version__); print("cuda", torch.cuda.is_available(), "count", torch.cuda.device_count())'
      '';
    };

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
          export LD_LIBRARY_PATH="${pkgs.libdrm}/lib:${pkgs.numactl}/lib:${pkgs.pciutils}/lib:${pkgs.rocmPackages.clr}/lib:${pkgs.rocmPackages.hipblas}/lib:${pkgs.rocmPackages.rocblas}/lib:$LD_LIBRARY_PATH"

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

          python312Packages.sentencepiece
          python312Packages.requests

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
          export LD_LIBRARY_PATH="${pkgs.libdrm}/lib:${pkgs.numactl}/lib:${pkgs.pciutils}/lib:${pkgs.rocmPackages.clr}/lib:${pkgs.rocmPackages.hipblas}/lib:${pkgs.rocmPackages.rocblas}/lib:$LD_LIBRARY_PATH"

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
          export LD_LIBRARY_PATH="${pkgs.libdrm}/lib:${pkgs.numactl}/lib:${pkgs.pciutils}/lib:${pkgs.rocmPackages.clr}/lib:${pkgs.rocmPackages.hipblas}/lib:${pkgs.rocmPackages.rocblas}/lib:$LD_LIBRARY_PATH"

          export DRIFT_RESULTS_DIR=$PWD/out
          mkdir -p $DRIFT_RESULTS_DIR

          echo "gfx803 drift testing shell"
          echo "Run: run-drift-matrix"
          
          # Add scripts to PATH so they are easy to run
          export PATH="$PWD/scripts:$PATH"
        '';
      };

      whisperx-webui-gfx803 = pkgs.mkShell {
        buildInputs = whisperxWebUICommonInputs ++ [
          startWhisperxWebuiGfx803
          bootstrapWhisperxWebuiSilero
          verifyWhisperxWebuiRuntime
        ];

        shellHook = ''
          ${gfx803Env}
          export GFX803_COMPAT_ROOT="$PWD"
          export WEBUI_ROOT="''${WEBUI_ROOT:-${whisperxWebUIRepo}}"
          export EXTRACTED_OUTDIR="''${EXTRACTED_OUTDIR:-$GFX803_COMPAT_ROOT}"
          export JOBLIB_MULTIPROCESSING="''${JOBLIB_MULTIPROCESSING:-0}"
          export HIP_LAUNCH_BLOCKING="''${HIP_LAUNCH_BLOCKING:-1}"
          export XDG_CACHE_HOME="''${XDG_CACHE_HOME:-$WEBUI_ROOT/.cache}"
          export TORCH_HOME="''${TORCH_HOME:-$WEBUI_ROOT/.cache/torch}"
          export HF_HOME="''${HF_HOME:-$WEBUI_ROOT/.cache/huggingface}"
          export HUGGINGFACE_HUB_CACHE="''${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}"
          mkdir -p "$XDG_CACHE_HOME" "$TORCH_HOME" "$HF_HOME" "$WEBUI_ROOT/models" "$WEBUI_ROOT/outputs"

          echo "gfx803 WhisperX-WebUI shell"
          echo "Compatibility root: $GFX803_COMPAT_ROOT"
          echo "WebUI root:         $WEBUI_ROOT"
          echo "Launch with:        start-whisperx-webui-gfx803 --server_name 0.0.0.0 --server_port 7860"
          echo "Warm VAD cache:     bootstrap-whisperx-webui-silero-cache"
          echo "Verify runtime:     verify-whisperx-webui-gfx803-runtime"
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

      whisperx-webui-gfx803 = {
        type = "app";
        program = "${startWhisperxWebuiGfx803}/bin/start-whisperx-webui-gfx803";
      };

      verify-whisperx-webui-runtime = {
        type = "app";
        program = "${verifyWhisperxWebuiRuntime}/bin/verify-whisperx-webui-gfx803-runtime";
      };
    };

  };
}
