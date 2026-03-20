#!/bin/bash
# Launch vLLM server for CultureDx experiments
# Hardware: RTX 5090 32GB GDDR7 (SM_120 Blackwell)
# Model: Qwen3-32B-AWQ (4-bit quantized, ~18.5GB model + 8.8GB KV cache)
#
# Usage:
#   ./scripts/launch_vllm.sh              # Start server
#   ./scripts/launch_vllm.sh --stop       # Stop server
#   ./scripts/launch_vllm.sh --status     # Check server status
#   ./scripts/launch_vllm.sh --smoke      # Run smoke test

set -euo pipefail

MODEL="Qwen/Qwen3-32B-AWQ"
PORT=8000
HOST="0.0.0.0"
MAX_MODEL_LEN=16384       # 16K context + transcript truncation for long cases
GPU_MEMORY_UTILIZATION=0.90  # Leave ~3.2GB for runtime overhead
TENSOR_PARALLEL=1
MAX_NUM_SEQS=4             # 4 concurrent with 16K context
SWAP_SPACE=4               # 4GB CPU swap for overflow sequences
LOGFILE="outputs/vllm_server.log"
PIDFILE="/tmp/vllm_culturedx.pid"

case "${1:-start}" in
    --stop|stop)
        if [ -f "$PIDFILE" ]; then
            PID=$(cat "$PIDFILE")
            echo "Stopping vLLM server (PID: $PID)..."
            kill "$PID" 2>/dev/null || true
            rm -f "$PIDFILE"
            echo "Done."
        else
            echo "No PID file found. Checking for running vllm processes..."
            pkill -f "vllm.entrypoints.openai.api_server" 2>/dev/null && echo "Killed." || echo "No vLLM server running."
        fi
        ;;

    --status|status)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            echo "vLLM server running (PID: $(cat "$PIDFILE"))"
            curl -s "http://localhost:${PORT}/health" && echo " [healthy]" || echo " [not responding]"
        else
            echo "vLLM server not running"
        fi
        ;;

    --smoke|smoke)
        echo "Running smoke test against vLLM at localhost:${PORT}..."
        curl -s -X POST "http://localhost:${PORT}/v1/chat/completions" \
            -H "Content-Type: application/json" \
            -d '{
                "model": "'"$MODEL"'",
                "messages": [{"role": "user", "content": "Say hello in Chinese. Reply with one sentence only."}],
                "temperature": 0.0,
                "max_tokens": 100,
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": false}
                }
            }' | python3 -m json.tool
        echo ""

        # Test concurrent requests (simulating parallel criterion checking)
        echo "Testing 5 concurrent requests..."
        for i in $(seq 1 5); do
            curl -s -X POST "http://localhost:${PORT}/v1/chat/completions" \
                -H "Content-Type: application/json" \
                -d '{
                    "model": "'"$MODEL"'",
                    "messages": [{"role": "user", "content": "What is disorder F3'"$i"' in ICD-10? Reply in one sentence."}],
                    "temperature": 0.0,
                    "max_tokens": 100,
                    "extra_body": {
                        "chat_template_kwargs": {"enable_thinking": false}
                    }
                }' &
        done
        echo "Waiting for concurrent requests..."
        wait
        echo "Concurrent test done."
        ;;

    --start|start)
        # Stop Ollama if running (they compete for GPU)
        echo "Checking for running Ollama..."
        if pgrep -x ollama > /dev/null 2>&1; then
            echo "WARNING: Ollama is running. Stop it first to free GPU memory."
            echo "  systemctl --user stop ollama  OR  ollama stop"
            echo "  Then re-run this script."
            exit 1
        fi

        mkdir -p outputs

        echo "Launching vLLM server..."
        echo "  Model: $MODEL"
        echo "  Port: $PORT"
        echo "  Max context: $MAX_MODEL_LEN tokens"
        echo "  GPU utilization: $GPU_MEMORY_UTILIZATION"
        echo "  Max concurrent seqs: $MAX_NUM_SEQS"
        echo "  Log: $LOGFILE"

        # Launch vLLM
        python -m vllm.entrypoints.openai.api_server \
            --model "$MODEL" \
            --host "$HOST" \
            --port "$PORT" \
            --max-model-len "$MAX_MODEL_LEN" \
            --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
            --tensor-parallel-size "$TENSOR_PARALLEL" \
            --max-num-seqs "$MAX_NUM_SEQS" \
            --swap-space "$SWAP_SPACE" \
            --dtype auto \
            --quantization awq \
            --trust-remote-code \
            --no-enable-log-requests \
            --enforce-eager \
            > "$LOGFILE" 2>&1 &

        VLLM_PID=$!
        echo "$VLLM_PID" > "$PIDFILE"
        echo "vLLM server started (PID: $VLLM_PID)"
        echo "Waiting for server to be ready..."

        # Wait for server to be healthy (model loading takes ~30-60s)
        for i in $(seq 1 120); do
            if curl -s "http://localhost:${PORT}/health" > /dev/null 2>&1; then
                echo "Server ready after ${i}s!"
                echo ""
                echo "Usage:"
                echo "  # Run ablation sweep with vLLM"
                echo "  uv run python scripts/ablation_sweep.py --provider vllm --model $MODEL -n 50"
                echo ""
                echo "  # Stop server"
                echo "  ./scripts/launch_vllm.sh --stop"
                exit 0
            fi
            # Check if process died
            if ! kill -0 "$VLLM_PID" 2>/dev/null; then
                echo "ERROR: vLLM server died during startup. Check $LOGFILE"
                tail -20 "$LOGFILE"
                rm -f "$PIDFILE"
                exit 1
            fi
            sleep 1
        done

        echo "WARNING: Server did not become healthy in 120s. Check $LOGFILE"
        tail -20 "$LOGFILE"
        ;;

    *)
        echo "Usage: $0 [--start|--stop|--status|--smoke]"
        exit 1
        ;;
esac
