#!/usr/bin/env bash
set -euo pipefail

# run_drift_matrix_on_nix.sh
# Runs the drift tests under the current Nix environment.

OUTDIR="${1:-results}"
mkdir -p "$OUTDIR"

run_case () {
  NAME=$1
  shift

  echo "=== RUNNING $NAME ==="
  
  # Run the core python test, capturing only the JSON output
  JSON_OUT=$("$@" python tests/drift_core.py | grep "FINAL_JSON=" | sed 's/FINAL_JSON=//')
  
  if [ -n "$JSON_OUT" ]; then
    echo "$JSON_OUT" | jq . > "$OUTDIR/${NAME}.json"
    echo "Saved $OUTDIR/${NAME}.json"
  else
    echo "Failed to capture JSON for $NAME"
  fi
}

# Run Direct
run_case direct \
  env MIOPEN_DEBUG_CONV_DIRECT=1 MIOPEN_DEBUG_CONV_GEMM=0 

# Run GEMM
run_case gemm \
  env MIOPEN_DEBUG_CONV_DIRECT=0 MIOPEN_DEBUG_CONV_GEMM=1 

# Run Stable Profile
run_case stable_profile \
  env MIOPEN_DEBUG_CONV_WINOGRAD=0 MIOPEN_DEBUG_CONV_FFT=0 MIOPEN_DEBUG_DISABLE_FIND_DB=1 MIOPEN_FIND_ENFORCE=3
