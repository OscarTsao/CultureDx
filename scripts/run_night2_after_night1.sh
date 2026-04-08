#!/bin/bash
set -euo pipefail
cd /home/user/YuNing/CultureDx

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# Wait for Night 1 DtV fix to complete (PID file or process check)
NIGHT1_PID=$(ps aux | grep "run_night1_dtv_fix" | grep -v grep | awk '{print $2}' | head -1)

if [ -n "$NIGHT1_PID" ]; then
    log "Waiting for Night 1 DtV (PID $NIGHT1_PID) to complete..."
    while kill -0 "$NIGHT1_PID" 2>/dev/null; do
        sleep 30
    done
    log "Night 1 DtV complete!"
else
    log "Night 1 DtV not running (already done or not found)"
fi

# Kill any leftover vLLM from Night 1
pkill -f "vllm serve" 2>/dev/null || true
sleep 5

log "=== Starting Night 2: Architecture Ablations ==="
exec bash /home/user/YuNing/CultureDx/scripts/run_night2_chain.sh
