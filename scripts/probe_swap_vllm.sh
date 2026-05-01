#!/usr/bin/env bash
# Kill existing vLLM and start a new one with the given model.
# Usage: swap_vllm.sh <model_id> [<extra_vllm_args>]
set -e -u -o pipefail

MODEL="${1:?model_id required}"
shift || true
EXTRA_ARGS="$*"

echo "[swap_vllm] killing existing vLLM (port 8000)..."
pkill -f "vllm.entrypoints.openai.api_server" || true
sleep 5
# Force kill if still alive
pgrep -f "vllm.entrypoints" | xargs -r kill -9 2>/dev/null || true
sleep 3

echo "[swap_vllm] free port 8000? $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/v1/models 2>/dev/null || echo 'down')"

echo "[swap_vllm] starting vLLM with model: ${MODEL}"
echo "[swap_vllm] extra args: ${EXTRA_ARGS}"

# Detect AWQ vs raw
QUANT_FLAGS=""
if [[ "${MODEL}" == *"AWQ"* ]] || [[ "${MODEL}" == *"awq"* ]]; then
    QUANT_FLAGS="--quantization awq_marlin"
fi

nohup /home/user/miniforge3/bin/python3 -m vllm.entrypoints.openai.api_server \
    --model "${MODEL}" \
    ${QUANT_FLAGS} \
    --port 8000 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.92 \
    --dtype float16 \
    --enforce-eager \
    ${EXTRA_ARGS} \
    > /tmp/vllm_${MODEL//\//_}.log 2>&1 &

VLLM_PID=$!
echo "[swap_vllm] vLLM PID: ${VLLM_PID}"

# Wait until ready
echo "[swap_vllm] waiting for vLLM to come up..."
for i in $(seq 1 120); do
    if curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "${MODEL##*/}"; then
        echo "[swap_vllm] vLLM ready after ${i}*5=$((i*5))s"
        exit 0
    fi
    sleep 5
done

echo "[swap_vllm] TIMEOUT — vLLM did not come up in 600s"
tail -50 /tmp/vllm_${MODEL//\//_}.log
exit 1
