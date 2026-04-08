#!/bin/bash
# Selective reasoning: Diagnostician think=true, Checker think=false
# Requires vLLM with --reasoning-parser qwen3
# Usage: bash scripts/run_selective_reasoning.sh [N_CASES]

set -e
N=${1:-50}
OUTDIR=outputs/eval/dtv_v2_reasoning_${N}

echo "=== Selective Reasoning Mode (N=$N) ==="

pkill -f "vllm serve" 2>/dev/null || true
sleep 5

echo "Starting Qwen3-32B-AWQ with reasoning parser..."
vllm serve Qwen/Qwen3-32B-AWQ \
    --port 8000 --max-model-len 32768 \
    --gpu-memory-utilization 0.9 --dtype auto \
    --reasoning-parser qwen3 \
    > /tmp/vllm_reasoning.log 2>&1 &

for i in $(seq 1 90); do
    curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "Qwen" && break
    sleep 3
done
echo "vLLM ready with reasoning parser."

# TODO: Need to wire per-agent thinking toggle into the pipeline
# Currently disable_thinking is global. Need to modify:
# - HiEDMode._diagnose_then_verify to pass enable_thinking=True to diagnostician
# - CriterionCheckerAgent to pass enable_thinking=False
# For now, run with thinking=true for all (baseline comparison)

CUDA_VISIBLE_DEVICES="" uv run culturedx run \
    -c configs/vllm_awq_reasoning.yaml \
    -c configs/hied_dtv_v2.yaml \
    -d lingxidiag16k --data-path data/raw/lingxidiag16k \
    -n $N -o $OUTDIR \
    2>&1 | tee ${OUTDIR}.log

echo "=== Selective reasoning done. Results in $OUTDIR ==="
