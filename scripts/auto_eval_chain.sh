#!/usr/bin/env bash
# Auto-chain: watches finetune PID, then runs full eval pipeline.
#
# Phase 1: Wait for finetune (PID $FINETUNE_PID) to finish
# Phase 2: Full eval with Qwen3-32B-AWQ (vLLM)
# Phase 3: Full eval with finetuned Qwen3-8B (vLLM + LoRA adapter)
# Phase 4: Reasoning/CoT ablation
#
# Usage:
#   FINETUNE_PID=320737 nohup ./scripts/auto_eval_chain.sh > outputs/eval/auto_chain.log 2>&1 &

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FINETUNE_PID=${FINETUNE_PID:-320737}
VLLM_PORT=${VLLM_PORT:-8000}
VLLM_URL="http://localhost:${VLLM_PORT}"
DATASETS="lingxidiag,mdd5k"
BATCH_SIZE=50
EVAL_SCRIPT="scripts/run_full_eval.py"

LOG_DIR="outputs/eval/logs"
mkdir -p "$LOG_DIR"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
    log "FATAL: $*"
    exit 1
}

wait_for_pid() {
    local pid=$1
    local label=$2
    log "Waiting for ${label} (PID ${pid}) to finish..."
    while kill -0 "$pid" 2>/dev/null; do
        sleep 60
    done
    log "${label} (PID ${pid}) finished."
}

