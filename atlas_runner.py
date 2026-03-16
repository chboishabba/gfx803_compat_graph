#!/usr/bin/env python3
import argparse
import subprocess
import os
import sys
import json
import platform
import shutil
from pathlib import Path

# ANSI colors for nice terminal output
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    print(f"{BLUE}{BOLD}")
    print("  GFX803 COMPATIBILITY ATLAS RUNNER")
    print("  =================================")
    print(f"  Single entrypoint for community testers{RESET}\n")

def run_command(cmd, desc):
    print(f"{YELLOW}>>> {desc}...{RESET}")
    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"{GREEN}Done.{RESET}\n")
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error executing command: {e}{RESET}\n")

def detect_system():
    info = {
        "gpu": "RX580",
        "kernel": platform.release(),
        "nix": shutil.which("nix") is not None or os.path.exists("/nix"),
        "segfault": False
    }
    
    # Try to detect GPU
    try:
        # Check for AMD GPUs in sysfs
        if os.path.exists('/sys/class/drm'):
            for card in os.listdir('/sys/class/drm'):
                if card.startswith('card') and not '-' in card:
                    vendor_path = f'/sys/class/drm/{card}/device/vendor'
                    if os.path.exists(vendor_path):
                        with open(vendor_path, 'r') as f:
                            if '0x1002' in f.read().lower():
                                device_path = f'/sys/class/drm/{card}/device/device'
                                if os.path.exists(device_path):
                                    with open(device_path, 'r') as df:
                                        dev_id = df.read().strip().lower()
                                        # Polaris 10/20: 67df, 67ef, 67ff, 6fdf (RX 470/480/570/580/590)
                                        if any(id in dev_id for id in ['67df', '67ef', '67ff', '6fdf']):
                                            info["gpu"] = "RX580"
                                        elif '7300' in dev_id:
                                            info["gpu"] = "R9 Fury/Nano"
                                break
    except Exception:
        pass

    # Try to detect segfaults in dmesg (last few lines)
    try:
        # Check dmesg for kfd/segfault - minimal impact, with timeout
        dmesg = subprocess.check_output(['dmesg', '-T'], stderr=subprocess.DEVNULL, timeout=2).decode().lower().splitlines()
        for line in dmesg[-50:]:
            if "kfd" in line or "segfault" in line:
                info["segfault"] = True
                break
    except Exception:
        try:
            journal = subprocess.check_output(['journalctl', '-n', '20', '--priority', '3'], stderr=subprocess.DEVNULL, timeout=2).decode().lower()
            if "kfd" in journal or "segfault" in journal:
                info["segfault"] = True
        except Exception:
            pass

    return info

def get_matching_experiments(sys_info, workload, use_vulkan=False):
    plan_path = Path("out/ranked_experiment_plan.json")
    if not plan_path.exists():
        return []
        
    try:
        plan = json.loads(plan_path.read_text())
    except Exception:
        return []

    scored_plan = []
    for exp in plan:
        match_score = 0
        targets = [t.lower() for t in exp.get("targets", [])]
        
        # 1. Workload match
        if workload:
            for t in targets:
                if workload in t or (t.startswith("workload:") and workload in t):
                    match_score += 15
        
        # 2. Tech stack match
        if use_vulkan and any("vulkan" in t for t in targets):
            match_score += 20
        
        if sys_info.get("nix") and any("nix" in t or "stack:" in t for t in targets):
            match_score += 5
            
        # 3. Issue match (segfaults)
        if sys_info.get("segfault") and any(t in ["driver:amdgpu_kfd", "component:host_kernel", "component:kfd"] for t in targets):
            match_score += 10

        # Base score from the global plan
        total_score = exp.get("score", 0) + match_score
        
        scored_plan.append({
            "exp": exp,
            "total_score": total_score
        })

    scored_plan.sort(key=lambda x: x["total_score"], reverse=True)
    return [s["exp"] for s in scored_plan]

