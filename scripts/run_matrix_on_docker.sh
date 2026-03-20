#!/usr/bin/env bash
# run_matrix_on_docker.sh
# Runs the drift validation matrix across different container implementations
# Usage: ./scripts/run_matrix_on_docker.sh robertrosenbusch/rocm6_gfx803_comfyui:5.7

set -e

IMAGE=$1
if [ -z "$IMAGE" ]; then
    echo "Usage: $0 <docker-image>"
    exit 1
fi

echo "=== Pulling $IMAGE ==="
docker pull "$IMAGE"

NAME=$(echo "$IMAGE" | tr ':/' '_')
RESULTS_FILE="results_${NAME}.jsonl"
rm -f "$RESULTS_FILE"

# Make our python script available inside
SCRIPT_DIR="$(pwd)/tests"

run_case() {
    TEST_NAME=$1
    shift
    
    echo "--- Running $TEST_NAME on $IMAGE ---"
    
    # Run the test inside docker
    # We pass the environment variables inside docker run
    # and map the test script
    # Then we run it and tee the stdout to capture whatever it prints
    docker run --rm --entrypoint "" \
        --device=/dev/kfd --device=/dev/dri --group-add video --ipc=host \
        -v "$SCRIPT_DIR:/tester" \
        -e HSA_OVERRIDE_GFX_VERSION=8.0.3 \
        -e ROC_ENABLE_PRE_VEGA=1 \
        "$@" \
        "$IMAGE" \
        bash -c "source /ComfyUI/venv/bin/activate 2>/dev/null || source /Whisper-WebUI/venv/bin/activate 2>/dev/null || echo 'Assume global python' && python3 /tester/drift_core.py" > "tmp_output_${TEST_NAME}.log" 2>&1
    
    if grep -q "FINAL_JSON=" "tmp_output_${TEST_NAME}.log"; then
        grep "FINAL_JSON=" "tmp_output_${TEST_NAME}.log" | sed 's/FINAL_JSON=//' >> "$RESULTS_FILE"
        echo "Successfully collected result."
    else
        echo "Failed to get JSON output. See tmp_output_${TEST_NAME}.log"
        cat "tmp_output_${TEST_NAME}.log"
    fi
}

run_case "default"
run_case "direct_only" -e MIOPEN_DEBUG_CONV_DIRECT=1 -e MIOPEN_DEBUG_CONV_GEMM=0
run_case "gemm_only" -e MIOPEN_DEBUG_CONV_DIRECT=0 -e MIOPEN_DEBUG_CONV_GEMM=1

echo "Done running matrix. Results:"
cat "$RESULTS_FILE"
