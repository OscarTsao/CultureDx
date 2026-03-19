#!/bin/bash
# Monitor GPU and run pilot experiment when enough VRAM is available.
# Usage: nohup bash scripts/run_when_gpu_free.sh > /tmp/gpu_wait.log 2>&1 &

REQUIRED_FREE_MB=22000  # qwen3:32b needs ~20GB + KV cache
CHECK_INTERVAL=60       # Check every 60 seconds
MODEL="qwen3:32b"
MODES="hied,single,psycot"

echo "$(date): Waiting for ${REQUIRED_FREE_MB}MB free GPU memory..."

while true; do
    FREE_MB=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1)
    echo "$(date): GPU free: ${FREE_MB}MB (need ${REQUIRED_FREE_MB}MB)"

    if [ "$FREE_MB" -ge "$REQUIRED_FREE_MB" ] 2>/dev/null; then
        echo "$(date): GPU available! Starting experiment..."

        # Kill any existing Ollama
        pkill -9 -f "ollama serve" 2>/dev/null
        pkill -9 -f "ollama runner" 2>/dev/null
        sleep 3

        # Start Ollama with optimal settings
        OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=1 OLLAMA_MAX_LOADED_MODELS=1 \
            nohup /home/user/ollama-local/bin/ollama serve > /tmp/ollama_experiment.log 2>&1 &
        sleep 5

        # Verify Ollama is running
        if curl -s http://localhost:11434/ > /dev/null 2>&1; then
            echo "$(date): Ollama started. Running experiment..."
            cd /home/user/YuNing/CultureDx
            uv run python scripts/pilot_experiment.py \
                --n-cases 20 \
                --model "$MODEL" \
                --output-dir outputs/pilot_v5 \
                --cache-dir data/cache \
                --modes "$MODES" \
                --target-disorders "F32,F33,F41.1,F42,F43.1" 2>&1 | tee /tmp/pilot_v5.log

            echo "$(date): Experiment complete!"
            exit 0
        else
            echo "$(date): Ollama failed to start"
            exit 1
        fi
    fi

    sleep "$CHECK_INTERVAL"
done
