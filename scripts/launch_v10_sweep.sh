#!/bin/bash
# launch_v10_sweep.sh
# V10 ablation sweep: hied + psycot, no-evidence, n=200, seed=42
# Datasets: LingxiDiag16k, MDD-5k
# vLLM: Qwen3-32B-AWQ with APC (Automatic Prefix Caching), 24K context
#
# Usage:
#   ./scripts/launch_v10_sweep.sh
#
# Logs appended to: outputs/vllm_v10_sweep.log

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths (absolute, resolved from this script's location)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LOGFILE="$ROOT/outputs/vllm_v10_sweep.log"
PIDFILE="/tmp/vllm_culturedx.pid"
PORT=8000
MODEL="Qwen/Qwen3-32B-AWQ"

# ---------------------------------------------------------------------------
# Logging helper — all output goes to stdout AND the log file (append)
# ---------------------------------------------------------------------------
mkdir -p "$ROOT/outputs"
exec > >(tee -a "$LOGFILE") 2>&1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=========================================="
log "V10 sweep starting"
log "Root: $ROOT"
log "Log:  $LOGFILE"
log "=========================================="

# ---------------------------------------------------------------------------
# Step 1: Kill the current vLLM server
# ---------------------------------------------------------------------------
log "Step 1: Stopping existing vLLM server..."

if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    log "  Found PID file: $OLD_PID"
    if kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID"
        log "  Sent SIGTERM to PID $OLD_PID"
    else
        log "  PID $OLD_PID is not running"
    fi
    rm -f "$PIDFILE"
else
    log "  No PID file found; trying pkill..."
    pkill -f "vllm.entrypoints.openai.api_server" 2>/dev/null && log "  Killed vLLM process(es)." || log "  No vLLM process found."
fi

# ---------------------------------------------------------------------------
# Step 2: Wait 5 seconds for GPU memory to free
# ---------------------------------------------------------------------------
log "Step 2: Waiting 5 seconds for GPU memory to free..."
sleep 5
log "  Done waiting."

# ---------------------------------------------------------------------------
# Step 3: Restart vLLM with APC (Automatic Prefix Caching), 24K context
# ---------------------------------------------------------------------------
log "Step 3: Starting vLLM server (model=$MODEL, port=$PORT, apc=enabled, max-model-len=24576)..."

cd "$ROOT"
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-32B-AWQ \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 24576 \
    --gpu-memory-utilization 0.90 \
    --tensor-parallel-size 1 \
    --max-num-seqs 4 \
    --swap-space 4 \
    --dtype auto \
    --quantization awq \
    --trust-remote-code \
    --no-enable-log-requests \
    --enable-prefix-caching \
    >> "$ROOT/outputs/vllm_server_v10.log" 2>&1 &

VLLM_PID=$!
echo "$VLLM_PID" > "$PIDFILE"
log "  vLLM server started (PID: $VLLM_PID)"
log "  Server log: $ROOT/outputs/vllm_server_v10.log"

# ---------------------------------------------------------------------------
# Step 4: Wait for vLLM health check (up to 120 seconds)
# ---------------------------------------------------------------------------
log "Step 4: Waiting for vLLM health check (timeout 120s)..."

READY=0
for i in $(seq 1 120); do
    if curl -s "http://localhost:${PORT}/health" > /dev/null 2>&1; then
        log "  Server healthy after ${i}s."
        READY=1
        break
    fi
    # Abort early if the server process has already died
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        log "ERROR: vLLM server process (PID $VLLM_PID) died during startup."
        log "       Check $ROOT/outputs/vllm_server_v10.log for details."
        tail -30 "$ROOT/outputs/vllm_server_v10.log" || true
        exit 1
    fi
    sleep 1
done

if [ "$READY" -eq 0 ]; then
    log "ERROR: vLLM server did not become healthy within 120s."
    log "       Check $ROOT/outputs/vllm_server_v10.log for details."
    tail -30 "$ROOT/outputs/vllm_server_v10.log" || true
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 5a: V10 sweep — LingxiDiag16k
# ---------------------------------------------------------------------------
log "Step 5a: Running V10 sweep for LingxiDiag16k (n=200, modes=hied,psycot, no-evidence)..."

cd "$ROOT"
uv run python scripts/ablation_sweep.py \
    --provider vllm \
    --model Qwen/Qwen3-32B-AWQ \
    --modes hied,psycot \
    --no-evidence \
    -n 200 \
    --seed 42 \
    --dataset lingxidiag16k \
    --sweep-name v10_lingxidiag

log "  LingxiDiag16k sweep complete."

# ---------------------------------------------------------------------------
# Step 5b: V10 sweep — MDD-5k
# ---------------------------------------------------------------------------
log "Step 5b: Running V10 sweep for MDD-5k (n=200, modes=hied,psycot, no-evidence)..."

cd "$ROOT"
uv run python scripts/ablation_sweep.py \
    --provider vllm \
    --model Qwen/Qwen3-32B-AWQ \
    --modes hied,psycot \
    --no-evidence \
    -n 200 \
    --seed 42 \
    --dataset mdd5k_raw \
    --sweep-name v10_mdd5k

log "  MDD-5k sweep complete."

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "=========================================="
log "V10 sweep complete"
log "=========================================="
echo "V10 sweep complete"
