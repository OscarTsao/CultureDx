#!/bin/bash
# Cross-family model probe: test F32 bias on different model families
# Usage: bash scripts/run_cross_family_probe.sh [yi|glm|both]

set -e
TARGET=${1:-yi}
N_CASES=100

echo "=== Cross-Family Model Probe ==="

if [[ "$TARGET" == "yi" || "$TARGET" == "both" ]]; then
    echo "--- Yi-1.5-34B-Chat-AWQ ---"
    
    # Kill existing vLLM
    pkill -f "vllm serve" 2>/dev/null || true
    sleep 3
    
    # Start Yi on port 8000
    vllm serve 01-ai/Yi-1.5-34B-Chat-AWQ \
        --port 8000 --max-model-len 16384 \
        --gpu-memory-utilization 0.9 --dtype auto \
        > /tmp/vllm_yi.log 2>&1 &
    
    echo "Waiting for Yi vLLM..."
    for i in $(seq 1 90); do
        curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "Yi" && break
        sleep 3
    done
    echo "Yi ready."
    
    # Run single baseline probe
    python scripts/run_api_backbone.py \
        --provider vllm --model 01-ai/Yi-1.5-34B-Chat-AWQ \
        --max-cases $N_CASES --output-dir outputs/probe/yi-34b \
        --skip-dtv --skip-triage
    
    echo "Yi probe complete."
fi

if [[ "$TARGET" == "glm" || "$TARGET" == "both" ]]; then
    echo "--- GLM-4-9B-Chat ---"
    
    pkill -f "vllm serve" 2>/dev/null || true
    sleep 3
    
    vllm serve THUDM/glm-4-9b-chat \
        --port 8000 --max-model-len 16384 \
        --gpu-memory-utilization 0.5 --dtype auto \
        > /tmp/vllm_glm.log 2>&1 &
    
    echo "Waiting for GLM vLLM..."
    for i in $(seq 1 60); do
        curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "glm" && break
        sleep 3
    done
    echo "GLM ready."
    
    python scripts/run_api_backbone.py \
        --provider vllm --model THUDM/glm-4-9b-chat \
        --max-cases $N_CASES --output-dir outputs/probe/glm-4-9b \
        --skip-dtv --skip-triage
    
    echo "GLM probe complete."
fi

echo "=== Probe done. Check outputs/probe/ for results ==="
