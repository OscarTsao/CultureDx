#!/bin/bash
# launch_final_sweep.sh
# Final sweep: paper main results table
#
# Matrix: 3 modes × 3 conditions × 2 datasets = 18 runs
#   Modes: hied, psycot, single
#   Conditions: no_evidence, bge-m3_evidence (with somatization), bge-m3_no_somatization
#   Datasets: lingxidiag16k, mdd5k_raw
#
# All improvements applied:
#   - Calibrator V2 weights (LOO-CV tuned)
#   - Prompt engineering (F41.1/A,B1,B2 + F32/C2,C3 FN reduction)
#   - Chief complaint + demographics in triage prompt
#   - Platt scaling available for post-hoc calibration
#
# LLM cache: Single mode likely cache-hits (prompt unchanged).
#             HiED + PsyCoT checker prompts changed → cache miss for criterion checking.
#             Triage prompts changed → cache miss for triage.
#
# Usage:
#   ./scripts/launch_final_sweep.sh
#
# Logs: outputs/launch_final_sweep.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LOGFILE="$ROOT/outputs/launch_final_sweep.log"
PORT=8000

mkdir -p "$ROOT/outputs"
exec > >(tee -a "$LOGFILE") 2>&1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=========================================="
log "Final sweep starting (paper main results)"
log "Root: $ROOT"
log "Log:  $LOGFILE"
log "=========================================="

# Check vLLM health
log "Checking vLLM health..."
if curl -s "http://localhost:${PORT}/health" > /dev/null 2>&1; then
    log "  vLLM server healthy on port ${PORT}."
else
    log "ERROR: vLLM server not responding on port ${PORT}."
    log "       Start with: ./scripts/launch_vllm.sh"
    exit 1
fi

cd "$ROOT"

# ---------------------------------------------------------------------------
# LingxiDiag16k: 3 modes × 3 conditions = 9 runs
# ---------------------------------------------------------------------------
log "=========================================="
log "Dataset 1/2: LingxiDiag16k (n=200)"
log "=========================================="

uv run python scripts/ablation_sweep.py \
    --provider vllm \
    --model Qwen/Qwen3-32B-AWQ \
    --modes hied,psycot,single \
    --full \
    --retriever bge-m3 \
    -n 200 \
    --seed 42 \
    --dataset lingxidiag16k \
    --sweep-name final_lingxidiag

log "LingxiDiag16k sweep complete."

# ---------------------------------------------------------------------------
# MDD-5k: 3 modes × 3 conditions = 9 runs
# ---------------------------------------------------------------------------
log "=========================================="
log "Dataset 2/2: MDD-5k (n=200)"
log "=========================================="

uv run python scripts/ablation_sweep.py \
    --provider vllm \
    --model Qwen/Qwen3-32B-AWQ \
    --modes hied,psycot,single \
    --full \
    --retriever bge-m3 \
    -n 200 \
    --seed 42 \
    --dataset mdd5k_raw \
    --sweep-name final_mdd5k

log "MDD-5k sweep complete."

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log "=========================================="
log "Final sweep complete! 18 conditions total."
log "Results:"
log "  outputs/sweeps/final_lingxidiag_*/sweep_report.json"
log "  outputs/sweeps/final_mdd5k_*/sweep_report.json"
log "=========================================="
