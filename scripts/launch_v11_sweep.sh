#!/bin/bash
# launch_v11_sweep.sh
# V11 ablation sweep: hied + psycot, no-evidence, n=200, seed=42
# Datasets: LingxiDiag16k, MDD-5k
# vLLM: Qwen3-32B-AWQ with APC (Automatic Prefix Caching), 24K context
#
# V11 changes being tested:
#   Fix 9:  Conditional proportion-based calibrator (alpha=0.7 contested, 1.0 normal)
#   Fix 10: Extra-soft F41.1 threshold (2/4 met with anxiety-specific criterion)
#   Fix 11: F41.1 Criterion A prompt relaxation (accept chronic worry without temporal markers)
#
# NOTE: vLLM server is assumed to already be running from V10. Steps 1-4 are
#       skipped; we only verify health before launching the sweep.
#
# Usage:
#   ./scripts/launch_v11_sweep.sh
#
# Logs appended to: outputs/launch_v11.log

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths (absolute, resolved from this script's location)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LOGFILE="$ROOT/outputs/launch_v11.log"
PORT=8000

# ---------------------------------------------------------------------------
# Logging helper — all output goes to stdout AND the log file (append)
# ---------------------------------------------------------------------------
mkdir -p "$ROOT/outputs"
exec > >(tee -a "$LOGFILE") 2>&1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=========================================="
log "V11 sweep starting"
log "Root: $ROOT"
log "Log:  $LOGFILE"
log "=========================================="

# ---------------------------------------------------------------------------
# Step 1: Check vLLM health (server should already be running from V10)
# ---------------------------------------------------------------------------
log "Step 1: Checking vLLM health (server expected to be running from V10)..."

if curl -s "http://localhost:${PORT}/health" > /dev/null 2>&1; then
    log "  vLLM server is healthy on port ${PORT}."
else
    log "ERROR: vLLM server is not responding on port ${PORT}."
    log "       Please start the vLLM server (e.g., via launch_v10_sweep.sh) before running V11."
    log "       Server log: $ROOT/outputs/vllm_server_v11.log"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 2a: V11 sweep — LingxiDiag16k
# ---------------------------------------------------------------------------
log "Step 2a: Running V11 sweep for LingxiDiag16k (n=200, modes=hied,psycot, no-evidence)..."

cd "$ROOT"
uv run python scripts/ablation_sweep.py \
    --provider vllm \
    --model Qwen/Qwen3-32B-AWQ \
    --modes hied,psycot \
    --no-evidence \
    -n 200 \
    --seed 42 \
    --dataset lingxidiag16k \
    --sweep-name v11_lingxidiag

log "  LingxiDiag16k sweep complete."

# ---------------------------------------------------------------------------
# Step 2b: V11 sweep — MDD-5k
# ---------------------------------------------------------------------------
log "Step 2b: Running V11 sweep for MDD-5k (n=200, modes=hied,psycot, no-evidence)..."

cd "$ROOT"
uv run python scripts/ablation_sweep.py \
    --provider vllm \
    --model Qwen/Qwen3-32B-AWQ \
    --modes hied,psycot \
    --no-evidence \
    -n 200 \
    --seed 42 \
    --dataset mdd5k_raw \
    --sweep-name v11_mdd5k

log "  MDD-5k sweep complete."

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "=========================================="
log "V11 sweep complete"
log "=========================================="
echo "V11 sweep complete"
