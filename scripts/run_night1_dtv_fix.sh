#!/bin/bash
set -euo pipefail
cd /home/user/YuNing/CultureDx

log() { echo "[$(date '+%H:%M:%S')] $*"; }

start_vllm() {
  local model="$1"
  pkill -f "vllm serve" 2>/dev/null || true
  sleep 5
  log "Starting vLLM: $model"
  nohup vllm serve "$model" \
    --port 8000 --max-model-len 32768 \
    --gpu-memory-utilization 0.92 --dtype auto --enforce-eager \
    > /tmp/vllm_current.log 2>&1 &
  for i in $(seq 1 180); do
    if curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "model"; then
      log "vLLM ready after ${i}s"
      return 0
    fi
    sleep 2
  done
  log "ERROR: vLLM failed"; return 1
}

log "=== DtV Fix: Run DtV for 14B + 30B ==="

# ── 14B DtV ──
start_vllm "Qwen/Qwen3-14B-AWQ"
mkdir -p outputs/scaling/qwen3-14b-awq-dtv
log "Running 14B DtV..."
uv run python3 scripts/run_api_backbone.py \
  --provider vllm --model "Qwen/Qwen3-14B-AWQ" \
  --max-cases 1000 --concurrent 8 --merge-2c4c \
  --skip-single --skip-triage \
  --output-dir outputs/scaling/qwen3-14b-awq-dtv 2>&1 | tee outputs/scaling/qwen3-14b-awq-dtv/run.log
log "14B DtV DONE"

# ── 30B DtV ──
start_vllm "stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ"
mkdir -p outputs/scaling/qwen3-30b-a3b-awq-dtv
log "Running 30B DtV..."
uv run python3 scripts/run_api_backbone.py \
  --provider vllm --model "stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ" \
  --max-cases 1000 --concurrent 8 --merge-2c4c \
  --skip-single --skip-triage \
  --output-dir outputs/scaling/qwen3-30b-a3b-awq-dtv 2>&1 | tee outputs/scaling/qwen3-30b-a3b-awq-dtv/run.log
log "30B DtV DONE"

pkill -f "vllm serve" 2>/dev/null || true
log "=== ALL DONE ==="
