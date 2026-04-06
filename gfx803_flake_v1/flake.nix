{
  description = "gfx803 / Polaris ROCm runtime + drift-matrix + compatibility-graph tooling";

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

    lib = pkgs.lib;

    gfx803EnvText = ''
      export HSA_OVERRIDE_GFX_VERSION=8.0.3
      export ROC_ENABLE_PRE_VEGA=1
      export PYTORCH_ROCM_ARCH=gfx803
      export ROCM_ARCH=gfx803
      export TORCH_BLAS_PREFER_HIPBLASLT=0

      # Safer defaults for Polaris stability
      export MIOPEN_DEBUG_CONV_WINOGRAD=0
      export MIOPEN_DEBUG_CONV_FFT=0
      export CUBLAS_WORKSPACE_CONFIG=:4096:8
    '';

    graphPy = pkgs.python312.withPackages (ps: with ps; [
      networkx
    ]);

    commonInputs = with pkgs; [
      bash
      coreutils
      findutils
      gnugrep
      gawk
      jq
      git
      cmake
      ninja
      gnumake
      pkg-config
      ccache
      which
      python312
      python312Packages.pip
      python312Packages.virtualenv
      python312Packages.setuptools
      python312Packages.wheel
      graphPy
      rocmPackages.clr
      rocmPackages.rocblas
      rocmPackages.miopen
      rocmPackages.rocminfo
      rocmPackages.rocm-smi
    ];

    whisperxInputs = builtins.filter
      (pkg: !(builtins.elem pkg [
        pkgs.rocmPackages.clr
        pkgs.rocmPackages.rocblas
        pkgs.rocmPackages.miopen
      ]))
      commonInputs;

    repoRootDetect = ''
      if REPO_ROOT_GIT="$(git rev-parse --show-toplevel 2>/dev/null)" && [[ -n "$REPO_ROOT_GIT" ]]; then
        REPO_ROOT_DEFAULT="$REPO_ROOT_GIT"
      elif [[ -d "$PWD/scripts" ]]; then
        REPO_ROOT_DEFAULT="$PWD"
      elif [[ -d "$PWD/../scripts" ]]; then
        REPO_ROOT_DEFAULT="$(cd "$PWD/.." && pwd)"
      else
        REPO_ROOT_DEFAULT="$PWD"
      fi
    '';

    driftRunner = pkgs.writeShellApplication {
      name = "run-drift-matrix";
      runtimeInputs = commonInputs;
      text = ''
        set -euo pipefail

        ${repoRootDetect}
        REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
        export OUT_DIR=''${OUT_DIR:-$REPO_ROOT/out/drift}

        PYTHON_CMD=()
        if [[ -n "''${TORCH_PYTHON:-}" ]]; then
          PYTHON_CMD=("$TORCH_PYTHON")
        elif [[ -x "$REPO_ROOT/docker-venv/venv/bin/python" && -d "$REPO_ROOT/docker-venv/conda-python" && -f "$REPO_ROOT/scripts/host-docker-python.sh" ]]; then
          PYTHON_CMD=(bash "$REPO_ROOT/scripts/host-docker-python.sh")
        elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
          PYTHON_CMD=("$REPO_ROOT/.venv/bin/python")
        elif [[ -x "$REPO_ROOT/venv/bin/python" ]]; then
          PYTHON_CMD=("$REPO_ROOT/venv/bin/python")
        else
          PYTHON_CMD=("$(command -v python3)")
        fi

        export STACK_ID=''${STACK_ID:-rocm64_extracted_host}
        export REFERENCE_CLASS=''${REFERENCE_CLASS:-reference}
        export RUNTIME_FAMILY=''${RUNTIME_FAMILY:-rocm64_patched}
        export RUNTIME_SOURCE=''${RUNTIME_SOURCE:-itir:latest extracted host runtime}
        export WORKLOAD=''${WORKLOAD:-bug_report_mre}

        BENCHMARK_PYTHON_JSON="$(python3 -c 'import json, sys; print(json.dumps(sys.argv[1:]))' "''${PYTHON_CMD[@]}")"
        python3 "$REPO_ROOT/scripts/run_benchmark_matrix.py" \
          --repo-root "$REPO_ROOT" \
          --python-cmd-json "$BENCHMARK_PYTHON_JSON" \
          --out-dir "$OUT_DIR" \
          --stack-id "$STACK_ID" \
          --reference-class "$REFERENCE_CLASS" \
          --runtime-family "$RUNTIME_FAMILY" \
          --runtime-source "$RUNTIME_SOURCE" \
          --workload "$WORKLOAD"
      '';
    };

    graphUpdater = pkgs.writeShellApplication {
      name = "update-compat-graph";
      runtimeInputs = [ graphPy pkgs.python312 ];
      text = ''
        set -euo pipefail
        ${repoRootDetect}
        REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
        JSONL=''${JSONL:-$REPO_ROOT/out/drift/benchmark-results.jsonl}
        GRAPH_JSON=''${GRAPH_JSON:-$REPO_ROOT/out/compat-graph-results.json}
        python3 "$REPO_ROOT/scripts/update_graph.py" "$JSONL" "$GRAPH_JSON"
      '';
    };

    communityBundle = pkgs.writeShellApplication {
      name = "create-community-bundle";
      runtimeInputs = [ pkgs.python312 ];
      text = ''
        set -euo pipefail
        ${repoRootDetect}
        REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
        exec python3 "$REPO_ROOT/scripts/create_community_bundle.py" "$@"
      '';
    };

    releaseManifest = pkgs.writeShellApplication {
      name = "build-release-manifest";
      runtimeInputs = [ pkgs.python312 ];
      text = ''
        set -euo pipefail
        ${repoRootDetect}
        REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
        exec python3 "$REPO_ROOT/scripts/build_release_manifest.py" "$@"
      '';
    };

    verifyHost = pkgs.writeShellApplication {
      name = "verify-gfx803-host";
      runtimeInputs = commonInputs;
      text = ''
        set -euo pipefail
        echo "== host kernel =="
        uname -a
        echo
        echo "== groups =="
        id
        echo
        echo "== /dev/kfd =="
        ls -l /dev/kfd || true
        echo
        echo "== rocminfo =="
        rocminfo || true
        echo
        echo "== rocm-smi =="
        rocm-smi || true
      '';
    };

    frameworkRebuildDriver = pkgs.writeShellApplication {
      name = "run-gfx803-pytorch-framework-rebuild";
      runtimeInputs = commonInputs;
      text = ''
        set -euo pipefail
        ${repoRootDetect}
        REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
        exec "$REPO_ROOT/scripts/run-gfx803-pytorch-framework-rebuild.sh" "$@"
      '';
    };

    mkPytorchStackShell = { message, torchRunner, stackId, runtimeFamily, runtimeSource, extraHook ? "" }:
      pkgs.mkShell {
        buildInputs = commonInputs ++ [ driftRunner graphUpdater verifyHost communityBundle releaseManifest ] ++ (with pkgs; [
          python312Packages.numpy
          python312Packages.sentencepiece
          python312Packages.requests
        ]);
        shellHook = ''
          ${gfx803EnvText}
          ${repoRootDetect}
          export REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
          export TORCH_PYTHON="$REPO_ROOT/${torchRunner}"
          export STACK_ID="${stackId}"
          export REFERENCE_CLASS="reference"
          export RUNTIME_FAMILY="${runtimeFamily}"
          export RUNTIME_SOURCE="${runtimeSource}"
          ${extraHook}
          echo "${message}"
          echo "TORCH_PYTHON=$TORCH_PYTHON"
          echo "Use: run-drift-matrix"
        '';
      };

  in {
    packages.${system} = {
      gfx803-env = pkgs.writeText "gfx803-env.sh" gfx803EnvText;
      run-drift-matrix = driftRunner;
      update-compat-graph = graphUpdater;
      verify-gfx803-host = verifyHost;
      run-gfx803-pytorch-framework-rebuild = frameworkRebuildDriver;
      create-community-bundle = communityBundle;
      build-release-manifest = releaseManifest;
    };

    apps.${system} = {
      drift-matrix = {
        type = "app";
        program = "${driftRunner}/bin/run-drift-matrix";
      };
      update-graph = {
        type = "app";
        program = "${graphUpdater}/bin/update-compat-graph";
      };
      community-bundle = {
        type = "app";
        program = "${communityBundle}/bin/create-community-bundle";
      };
      release-manifest = {
        type = "app";
        program = "${releaseManifest}/bin/build-release-manifest";
      };
      verify-host = {
        type = "app";
        program = "${verifyHost}/bin/verify-gfx803-host";
      };
      framework-rebuild = {
        type = "app";
        program = "${frameworkRebuildDriver}/bin/run-gfx803-pytorch-framework-rebuild";
      };
    };

    devShells.${system} = {
      # Native runtime + 5.7 Mathematical payload
      rocmNative-franken = pkgs.mkShell {
        buildInputs = commonInputs ++ [ driftRunner graphUpdater verifyHost communityBundle releaseManifest ];
        shellHook = ''
          ${gfx803EnvText}
          ${repoRootDetect}
          export REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
          
          # Inject 5.7 logic into ROCm 
          export ROCBLAS_TENSILE_LIBPATH="$REPO_ROOT/artifacts/rocm57/rocblas-library"
          export MIOPEN_SYSTEM_DB_PATH="$REPO_ROOT/artifacts/rocm57/miopen-db"

          echo "🧌 Using Frankenstein Payload (5.7 math in newer runtime):"
          echo "  ROCBLAS_TENSILE_LIBPATH=$ROCBLAS_TENSILE_LIBPATH"
          echo "  MIOPEN_SYSTEM_DB_PATH=$MIOPEN_SYSTEM_DB_PATH"
          if [[ ! -d "$ROCBLAS_TENSILE_LIBPATH" || ! -d "$MIOPEN_SYSTEM_DB_PATH" ]]; then
            echo "WARNING: 5.7 artifacts are missing. Run: bash scripts/extract-rocm57-artifacts.sh"
          fi
          echo "Use: run-drift-matrix"
        '';
      };

      base = pkgs.mkShell {
        buildInputs = commonInputs ++ [ driftRunner graphUpdater verifyHost communityBundle releaseManifest ];
        shellHook = ''
          ${gfx803EnvText}
          ${repoRootDetect}
          export REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
          echo "gfx803 base ROCm shell"
          echo "Use: verify-gfx803-host"
        '';
      };

      pytorch = pkgs.mkShell {
        buildInputs = commonInputs ++ [ driftRunner graphUpdater verifyHost communityBundle releaseManifest ] ++ (with pkgs; [
          python312Packages.numpy
          python312Packages.sentencepiece
          python312Packages.requests
        ]);
        shellHook = ''
          ${gfx803EnvText}
          ${repoRootDetect}
          export REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
          echo "gfx803 PyTorch/drift shell"
          if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
            echo "Using local venv at .venv"
          elif [[ -x "$REPO_ROOT/docker-venv/venv/bin/python" ]]; then
            echo "Using extracted docker-venv via scripts/host-docker-python.sh"
          else
            echo "No .venv detected. Set TORCH_PYTHON, create a local venv, or use docker-venv."
          fi
          echo "Use: run-drift-matrix"
        '';
      };

      "gfx803-pytorch-stack" = mkPytorchStackShell {
        message = "gfx803 PyTorch control stack (frozen Python/framework + known-working selected libs)";
        torchRunner = "scripts/host-docker-python.sh";
        stackId = "gfx803_pytorch_stack_control";
        runtimeFamily = "rocm64_extracted_control";
        runtimeSource = "frozen extracted 6.4 Python/framework with known-working selected libs";
      };

      "gfx803-pytorch-stack-upgrade" = mkPytorchStackShell {
        message = "gfx803 PyTorch upgrade stack (same frozen Python/framework + preserved old HSA/HIP ABI lane)";
        torchRunner = "scripts/host-rocm64-upgrade-oldabi-python.sh";
        stackId = "gfx803_pytorch_stack_upgrade";
        runtimeFamily = "rocm64_upgrade_oldabi";
        runtimeSource = "frozen extracted 6.4 Python/framework with preserved old HSA/HIP ABI and selected newer support libs";
      };

      "gfx803-pytorch-framework-rebuild" = pkgs.mkShell {
        buildInputs = commonInputs ++ [ driftRunner graphUpdater verifyHost communityBundle releaseManifest frameworkRebuildDriver ] ++ (with pkgs; [
          python312Packages.numpy
          python312Packages.requests
        ]);
        shellHook = ''
          ${gfx803EnvText}
          ${repoRootDetect}
          export REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
          export FRAMEWORK_REBUILD_RUNTIME_LIBDIR="''${FRAMEWORK_REBUILD_RUNTIME_LIBDIR:-$REPO_ROOT/artifacts/rocm64-upgrade-oldabi/lib-compat}"
          export FRAMEWORK_REBUILD_ROCM_ROOT="''${FRAMEWORK_REBUILD_ROCM_ROOT:-$REPO_ROOT/artifacts/rocm64-oldabi-sdk/opt-rocm}"
          echo "gfx803 PyTorch framework rebuild shell"
          echo "Runtime compat: $FRAMEWORK_REBUILD_RUNTIME_LIBDIR"
          echo "ROCm root: $FRAMEWORK_REBUILD_ROCM_ROOT"
          echo "Use: run-gfx803-pytorch-framework-rebuild"
        '';
      };

      comfyui = pkgs.mkShell {
        buildInputs = commonInputs ++ [ driftRunner graphUpdater verifyHost communityBundle releaseManifest ];
        shellHook = ''
          ${gfx803EnvText}
          ${repoRootDetect}
          export REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
          export COMMANDLINE_ARGS="--lowvram"
          echo "gfx803 ComfyUI shell"
        '';
      };

      whisperx = pkgs.mkShell {
        buildInputs = whisperxInputs ++ [ driftRunner graphUpdater verifyHost communityBundle releaseManifest ];
        shellHook = ''
          ${gfx803EnvText}
          ${repoRootDetect}
          export REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
          export JOBLIB_MULTIPROCESSING=0
          export HIP_LAUNCH_BLOCKING=''${HIP_LAUNCH_BLOCKING:-1}
          export TORCH_HOME="''${TORCH_HOME:-$REPO_ROOT/.cache/torch}"
          export TORCH_PYTHON="$REPO_ROOT/scripts/host-docker-python.sh"
          mkdir -p "$TORCH_HOME/hub"
          echo "gfx803 WhisperX shell"
          echo "HIP_LAUNCH_BLOCKING=$HIP_LAUNCH_BLOCKING"
          echo "TORCH_HOME=$TORCH_HOME"
          echo "Using extracted WhisperX runtime without Nix ROCm device-lib injection"
          echo "Run normal transcription with:"
          echo '  bash "$REPO_ROOT/scripts/host-docker-python.sh" -m whisperx /path/to/audio --model small --compute_type int8 --language en'
          echo 'Bootstrap Silero cache once with:'
          echo '  bash "$REPO_ROOT/scripts/bootstrap-silero-vad-cache.sh"'
        '';
      };

      ollama-bundle = pkgs.mkShell {
        buildInputs = with pkgs; [ coreutils gnugrep curl ];
        shellHook = ''
          ${gfx803EnvText}
          ${repoRootDetect}
          export REPO_ROOT=''${REPO_ROOT:-$REPO_ROOT_DEFAULT}
          export OLLAMA_BUNDLE_DIR="$REPO_ROOT/artifacts/ollama_reference"
          export LD_LIBRARY_PATH="$OLLAMA_BUNDLE_DIR/rocm-6.4.3/lib:''${LD_LIBRARY_PATH:-}"
          echo "gfx803 Ollama bundle shell"
          echo "Bundle: $OLLAMA_BUNDLE_DIR"
          echo "Run: OLLAMA_HOST=http://127.0.0.1:11434 $REPO_ROOT/scripts/host-ollama-bundle.sh serve"
        '';
      };
    };
  };
}
