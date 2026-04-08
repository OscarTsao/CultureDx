#!/bin/bash
# Sequential mixed-backbone: different model per agent role
# Phase 1: Yi-34B diagnostician → save rankings
# Phase 2: Qwen3-32B-AWQ checker → verify rankings
# Usage: bash scripts/run_sequential_mixed.sh [N_CASES]

set -e
N=${1:-100}
OUTDIR=outputs/eval/mixed_sequential_${N}

echo "=== Sequential Mixed Backbone (N=$N) ==="
echo "Phase 1: Yi-34B-AWQ diagnostician"
echo "Phase 2: Qwen3-32B-AWQ checker"
echo "Output: $OUTDIR"
echo ""

# --- Phase 1: Yi-34B diagnostician ---
pkill -f "vllm serve" 2>/dev/null || true
sleep 5

echo "[Phase 1] Starting Yi-34B-AWQ..."
vllm serve 01-ai/Yi-1.5-34B-Chat-AWQ \
    --port 8000 --max-model-len 16384 \
    --gpu-memory-utilization 0.9 --dtype auto \
    > /tmp/vllm_phase1.log 2>&1 &

for i in $(seq 1 90); do
    curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "Yi" && break
    sleep 3
done
echo "[Phase 1] Yi ready. Running diagnostician-only..."

# Run DtV with Yi as main LLM, skip checker phase (save diagnostician output)
CUDA_VISIBLE_DEVICES="" uv run culturedx run \
    -c configs/vllm_awq.yaml \
    -c configs/hied_dtv_v2.yaml \
    -d lingxidiag16k --data-path data/raw/lingxidiag16k \
    -n $N -o ${OUTDIR}_phase1 \
    2>&1 | tee ${OUTDIR}_phase1.log

echo "[Phase 1] Complete."

# --- Phase 2: Qwen3-32B-AWQ checker ---
pkill -f "vllm serve" 2>/dev/null || true
sleep 5

echo "[Phase 2] Starting Qwen3-32B-AWQ..."
vllm serve Qwen/Qwen3-32B-AWQ \
    --port 8000 --max-model-len 32768 \
    --gpu-memory-utilization 0.9 --dtype auto \
    > /tmp/vllm_phase2.log 2>&1 &

for i in $(seq 1 90); do
    curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "Qwen" && break
    sleep 3
done
echo "[Phase 2] Qwen ready. Running checker with saved diagnostician rankings..."

# Re-run DtV with Qwen as checker (diagnostician results cached from phase 1)
CUDA_VISIBLE_DEVICES="" uv run culturedx run \
    -c configs/vllm_awq.yaml \
    -c configs/hied_dtv_v2.yaml \
    -d lingxidiag16k --data-path data/raw/lingxidiag16k \
    -n $N -o $OUTDIR \
    2>&1 | tee ${OUTDIR}.log

echo "=== Sequential mixed done. Results in $OUTDIR ==="