def main():
    parser = argparse.ArgumentParser(description="GFX803 Compatibility Atlas Runner")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: update
    subparsers.add_parser("update", help="Update knowledge graph (ingest + mine + export)")
    
    # Command: viz
    subparsers.add_parser("viz", help="Open the interactive graph visualizer")

    # Command: plan
    subparsers.add_parser("plan", help="Show the ranked experiment plan")

    # Command: capture
    cap_parser = subparsers.add_parser("capture", help="Run the Vulkan Ground Truth Capture tool")
    cap_parser.add_argument("--name", type=str, default="layer_output", help="Name of the tensor layer")

    # Command: verify
    verify_parser = subparsers.add_parser("verify", help="Run basic PyTorch compatibility probe")
    verify_parser.add_argument("--env", type=str, choices=["docker", "nix", "local"], default="local", help="Execution environment")
    verify_parser.add_argument("--env-path", type=str, help="Docker image name (e.g., 'rocm/pytorch:rocm5.7_ubuntu22.04_py3.10_pytorch_2.0.1') or Nix flake path (e.g. '../rr_gfx803_rocm')")

    # Command: artifacts
    subparsers.add_parser("artifacts", help="List generated artifacts and images")

    # Command: benchmark (if sd.cpp is present)
    subparsers.add_parser("benchmark", help="Run stable-diffusion.cpp benchmark (Vulkan)")

    # Command: wizard
    wiz_parser = subparsers.add_parser("wizard", help="Clarification wizard to recommend debug path")
    wiz_parser.add_argument("--gpu", type=str, help="GPU model (e.g., RX580)")
    wiz_parser.add_argument("--kernel", type=str, help="Linux kernel version")
    wiz_parser.add_argument("--segfault", choices=['y', 'n'], help="Are you seeing SegFaults?")
    wiz_parser.add_argument("--nix", choices=['y', 'n'], help="Do you have Nix installed?")
    wiz_parser.add_argument("--workload", type=str, help="Target workload (ComfyUI, Ollama, etc.)")
    wiz_parser.add_argument("--generate-flake", action="store_true", help="Automatically generate flake.nix if applicable")

    args = parser.parse_args()

    if not args.command:
        print_banner()
        parser.print_help()
        return

    if args.command == "update":
        run_command("python run_demo.py", "Regenerating compatibility atlas and artifacts")
    
    elif args.command == "wizard":
        print(f"{BLUE}{BOLD}GFX803 COMPATIBILITY WIZARD{RESET}")
        print(f"{YELLOW}Detecting system specs...{RESET}\n")
        sys_info = detect_system()
        
        # Helper for CLI or Prompt
        def get_input(arg_val, prompt, default=None):
            if arg_val is not None:
                return arg_val
            val = input(prompt) or default
            return val

        gpu = get_input(args.gpu, f"1. What GPU are you using? (default: {sys_info['gpu']}): ", sys_info['gpu'])
        kernel = get_input(args.kernel, f"2. What is your Linux kernel version? (default: {sys_info['kernel']}): ", sys_info['kernel'])
        
        if args.segfault:
            segfault = args.segfault == 'y'
        else:
            default_seg = 'y' if sys_info['segfault'] else 'n'
            segfault = (input(f"3. Are you seeing SegFaults / KFD resets? (y/n, default: {default_seg}): ").lower() or default_seg) == 'y'
            
        if args.nix:
            nix = args.nix == 'y'
        else:
            default_nix = 'y' if sys_info['nix'] else 'n'
            nix = (input(f"4. Do you have Nix installed? (y/n, default: {default_nix}): ").lower() or default_nix) == 'y'
            
        workload = get_input(args.workload, "5. What are you trying to run? (e.g., ComfyUI, Ollama, WhisperX, PyTorch): ", "PyTorch").lower()

        print(f"\n{BOLD}RECOMMENDATION:{RESET}")
        print("-" * 30)

        use_vulkan = False
        isolated_nix = False

        if kernel and ("6.13" in kernel or "6.14" in kernel):
            print(f"{RED}! WARNING: Kernel {kernel} is known to cause KFD SegFaults on GFX803.{RESET}")
            if nix:
                print(f"{GREEN}* ACTION: Use a Nix flake to build in an isolated env.{RESET}")
                isolated_nix = True
            else:
                print(f"{YELLOW}* ACTION: Downgrade to Kernel <=6.12.21, or upgrade to >=6.15.8.{RESET}")
                print(f"{YELLOW}* ALTERNATE: Switch to the Vulkan backend (ggml-vulkan) which does not use KFD.{RESET}")
                use_vulkan = True
        
        if segfault:
            print(f"{YELLOW}* ACTION: If using Ollama, ensure model size < VRAM. 7B models req 8GB.{RESET}")
            
        print(f"{GREEN}* ACTION: Always set MIOPEN_LOG_LEVEL=3 for PyTorch workloads.{RESET}")
        
        if "comfyui" in workload or segfault:
            print(f"{GREEN}* ACTION: Try adding --lowvram to your execution flags.{RESET}")

        if nix and isolated_nix:
            if args.generate_flake:
                gen = 'y'
            else:
                gen = input(f"\n{BOLD}Would you like me to generate a tailored flake.nix for {workload or 'PyTorch'} now? (y/n): {RESET}").lower()
            
            if gen == 'y':
                from textwrap import dedent
                flake_content = dedent(f'''\
                {{
                  description = "GFX803 Environment for {workload}";
                  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
                  outputs = {{ self, nixpkgs }}: let
                    system = "x86_64-linux";
                    pkgs = import nixpkgs {{ inherit system; config = {{ allowUnfree = true; rocmSupport = true; }}; }};
                  in {{
                    devShells.${{system}}.default = pkgs.mkShell {{
                      buildInputs = with pkgs; [ python311 python311Packages.pip python311Packages.virtualenv rocmPackages.rocm-smi ffmpeg {'go cmake ninja gcc' if 'ollama' in workload else ''} ];
                      shellHook = ''
                        export HSA_OVERRIDE_GFX_VERSION=8.0.3
                        export ROC_ENABLE_PRE_VEGA=1
                        export MIOPEN_LOG_LEVEL=3
                        {'export COMMANDLINE_ARGS="--lowvram"' if 'comfyui' in workload else ''}
                        {'export JOBLIB_MULTIPROCESSING=0' if 'whisper' in workload else ''}
                        echo "❄️ Nix shell for GFX803 {workload} active!"
                      '';
                    }};
                  }};
                }}
                ''')
                Path("flake.nix").write_text(flake_content)
                print(f"{GREEN}Generated 'flake.nix' in current directory! Run `nix develop` to enter it.{RESET}")
        elif not nix:
            print(f"{BLUE}* TIP: Installing Nix can help avoid massive Docker rebuilds. (https://nixos.org/download){RESET}")

        # Integrated Research Path Recommendation
        matching_exps = get_matching_experiments(sys_info, workload, use_vulkan)
        if matching_exps:
            best = matching_exps[0]
            print(f"\n{BOLD}{YELLOW}>>> RECOMMENDED RESEARCH PATH: {best['label']} <<<{RESET}")
            print(f"Goal: {best['id']}")
            if best.get('resolves'):
                print(f"Resolves Uncertainty: {', '.join(best['resolves'])}")
            
            if "vulkan" in best['id']:
                print(f"Action: Run 'python atlas_runner.py capture' or 'python atlas_runner.py benchmark'")
            elif "kernel" in best['id'] or "kfd" in best['id']:
                 print(f"Action: Check 'dmesg -w' while running workloads and report offsets.")
            else:
                 print(f"Action: Run 'python atlas_runner.py update' to refresh local context and check 'out/' artifacts.")
        else:
            print(f"\n{YELLOW}* TIP: Run 'python atlas_runner.py update' to generate a ranked research plan for your system.{RESET}")

    elif args.command == "verify":
        env = args.env
        env_path = args.env_path
        print(f"{BLUE}{BOLD}GFX803 PROBE VERIFICATION{RESET}")
        
        probe_script = "probe.py"
        if not Path(probe_script).exists():
            print(f"{RED}Error: {probe_script} not found in current directory.{RESET}")
            return
            
        cmd = ""
        if env == "local":
            cmd = f"python {probe_script}"
        elif env == "docker":
            if not env_path:
                print(f"{RED}Please specify a Docker image via --env-path (e.g., my_rocm_docker_image){RESET}")
                return
            print(f"{YELLOW}Preparing Docker container from image '{env_path}'...{RESET}")
            cmd = f"docker run --rm --entrypoint '' -v $(pwd):/app -w /app --device=/dev/kfd --device=/dev/dri --group-add=video --ipc=host {env_path} python3 {probe_script}"
        elif env == "nix":
            if not env_path:
                print(f"{RED}Please specify a path to the Nix flake via --env-path (e.g., '../rr_gfx803_rocm'){RESET}")
                return
            print(f"{YELLOW}Spawning into Nix environment '{env_path}'...{RESET}")
            cmd = f"nix develop {env_path}#default --command python {probe_script}"
            
        print(f"\n{GREEN}Executing Test:{RESET}")
        print(f"  {cmd}\n")
        
        try:
            result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
            print(result.stdout)
            if result.stderr:
                print(f"{RED}STDERR output:{RESET}")
                print(result.stderr)
            
            # Parse structured output from the extended probe
            patch = {"nodes": [], "edges": []}
            out_lines = result.stdout.strip().splitlines()
            out_lower = result.stdout.lower()
            
            # Parse individual test results
            test_results = {}
            for line in out_lines:
                if line.startswith("TEST:"):
                    parts = line.split(":", 3)  # TEST:name:STATUS  detail
                    if len(parts) >= 3:
                        tname = parts[1]
                        tstatus = parts[2].split()[0].lower()
                        test_results[tname] = tstatus
            
            # Parse overall status
            status = "unknown"
            if "nan_inf_noise_detected" in out_lower:
                status = "failed_noise"
            elif "success_basic_compat" in out_lower:
                status = "success"
            elif "partial_pass" in out_lower:
                status = "partial"
            elif "segfault" in out_lower or result.returncode == 139:
                status = "failed_segfault"
            elif "no_torch" in out_lower:
                status = "missing_pytorch"
            elif "no_cuda_available" in out_lower:
                status = "missing_cuda_backend"
            
            # Parse PROBE_JSON for metadata
            probe_meta = {}
            for line in out_lines:
                if line.startswith("PROBE_JSON:"):
                    try:
                        probe_meta = json.loads(line[len("PROBE_JSON:"):])
                    except Exception:
                        pass
                
            print(f"\n{BOLD}=> Verdict: {status.upper()}{RESET}")
            if test_results:
                for tname, tstatus in test_results.items():
                    icon = f"{GREEN}✓{RESET}" if tstatus == "pass" else f"{RED}✗{RESET}"
                    print(f"   {icon} {tname}: {tstatus}")
            
            # Build graph patch — one node per run, edges to individual test observations
            target = env_path if env_path else "local_system"
            kernel = probe_meta.get("kernel", platform.release())
            node_id = f"fact:run:{env}:{target.replace('/', '_').replace(':', '_')}"
            
            patch["nodes"].append({
                "node_id": node_id,
                "label": f"Probe on {env}/{target}: {status} ({len(test_results)} tests, kernel {kernel})",
                "kind": "observation",
                "status": "known_known",
                "confidence": 1.0,
                "source": "verify_runner",
                "attrs": {
                    "verdict": status,
                    "env": env,
                    "kernel": kernel,
                    "pytorch": probe_meta.get("pytorch", "unknown"),
                    "tests": test_results,
                }
            })
            patch["edges"].append({
                "src": node_id,
                "dst": "hw:rx580",
                "relation": "observed_on",
                "source": "verify_runner"
            })
            
            # Create per-test nodes for failures so they link into the frontier
            for tname, tstatus in test_results.items():
                if tstatus != "pass":
                    fail_id = f"obs:probe_fail:{tname}:{env}"
                    patch["nodes"].append({
                        "node_id": fail_id,
                        "label": f"{tname} {tstatus} on {env}/{target}",
                        "kind": "observation",
                        "status": "known_known",
                        "source": "verify_runner",
                    })
                    patch["edges"].append({
                        "src": fail_id,
                        "dst": node_id,
                        "relation": "part_of",
                        "source": "verify_runner"
                    })
                    # Link conv failures to the first_bad_layer unknown
                    if "conv" in tname:
                        patch["edges"].append({
                            "src": fail_id,
                            "dst": "unk:first_bad_layer",
                            "relation": "narrows",
                            "source": "verify_runner"
                        })
            
            patch_file = f"probe_patch_{env}.json"
            Path(patch_file).write_text(json.dumps(patch, indent=2))
            
            print(f"{GREEN}Auto-generated patch `{patch_file}`. Automatically calling `python merge.py` to ingest...{RESET}")
            run_command(f"python merge.py seed_facts.json {patch_file} && python run_demo.py", "Merging probe facts and recalculating graph")
            
        except Exception as e:
             print(f"{RED}Failed to run verification command: {e}{RESET}")

    elif args.command == "viz":
        viz_path = Path("out/visualizer_portable.html").resolve()
        if viz_path.exists():
            print(f"{GREEN}Opening visualizer: {viz_path}{RESET}")
            # Try to open in browser
            import webbrowser
            webbrowser.open(f"file://{viz_path}")
        else:
            print(f"{RED}Portable visualizer not found. Run 'update' first.{RESET}")

    elif args.command == "plan":
        plan_path = Path("out/ranked_experiment_plan.json")
        if plan_path.exists():
            plan = json.loads(plan_path.read_text())
            print(f"{BLUE}{BOLD}RANKED EXPERIMENT PLAN{RESET}")
            print("-" * 50)
            for item in plan[:10]:
                print(f"{BOLD}[{item['score']}] {item['label']}{RESET}")
                print(f"  Cost: {item['cost']}")
                print(f"  Resolves: {', '.join(item['resolves'])}")
                print()
        else:
            print(f"{RED}Experiment plan not found. Run 'update' first.{RESET}")

    elif args.command == "capture":
        # Interactive-ish wrapper for the capture tool
        print(f"{BLUE}Launching capture helper...{RESET}")
        run_command("python vulkan_ground_truth_capture.py", "Initializing capture tool")

    elif args.command == "artifacts":
        out_dir = Path("out")
        print(f"{BLUE}{BOLD}GENERATED ARTIFACTS (out/){RESET}")
        if out_dir.exists():
            for f in out_dir.iterdir():
                print(f"  - {f.name} ({f.stat().st_size} bytes)")
        else:
            print("  (out/ directory does not exist yet)")
            
        sd_assets = Path("stable-diffusion.cpp/assets")
        if sd_assets.exists():
            print(f"\n{BLUE}{BOLD}STABLE-DIFFUSION.CPP ASSETS{RESET}")
            images = list(sd_assets.glob("*.png")) + list(sd_assets.glob("*.jpg"))
            for img in images[:15]:
                print(f"  - {img.name}")
            if len(images) > 15:
                print(f"  ... and {len(images)-15} more.")

    elif args.command == "benchmark":
        sd_bin = Path("stable-diffusion.cpp/build/bin/sd-cli")
        if not sd_bin.exists():
            # Try alternate path if using nix
            sd_bin = Path("stable-diffusion.cpp/bin/sd-cli")
            
        if sd_bin.exists():
            run_command(f"{sd_bin} --benchmark", "Running sd.cpp Vulkan benchmark")
        else:
            print(f"{RED}Error: sd-cli binary not found. Please build stable-diffusion.cpp first.{RESET}")

if __name__ == "__main__":
    main()
