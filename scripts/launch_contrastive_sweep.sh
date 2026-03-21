#!/bin/bash
# launch_contrastive_sweep.sh
# Contrastive disambiguation 2×2 ablation: hied ± contrastive, n=200, seed=42
# Datasets: LingxiDiag16k, MDD-5k
# vLLM: Qwen3-32B-AWQ with APC, 24K context
#
# Conditions per dataset:
#   1. hied_no_evidence (contrastive OFF) — V10 baseline
#   2. hied_no_evidence (contrastive ON)  — V11 contrastive
#
# V10 baseline uses LLM cache, so only contrastive runs require fresh LLM calls.
#
# Usage:
#   ./scripts/launch_contrastive_sweep.sh
#
# Logs appended to: outputs/launch_contrastive.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LOGFILE="$ROOT/outputs/launch_contrastive.log"
PORT=8000

mkdir -p "$ROOT/outputs"
exec > >(tee -a "$LOGFILE") 2>&1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=========================================="
log "Contrastive ablation sweep starting"
log "Root: $ROOT"
log "=========================================="

# Check vLLM health
log "Checking vLLM health..."
if curl -s "http://localhost:${PORT}/health" > /dev/null 2>&1; then
    log "  vLLM server healthy on port ${PORT}."
else
    log "ERROR: vLLM server not responding on port ${PORT}."
    exit 1
fi

cd "$ROOT"

# === LingxiDiag16k ===

log "=== LingxiDiag16k: hied baseline (contrastive OFF) ==="
uv run python scripts/ablation_sweep.py \
    --provider vllm \
    --model Qwen/Qwen3-32B-AWQ \
    --modes hied \
    --no-evidence \
    -n 200 \
    --seed 42 \
    --dataset lingxidiag16k \
    --sweep-name contrastive_off_lingxidiag

log "=== LingxiDiag16k: hied contrastive (contrastive ON) ==="
uv run python scripts/ablation_sweep.py \
    --provider vllm \
    --model Qwen/Qwen3-32B-AWQ \
    --modes hied \
    --no-evidence \
    --contrastive \
    -n 200 \
    --seed 42 \
    --dataset lingxidiag16k \
    --sweep-name contrastive_on_lingxidiag

# === MDD-5k ===

log "=== MDD-5k: hied baseline (contrastive OFF) ==="
uv run python scripts/ablation_sweep.py \
    --provider vllm \
    --model Qwen/Qwen3-32B-AWQ \
    --modes hied \
    --no-evidence \
    -n 200 \
    --seed 42 \
    --dataset mdd5k_raw \
    --sweep-name contrastive_off_mdd5k

log "=== MDD-5k: hied contrastive (contrastive ON) ==="
uv run python scripts/ablation_sweep.py \
    --provider vllm \
    --model Qwen/Qwen3-32B-AWQ \
    --modes hied \
    --no-evidence \
    --contrastive \
    -n 200 \
    --seed 42 \
    --dataset mdd5k_raw \
    --sweep-name contrastive_on_mdd5k

log "=========================================="
log "Contrastive ablation sweep complete"
log "=========================================="
