#!/bin/bash
set -euo pipefail
cd /home/user/YuNing/CultureDx

log() { echo "[$(date '+%H:%M:%S')] $*"; }

wait_for_download() {
  local model_dir="$1"
  log "Waiting for download: $model_dir"
  while [ "$(ls "$model_dir"/blobs/*.incomplete 2>/dev/null | wc -l)" -gt 0 ]; do
    sleep 10
  done
  log "Download complete: $model_dir"
}

start_vllm() {
  local model="$1"
  local max_model_len="${2:-32768}"
  
  pkill -f "vllm serve" 2>/dev/null || true
  sleep 5
  
  log "Starting vLLM: $model (max_model_len=$max_model_len)"
  nohup vllm serve "$model" \
    --port 8000 --max-model-len "$max_model_len" \
    --gpu-memory-utilization 0.92 --dtype auto --enforce-eager \
    > /tmp/vllm_current.log 2>&1 &
  
  log "Waiting for vLLM to be ready..."
  for i in $(seq 1 180); do
    if curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "model"; then
      log "vLLM ready after ${i}s"
      return 0
    fi
    sleep 2
  done
  log "ERROR: vLLM failed to start!"
  return 1
}

run_experiment() {
  local model="$1"
  local output_dir="$2"
  local label="$3"
  
  mkdir -p "$output_dir"
  
  # Single
  log "Running $label Single..."
  uv run python3 scripts/run_api_backbone.py \
    --provider vllm --model "$model" \
    --max-cases 1000 --concurrent 8 --merge-2c4c \
    --skip-dtv \
    --output-dir "$output_dir" 2>&1 | tee "$output_dir/single.log"
  
  # DtV (skip triage, rank all 12 directly)
  log "Running $label DtV..."
  uv run python3 scripts/run_api_backbone.py \
    --provider vllm --model "$model" \
    --max-cases 1000 --concurrent 8 --merge-2c4c \
    --skip-single --skip-triage \
    --output-dir "$output_dir" 2>&1 | tee "$output_dir/dtv.log"
  
  log "$label DONE"
}

# ═══════════════════════════════════════════════════════════════
log "=== Night 1: Model Scaling Chain ==="

# ── Qwen3-14B-AWQ ──
HF_14B="/home/user/.cache/huggingface/hub/models--Qwen--Qwen3-14B-AWQ"
wait_for_download "$HF_14B"
start_vllm "Qwen/Qwen3-14B-AWQ"
run_experiment "Qwen/Qwen3-14B-AWQ" "outputs/scaling/qwen3-14b-awq" "Qwen3-14B-AWQ"

# ── Qwen3-30B-A3B-AWQ ──
HF_30B="/home/user/.cache/huggingface/hub/models--stelterlab--Qwen3-30B-A3B-Instruct-2507-AWQ"
wait_for_download "$HF_30B"
start_vllm "stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ"
run_experiment "stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ" "outputs/scaling/qwen3-30b-a3b-awq" "Qwen3-30B-A3B-AWQ"

# ── Cleanup ──
pkill -f "vllm serve" 2>/dev/null || true

log "=== Night 1 COMPLETE ==="
log "Score: uv run python3 scripts/score_scaling.py"