stop_vllm() {
    local pids
    pids=$(pgrep -f "vllm.entrypoints" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        log "Stopping existing vLLM processes: $pids"
        kill $pids 2>/dev/null || true
        sleep 5
        for p in $pids; do
            if kill -0 "$p" 2>/dev/null; then
                kill -9 "$p" 2>/dev/null || true
            fi
        done
        sleep 2
    fi
}

start_vllm() {
    local model=$1
    local extra_args="${2:-}"
    local logfile="${LOG_DIR}/vllm_$(echo "$model" | tr '/' '_').log"

    stop_vllm
    sleep 3

    log "Starting vLLM with model: $model"
    nohup vllm serve "$model" \
        --port "$VLLM_PORT" \
        --tensor-parallel-size 1 \
        --max-model-len 16384 \
        --gpu-memory-utilization 0.90 \
        --dtype auto \
        $extra_args \
        > "$logfile" 2>&1 &
    local vllm_pid=$!
    log "vLLM PID: $vllm_pid (log: $logfile)"

    local timeout=600
    local elapsed=0
    while [[ $elapsed -lt $timeout ]]; do
        if curl -fsS "${VLLM_URL}/health" > /dev/null 2>&1; then
            log "vLLM is healthy after ${elapsed}s"
            return 0
        fi
        if ! kill -0 "$vllm_pid" 2>/dev/null; then
            die "vLLM died during startup. Check $logfile"
        fi
        sleep 10
        elapsed=$((elapsed + 10))
    done
    die "vLLM did not become healthy within ${timeout}s"
}

run_eval() {
    local model_name=$1
    local output_dir=$2
    local extra_args="${3:-}"
    local logfile="${LOG_DIR}/eval_$(basename "$output_dir").log"

    log "=== Starting eval: $model_name -> $output_dir ==="

    python3 "$EVAL_SCRIPT" \
        --config configs/base.yaml \
        --config configs/vllm_awq.yaml \
        --config configs/hied.yaml \
        --datasets "$DATASETS" \
        --modes hied,single \
        --model-name "$model_name" \
        --batch-size "$BATCH_SIZE" \
        --output-dir "$output_dir" \
        --with-evidence \
        --with-somatization \
        --resume \
        $extra_args \
        > "$logfile" 2>&1

    local rc=$?
    if [[ $rc -eq 0 ]]; then
        log "Eval completed successfully: $output_dir"
    else
        log "WARNING: Eval exited with code $rc: $output_dir (continuing chain)"
    fi
    return 0
}

# Phase 1: Wait for finetune
if kill -0 "$FINETUNE_PID" 2>/dev/null; then
    wait_for_pid "$FINETUNE_PID" "QLoRA finetune"
else
    log "Finetune PID $FINETUNE_PID already finished."
fi

FINETUNE_OUTPUT="outputs/finetune/qwen3_8b_teacher_v1"
if [[ ! -d "$FINETUNE_OUTPUT" ]]; then
    die "Finetune output directory not found: $FINETUNE_OUTPUT"
fi
log "Finetune output found at $FINETUNE_OUTPUT"

# Phase 2: Qwen3-32B-AWQ
log "===== PHASE 2: Qwen3-32B-AWQ evaluation ====="
start_vllm "Qwen/Qwen3-32B-AWQ"
run_eval "Qwen/Qwen3-32B-AWQ" "outputs/eval/full_qwen3_32b_awq"

# Phase 3: Finetuned Qwen3-8B
log "===== PHASE 3: Finetuned Qwen3-8B evaluation ====="
BEST_CKPT=$(ls -d "$FINETUNE_OUTPUT"/checkpoint-* 2>/dev/null | sort -t- -k2 -n | tail -1)
if [[ -z "$BEST_CKPT" ]]; then
    log "WARNING: No checkpoint found in $FINETUNE_OUTPUT -- skipping finetuned model eval"
else
    log "Using checkpoint: $BEST_CKPT"
    stop_vllm
    sleep 3

    LORA_LOGFILE="${LOG_DIR}/vllm_qwen3_8b_lora.log"
    log "Starting vLLM with Qwen3-8B + LoRA adapter"
    nohup vllm serve "Qwen/Qwen3-8B" \
        --port "$VLLM_PORT" \
        --tensor-parallel-size 1 \
        --max-model-len 16384 \
        --gpu-memory-utilization 0.90 \
        --dtype auto \
        --enable-lora \
        --lora-modules "culturedx-checker=$BEST_CKPT" \
        --max-lora-rank 16 \
        > "$LORA_LOGFILE" 2>&1 &
    VLLM_LORA_PID=$!

    timeout=600
    elapsed=0
    vllm_ok=0
    while [[ $elapsed -lt $timeout ]]; do
        if curl -fsS "${VLLM_URL}/health" > /dev/null 2>&1; then
            log "vLLM+LoRA is healthy after ${elapsed}s"
            vllm_ok=1
            break
        fi
        if ! kill -0 "$VLLM_LORA_PID" 2>/dev/null; then
            log "WARNING: vLLM+LoRA died during startup. Check $LORA_LOGFILE"
            break
        fi
        sleep 10
        elapsed=$((elapsed + 10))
    done

    if [[ $vllm_ok -eq 1 ]]; then
        run_eval "culturedx-checker" \
            "outputs/eval/full_qwen3_8b_finetune" \
            "--adapter-path $BEST_CKPT"
    else
        log "WARNING: Could not start vLLM+LoRA -- skipping finetuned model eval"
    fi
fi

# Phase 4: Reasoning/CoT ablation
log "===== PHASE 4: Reasoning/CoT ablation ====="
stop_vllm
sleep 5

export MAX_CASES=200
export MODEL="Qwen/Qwen3-32B-AWQ"
export DATASETS="lingxidiag,mdd5k"

if [[ -x scripts/run_reasoning_eval.sh ]]; then
    log "Running reasoning ablation script..."
    ./scripts/run_reasoning_eval.sh > "${LOG_DIR}/reasoning_ablation.log" 2>&1 || {
        log "WARNING: Reasoning ablation exited with errors (see log)"
    }
else
    log "WARNING: scripts/run_reasoning_eval.sh not found or not executable"
fi

# Done
stop_vllm
log "===== ALL EVALUATION PHASES COMPLETE ====="
log "Results:"
log "  Phase 2: outputs/eval/full_qwen3_32b_awq/"
log "  Phase 3: outputs/eval/full_qwen3_8b_finetune/"
log "  Phase 4: outputs/eval/reasoning_ablation/"
