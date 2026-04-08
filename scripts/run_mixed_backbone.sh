#!/bin/bash
# Mixed-backbone DtV: Yi diagnostician + Qwen checker
# Requires: Yi-34B on port 8000, Qwen3-32B-AWQ on port 8001
# Usage: bash scripts/run_mixed_backbone.sh

set -e
N_CASES=${1:-50}

echo "=== Mixed Backbone: Yi diagnostician + Qwen checker ==="

# Kill existing vLLM
pkill -f "vllm serve" 2>/dev/null || true
sleep 3

# Start Yi-34B as diagnostician (port 8000, ~18GB)
echo "Starting Yi-34B on port 8000..."
vllm serve 01-ai/Yi-1.5-34B-Chat-AWQ \
    --port 8000 --max-model-len 16384 \
    --gpu-memory-utilization 0.55 --dtype auto \
    > /tmp/vllm_yi.log 2>&1 &

sleep 10

# Start Qwen3-8B as checker (port 8001, ~5GB)
echo "Starting Qwen3-8B on port 8001..."
vllm serve Qwen/Qwen3-8B \
    --port 8001 --max-model-len 16384 \
    --gpu-memory-utilization 0.30 --dtype auto \
    > /tmp/vllm_qwen.log 2>&1 &

echo "Waiting for both models..."
for i in $(seq 1 90); do
    YI_OK=$(curl -s http://localhost:8000/v1/models 2>/dev/null | grep -c "Yi")
    QW_OK=$(curl -s http://localhost:8001/v1/models 2>/dev/null | grep -c "Qwen")
    if [ "$YI_OK" -gt 0 ] && [ "$QW_OK" -gt 0 ]; then
        echo "Both models ready."
        break
    fi
    sleep 3
done

# Run DtV v2.2 with mixed backbone
# Main LLM (diagnostician): Yi on port 8000
# Checker LLM: Qwen on port 8001
CUDA_VISIBLE_DEVICES="" uv run culturedx run \
    -c configs/vllm_awq.yaml \
    -c configs/hied_dtv_v2.yaml \
    -d lingxidiag16k --data-path data/raw/lingxidiag16k \
    -n $N_CASES \
    -o outputs/eval/mixed_yi_qwen_${N_CASES} \
    --llm-base-url http://localhost:8000 \
    --llm-model "01-ai/Yi-1.5-34B-Chat-AWQ" \
    --checker-base-url http://localhost:8001 \
    --checker-model "Qwen/Qwen3-8B"

echo "=== Mixed backbone done ==="
