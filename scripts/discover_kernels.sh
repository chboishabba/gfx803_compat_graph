#!/usr/bin/env bash
# Discover and individual testing for Tensile kernels
# Requires: roctracer, rocprofiler in PATH

set -e

RESULTS_DIR=${DRIFT_RESULTS_DIR:-./out}
mkdir -p "$RESULTS_DIR"

echo "=== Tensile Kernel Discovery Mode ==="

# Step 1: Run MRE with profiling to capture kernel names
echo "Tracing kernels..."
# We use a short run (e.g. 5 iterations) to capture the names
env MIOPEN_DEBUG_CONV_DET=1 \
    MIOPEN_DEBUG_DISABLE_FIND_DB=1 \
    rocprof --hip-trace python tests/bug_report_mre.py --iterations 5 > "$RESULTS_DIR/discovery_trace.log" 2>&1

# Step 2: Extract unique Tensile kernels
# Tensile kernels usually contain 'Cijk' or 'Tensile'
kernels=$(grep -oE "Cijk_[A-Za-z0-9_]+" results.stats.csv | sort -u)

if [ -z "$kernels" ]; then
    echo "No Tensile kernels detected in trace."
    exit 1
fi

echo "Detected Kernels:"
echo "$kernels"

# Step 3: Test each kernel individually (if MIOpen allowed forcing specific Tensile kernels)
# Note: MIOpen doesn't easily allow forcing a specific Tensile *identity* via env vars, 
# but it does allow forcing Solver families (GEMM vs Direct vs Winograd).
# For deep individual kernel testing, we usually need to patch the Tensile library or 
# use a standalone Tensile runner.

# For now, we record the discovery into the graph.
for k in $kernels; do
    echo "Registering kernel: $k"
    jq -n --arg k "$k" '{type: "tensile_kernel", name: $k, status: "detected"}' >> "$RESULTS_DIR/kernels.jsonl"
done

echo "Discovery complete. Kernels saved to $RESULTS_DIR/kernels.jsonl"
