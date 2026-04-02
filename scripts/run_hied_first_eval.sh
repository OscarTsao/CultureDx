#!/usr/bin/env bash
# HiED-first evaluation chain: runs HiED ablations first, then other modes.
#
# Priority order:
#   Phase 1: Wait for finetune (if running)
#   Phase 2: HiED ablations (Qwen3-32B-AWQ)
#     - hied-baseline:         no evidence, no reasoning
#     - hied-evidence:         with evidence + somatization
#     - hied-no-somat:         with evidence, no somatization
#     - hied-reasoning:        reasoning enabled (disable_thinking=false)
#     - hied-reasoning-evidence: reasoning + evidence
#     - hied-cot:              CoT prompt variant
#     - hied-reasoning-cot:    reasoning + CoT
#   Phase 3: Other modes (single, psycot)
#     - single-baseline
#     - psycot-evidence
#   Phase 4: Finetuned model eval (if checkpoint available)
#
# Usage:
#   nohup ./scripts/run_hied_first_eval.sh > outputs/eval/hied_first.log 2>&1 &
#   FINETUNE_PID=320737 ./scripts/run_hied_first_eval.sh
#   SKIP_FINETUNE_WAIT=1 ./scripts/run_hied_first_eval.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN=${PYTHON_BIN:-python3}
VLLM_PORT=${VLLM_PORT:-8000}
VLLM_URL="http://localhost:${VLLM_PORT}"
MODEL=${MODEL:-"Qwen/Qwen3-32B-AWQ"}
DATASETS=${DATASETS:-"lingxidiag,mdd5k"}
EVAL_SCRIPT="scripts/run_full_eval.py"
BATCH_SIZE=${BATCH_SIZE:-100}
OUTPUT_BASE=${OUTPUT_BASE:-"outputs/eval/hied_first_$(date +%Y%m%d_%H%M%S)"}
LOG_DIR="${OUTPUT_BASE}/logs"
FINETUNE_PID=${FINETUNE_PID:-""}
SKIP_FINETUNE_WAIT=${SKIP_FINETUNE_WAIT:-0}
FINETUNE_OUTPUT="outputs/finetune/qwen3_8b_teacher_v1"

mkdir -p "$LOG_DIR"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
    log "FATAL: $*"
    exit 1
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

    if curl -fsS "${VLLM_URL}/health" > /dev/null 2>&1; then
        log "vLLM already healthy at ${VLLM_URL}"
        return 0
    fi

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

run_condition() {
    local name="$1"
    local mode="$2"
    local with_evidence="$3"
    local with_somat="$4"
    local thinking="$5"
    local variant="${6:-}"
    local extra_yaml="${7:-}"
    local output_dir="${OUTPUT_BASE}/${name}"
    local log_file="${LOG_DIR}/${name}.log"

    mkdir -p "$output_dir"

    # Build temporary config overlay for thinking/reasoning settings
    local tmp_cfg
    tmp_cfg="$(mktemp "${TMPDIR:-/tmp}/culturedx_eval_XXXXXX.yaml")"

    local max_tokens temperature top_k disable_thinking
    if [[ "$thinking" == "true" ]]; then
        max_tokens=4096
        temperature=0.6
        top_k=20
        disable_thinking=false
    else
        max_tokens=2048
        temperature=0.0
        top_k=1
        disable_thinking=true
    fi

    cat > "$tmp_cfg" <<YAML
llm:
  provider: vllm
  model_id: "${MODEL}"
  base_url: "${VLLM_URL}"
  temperature: ${temperature}
  top_k: ${top_k}
  disable_thinking: ${disable_thinking}
  max_tokens: ${max_tokens}
  max_concurrent: 32
mode:
  name: ${mode}
  type: ${mode}
  prompt_variant: "${variant}"
YAML

    # Append any extra YAML overrides (e.g. retriever/reranker config)
    if [[ -n "$extra_yaml" ]]; then
        printf '\n%s\n' "$extra_yaml" >> "$tmp_cfg"
    fi

    local -a config_args=(
        --config configs/base.yaml
    )
    if [[ -f "configs/${mode}.yaml" ]]; then
        config_args+=(--config "configs/${mode}.yaml")
    fi
    config_args+=(
        --config configs/vllm_awq.yaml
    )
    if [[ "$with_evidence" == "1" ]]; then
        config_args+=(--config configs/evidence.yaml)
    fi
    if [[ "$thinking" == "true" ]]; then
        config_args+=(--config configs/reasoning.yaml)
    fi
    config_args+=(--config "$tmp_cfg")

    local -a eval_args=(
        "$PYTHON_BIN" "$EVAL_SCRIPT"
        "${config_args[@]}"
        --datasets "$DATASETS"
        --modes "$mode"
        --model-name "$MODEL"
        --batch-size "$BATCH_SIZE"
        --output-dir "$output_dir"
        --split validation
        --resume
    )
    if [[ "$with_evidence" == "1" ]]; then
        eval_args+=(--with-evidence)
    fi
    if [[ "$with_evidence" == "1" && "$with_somat" == "1" ]]; then
        eval_args+=(--with-somatization)
    fi

    log "=== Condition: ${name} (mode=${mode}, evidence=${with_evidence}, somat=${with_somat}, thinking=${thinking}, variant=${variant}) ==="
    if "${eval_args[@]}" 2>&1 | tee "$log_file"; then
        log "=== Done: ${name} ==="
    else
        log "=== WARNING: ${name} exited with errors (continuing chain) ==="
    fi
    rm -f "$tmp_cfg"
}

