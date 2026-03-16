{
  description = "sd.cpp Vulkan development environment for RX580 ground-truth testing";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
  in {
    packages.${system}.default = pkgs.stdenv.mkDerivation {
      pname = "stable-diffusion-cpp";
      version = "v1.0.0"; # Or track a specific commit
      src = pkgs.fetchFromGitHub {
        owner = "leejet";
        repo = "stable-diffusion.cpp";
        rev = "master"; # Recommend pinning this in production
        sha256 = pkgs.lib.fakeSha256; # Need to update checksum next built or pull via git
        fetchSubmodules = true;
      };

      nativeBuildInputs = with pkgs; [ cmake ninja pkg-config ];
      buildInputs = with pkgs; [ vulkan-headers vulkan-loader vulkan-tools glslang gcc ];

      cmakeFlags = [
        "-DSD_VULKAN=ON"
        "-G Ninja"
      ];

      installPhase = ''
        mkdir -p $out/bin
        cp bin/* $out/bin/
      '';
    };

    devShells.${system}.default = pkgs.mkShell {
      buildInputs = with pkgs; [
        cmake
        ninja
        gcc
        git
        pkg-config
        vulkan-headers
        vulkan-loader
        vulkan-tools
        vulkan-validation-layers
        glslang
      ];

      shellHook = ''
        echo "=========================================================="
        echo "❄️  Nix environment active: sd.cpp (Vulkan)"
        echo "=========================================================="
        echo "To build sd.cpp to start getting Vulkan ground-truth data:"
        echo ""
        echo "  nix build .#default  # <--- Use this to build directly!"
        echo ""
        echo "Or for manual building:"
        echo "  git clone --recursive https://github.com/leejet/stable-diffusion.cpp.git"
        echo "  cd stable-diffusion.cpp"
        echo "  mkdir build && cd build"
        echo "  cmake .. -G Ninja -DSD_VULKAN=ON"
        echo "  cmake --build . --config Release"
        echo "=========================================================="
      '';
    };
  };
}
