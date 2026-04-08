#!/bin/bash
set -e
cd /home/user/YuNing/CultureDx

# Night 1: Model Scaling Chain
# Qwen3-8B (done), Qwen3-14B-AWQ, Qwen3-30B-A3B-AWQ, Qwen3-32B (done)

echo "=== Night 1: Model Scaling Chain ==="
echo "Start: $(date)"

# ── Step 1: Qwen3-14B-AWQ ──────────────────────────────
echo ""
echo "=== Step 1: Qwen3-14B-AWQ ($(date)) ==="

# Kill any existing vLLM
pkill -f "vllm serve" 2>/dev/null || true
sleep 3

# Start vLLM for 14B-AWQ
echo "Starting vLLM for Qwen3-14B-AWQ..."
nohup vllm serve Qwen/Qwen3-14B-AWQ \
  --port 8000 --max-model-len 32768 \
  --gpu-memory-utilization 0.92 --dtype auto --enforce-eager \
  > /tmp/vllm_14b_awq.log 2>&1 &
VLLM_PID=$!
echo "vLLM PID: $VLLM_PID"

# Wait for vLLM to be ready
echo "Waiting for vLLM..."
for i in $(seq 1 120); do
  if curl -s http://localhost:8000/v1/models | grep -q "model"; then
    echo "vLLM ready after ${i}s"
    break
  fi
  sleep 2
done

# Run Single
echo "Running Qwen3-14B-AWQ Single..."
uv run python3 scripts/run_api_backbone.py \
  --provider vllm --model "Qwen/Qwen3-14B-AWQ" \
  --max-cases 1000 --concurrent 8 --merge-2c4c \
  --skip-dtv \
  --output-dir outputs/scaling/qwen3-14b-awq 2>&1 | tee outputs/scaling/qwen3-14b-awq/single.log

# Run DtV
echo "Running Qwen3-14B-AWQ DtV..."
uv run python3 scripts/run_api_backbone.py \
  --provider vllm --model "Qwen/Qwen3-14B-AWQ" \
  --max-cases 1000 --concurrent 8 --merge-2c4c \
  --skip-single --skip-triage \
  --output-dir outputs/scaling/qwen3-14b-awq 2>&1 | tee outputs/scaling/qwen3-14b-awq/dtv.log

echo "Qwen3-14B-AWQ DONE at $(date)"

# ── Step 2: Qwen3-30B-A3B-AWQ ──────────────────────────
echo ""
echo "=== Step 2: Qwen3-30B-A3B-AWQ ($(date)) ==="

# Kill vLLM and restart with new model
kill $VLLM_PID 2>/dev/null || true
pkill -f "vllm serve" 2>/dev/null || true
sleep 5

echo "Starting vLLM for Qwen3-30B-A3B-AWQ..."
nohup vllm serve stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ \
  --port 8000 --max-model-len 32768 \
  --gpu-memory-utilization 0.92 --dtype auto --enforce-eager \
  > /tmp/vllm_30b_a3b_awq.log 2>&1 &
VLLM_PID=$!
echo "vLLM PID: $VLLM_PID"

# Wait for vLLM to be ready
echo "Waiting for vLLM..."
for i in $(seq 1 180); do
  if curl -s http://localhost:8000/v1/models | grep -q "model"; then
    echo "vLLM ready after ${i}s"
    break
  fi
  sleep 2
done

# Run Single
echo "Running Qwen3-30B-A3B-AWQ Single..."
uv run python3 scripts/run_api_backbone.py \
  --provider vllm --model "stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ" \
  --max-cases 1000 --concurrent 8 --merge-2c4c \
  --skip-dtv \
  --output-dir outputs/scaling/qwen3-30b-a3b-awq 2>&1 | tee outputs/scaling/qwen3-30b-a3b-awq/single.log

# Run DtV
echo "Running Qwen3-30B-A3B-AWQ DtV..."
uv run python3 scripts/run_api_backbone.py \
  --provider vllm --model "stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ" \
  --max-cases 1000 --concurrent 8 --merge-2c4c \
  --skip-single --skip-triage \
  --output-dir outputs/scaling/qwen3-30b-a3b-awq 2>&1 | tee outputs/scaling/qwen3-30b-a3b-awq/dtv.log

echo "Qwen3-30B-A3B-AWQ DONE at $(date)"

# Kill vLLM
kill $VLLM_PID 2>/dev/null || true

echo ""
echo "=== Night 1 COMPLETE at $(date) ==="
echo "Score all results:"
echo "  uv run python3 scripts/score_scaling.py"
