#!/bin/bash
set -euo pipefail
cd /home/user/YuNing/CultureDx

# ==========================================================================
# Night 2: Architecture Ablations on Qwen3-32B-AWQ
#   Run 4: DtV + RareClassSpecialist (~2hr with concurrency)
#   Run 5: DtV + Mixed Checker 32B+8B (~2hr)
#   Run 6: DtV + Ensemble 32B+30B-A3B (~3hr)
# ==========================================================================

LOG_DIR="outputs/ablations"
mkdir -p "$LOG_DIR"

wait_for_vllm() {
    local port="${1:-8000}"
    local max_wait=300
    local waited=0
    echo "[$(date +%H:%M:%S)] Waiting for vLLM on port $port ..."
    while ! curl -s "http://localhost:${port}/v1/models" > /dev/null 2>&1; do
        sleep 5
        waited=$((waited + 5))
        if [ "$waited" -ge "$max_wait" ]; then
            echo "ERROR: vLLM on port $port not ready after ${max_wait}s"
            exit 1
        fi
    done
    echo "[$(date +%H:%M:%S)] vLLM on port $port ready (waited ${waited}s)"
}

kill_vllm() {
    echo "[$(date +%H:%M:%S)] Stopping vLLM processes ..."
    pkill -f "vllm serve" || true
    sleep 5
}

# ==========================================================================
# Ablation 4: DtV + RareClassSpecialist
# ==========================================================================
echo ""
echo "================================================================"
echo "  Ablation 4: DtV + RareClassSpecialist (32B)"
echo "  Started: $(date)"
echo "================================================================"

kill_vllm
vllm serve Qwen/Qwen3-32B-AWQ \
    --port 8000 --max-model-len 32768 \
    --gpu-memory-utilization 0.92 --dtype auto --enforce-eager &
wait_for_vllm 8000

uv run python3 scripts/run_api_backbone.py \
    --provider vllm --model Qwen/Qwen3-32B-AWQ \
    --max-cases 1000 --concurrent 8 --merge-2c4c \
    --skip-single --skip-triage --rare-specialist \
    --output-dir outputs/ablations/dtv-rare-specialist \
    2>&1 | tee "$LOG_DIR/run4_rare_specialist.log"

echo "[$(date +%H:%M:%S)] Ablation 4 complete."

# ==========================================================================
# Ablation 5: DtV + Mixed Checker (32B diagnostician + 8B checker)
# ==========================================================================
echo ""
echo "================================================================"
echo "  Ablation 5: DtV + Mixed Checker (32B diag + 8B checker)"
echo "  Started: $(date)"
echo "================================================================"

kill_vllm

# Dual vLLM: 32B on port 8000 (55% GPU), 8B on port 8001 (30% GPU)
vllm serve Qwen/Qwen3-32B-AWQ \
    --port 8000 --max-model-len 16384 \
    --gpu-memory-utilization 0.55 --dtype auto --enforce-eager &
vllm serve Qwen/Qwen3-8B \
    --port 8001 --max-model-len 16384 \
    --gpu-memory-utilization 0.30 --dtype auto --enforce-eager &
wait_for_vllm 8000
wait_for_vllm 8001

uv run python3 scripts/run_api_backbone.py \
    --provider vllm --model Qwen/Qwen3-32B-AWQ \
    --checker-base-url http://localhost:8001/v1 --checker-model Qwen/Qwen3-8B \
    --max-cases 1000 --concurrent 4 --merge-2c4c \
    --skip-single --skip-triage \
    --output-dir outputs/ablations/dtv-mixed-checker \
    2>&1 | tee "$LOG_DIR/run5_mixed_checker.log"

echo "[$(date +%H:%M:%S)] Ablation 5 complete."

# ==========================================================================
# Ablation 6: DtV + Ensemble Diagnostician (32B + 30B-A3B Borda merge)
# ==========================================================================
echo ""
echo "================================================================"
echo "  Ablation 6: DtV + Ensemble (32B + 30B-A3B Borda)"
echo "  Started: $(date)"
echo "================================================================"

kill_vllm

vllm serve Qwen/Qwen3-32B-AWQ \
    --port 8000 --max-model-len 16384 \
    --gpu-memory-utilization 0.55 --dtype auto --enforce-eager &
vllm serve stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ \
    --port 8001 --max-model-len 16384 \
    --gpu-memory-utilization 0.35 --dtype auto --enforce-eager &
wait_for_vllm 8000
wait_for_vllm 8001

uv run python3 scripts/run_api_backbone.py \
    --provider vllm --model Qwen/Qwen3-32B-AWQ \
    --ensemble --ensemble-base-url http://localhost:8001/v1 \
    --ensemble-model stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ \
    --max-cases 1000 --concurrent 4 --merge-2c4c \
    --skip-single --skip-triage \
    --output-dir outputs/ablations/dtv-ensemble \
    2>&1 | tee "$LOG_DIR/run6_ensemble.log"

echo "[$(date +%H:%M:%S)] Ablation 6 complete."

# ==========================================================================
# Cleanup
# ==========================================================================
kill_vllm

echo ""
echo "================================================================"
echo "  Night 2 complete: $(date)"
echo "  Results in outputs/ablations/"
echo "================================================================"
