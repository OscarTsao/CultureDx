#!/bin/bash
# Wait for V5 evidence sweep to finish, restart vLLM optimized, then launch N=200.
# Usage: nohup bash scripts/launch_n200_after_v5.sh > outputs/launch_n200.log 2>&1 &

V5_PID=1834947
N200_LOG="outputs/vllm_n200.log"

echo "$(date): Waiting for V5 evidence sweep (PID=$V5_PID) to finish..."

while kill -0 "$V5_PID" 2>/dev/null; do
    PROGRESS=$(grep -oP '\d+/50' outputs/vllm_v5.log 2>/dev/null | tail -1)
    echo "$(date): V5 at $PROGRESS"
    sleep 60
done

echo "$(date): V5 evidence sweep completed!"

# Restart vLLM with higher max-num-seqs for no-evidence runs
echo "$(date): Restarting vLLM with max-num-seqs=4 (no BGE-M3 needed)..."
VLLM_PID=$(pgrep -f "vllm.entrypoints")
if [ -n "$VLLM_PID" ]; then
    kill "$VLLM_PID"
    sleep 5
fi

cd /home/user/YuNing/CultureDx

nohup python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-32B-AWQ \
    --host 0.0.0.0 --port 8000 \
    --max-model-len 24576 \
    --gpu-memory-utilization 0.90 \
    --tensor-parallel-size 1 \
    --max-num-seqs 4 \
    --swap-space 4 \
    --dtype auto \
    --quantization awq \
    --trust-remote-code \
    --no-enable-log-requests \
    --enforce-eager \
    > /tmp/vllm_n200.log 2>&1 &

echo "$(date): Waiting for vLLM to start..."
sleep 30

# Verify vLLM is ready
for i in $(seq 1 12); do
    if curl -s http://localhost:8000/v1/models > /dev/null 2>&1; then
        echo "$(date): vLLM ready!"
        break
    fi
    echo "$(date): Waiting for vLLM... ($i/12)"
    sleep 10
done

echo "$(date): Launching N=200 3-mode sweep (hied, psycot, single)..."

nohup uv run python scripts/ablation_sweep.py \
    --provider vllm --model "Qwen/Qwen3-32B-AWQ" \
    --modes hied,psycot,single \
    --no-evidence \
    -n 200 --seed 42 \
    --sweep-name n200_3mode \
    > "$N200_LOG" 2>&1 &

N200_PID=$!
echo "$(date): N=200 sweep launched (PID=$N200_PID)"
echo "$(date): Log: $N200_LOG"
echo "PID=$N200_PID" > outputs/n200_pid.txt