# ============================================================
# Phase 1: Wait for finetune (optional)
# ============================================================
if [[ "$SKIP_FINETUNE_WAIT" != "1" && -n "$FINETUNE_PID" ]]; then
    if kill -0 "$FINETUNE_PID" 2>/dev/null; then
        log "Waiting for finetune PID $FINETUNE_PID to finish..."
        while kill -0 "$FINETUNE_PID" 2>/dev/null; do
            sleep 60
        done
        log "Finetune PID $FINETUNE_PID finished."
    else
        log "Finetune PID $FINETUNE_PID already finished."
    fi
fi

# ============================================================
# Phase 2: HiED ablations (primary — run first)
# ============================================================
log "===== PHASE 2: HiED ablations ====="
start_vllm "$MODEL"

#               name                     mode   evidence somat  thinking variant
run_condition  "hied-baseline"          "hied"  "0"     "0"    "false"  ""
run_condition  "hied-evidence"          "hied"  "1"     "1"    "false"  ""
run_condition  "hied-no-somat"          "hied"  "1"     "0"    "false"  ""
run_condition  "hied-mock-evidence"     "hied"  "1"     "1"    "false"  "" "evidence:
  retriever:
    name: mock"
run_condition  "hied-evidence-rerank"   "hied"  "1"     "1"    "false"  "" "evidence:
  rerank_enabled: true
  rerank_top_n: 5"
run_condition  "hied-reasoning"         "hied"  "0"     "0"    "true"   ""
run_condition  "hied-reasoning-evidence" "hied" "1"     "1"    "true"   ""
run_condition  "hied-cot"              "hied"  "0"     "0"    "false"  "cot"
run_condition  "hied-reasoning-cot"    "hied"  "0"     "0"    "true"   "cot"
run_condition  "hied-full-pipeline"    "hied"  "1"     "1"    "true"   "cot"

log "===== HiED ablations complete ====="

# ============================================================
# Phase 3: Other modes (lower priority)
# ============================================================
log "===== PHASE 3: Other modes ====="

run_condition  "single-baseline"       "single" "0"    "0"    "false"  ""
run_condition  "psycot-evidence"       "psycot" "1"    "1"    "false"  ""
run_condition  "psycot-reasoning-cot"  "psycot" "1"    "1"    "true"   "cot"

log "===== Other modes complete ====="

# ============================================================
# Phase 4: Finetuned model eval (if checkpoint available)
# ============================================================
BEST_CKPT=$(ls -d "$FINETUNE_OUTPUT"/checkpoint-* 2>/dev/null | sort -t- -k2 -n | tail -1 || true)
if [[ -n "$BEST_CKPT" ]]; then
    log "===== PHASE 4: Finetuned Qwen3-8B eval ====="
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
        # Create a temporary config for the finetuned model
        FT_CFG="$(mktemp "${TMPDIR:-/tmp}/culturedx_ft_XXXXXX.yaml")"
        cat > "$FT_CFG" <<YAML
llm:
  provider: vllm
  model_id: "culturedx-checker"
  base_url: "${VLLM_URL}"
  temperature: 0.0
  top_k: 1
  disable_thinking: true
  max_tokens: 2048
  max_concurrent: 32
YAML
        FT_OUT="${OUTPUT_BASE}/hied-finetuned"
        mkdir -p "$FT_OUT"
        FT_LOG="${LOG_DIR}/hied-finetuned.log"

        "$PYTHON_BIN" "$EVAL_SCRIPT" \
            --config configs/base.yaml \
            --config configs/hied.yaml \
            --config configs/vllm_awq.yaml \
            --config "$FT_CFG" \
            --datasets "$DATASETS" \
            --modes hied \
            --model-name "culturedx-checker" \
            --batch-size "$BATCH_SIZE" \
            --output-dir "$FT_OUT" \
            --split validation \
            --with-evidence \
            --with-somatization \
            --resume \
            2>&1 | tee "$FT_LOG" || log "WARNING: Finetuned eval exited with errors"

        rm -f "$FT_CFG"
    else
        log "WARNING: Could not start vLLM+LoRA — skipping finetuned model eval"
    fi
else
    log "No finetune checkpoint found — skipping Phase 4"
fi

# Cleanup
stop_vllm
log "===== ALL EVALUATION PHASES COMPLETE ====="
log "Results directory: ${OUTPUT_BASE}"
log "Conditions evaluated:"
for d in "$OUTPUT_BASE"/*/; do
    [[ "$(basename "$d")" == "logs" ]] && continue
    log "  $(basename "$d")"
done
