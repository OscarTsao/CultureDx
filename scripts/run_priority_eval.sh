#!/usr/bin/env bash
# Priority evaluation: hied-baseline (resume), single-baseline, hied-full-pipeline
#
# Usage:
#   nohup ./scripts/run_priority_eval.sh > outputs/eval/priority.log 2>&1 &

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN=${PYTHON_BIN:-python3}
VLLM_PORT=${VLLM_PORT:-8000}
VLLM_URL="http://localhost:${VLLM_PORT}"
MODEL=${MODEL:-"Qwen/Qwen3-32B-AWQ"}
DATASETS=${DATASETS:-"lingxidiag"}
EVAL_SCRIPT="scripts/run_full_eval.py"
BATCH_SIZE=${BATCH_SIZE:-100}
OUTPUT_BASE=${OUTPUT_BASE:-"outputs/eval/hied_first_20260401_182240"}
LOG_DIR="${OUTPUT_BASE}/logs"

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

    local tmp_cfg="${output_dir}/eval_config.yaml"

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
}

# ============================================================
# Priority runs: baseline -> single -> full-pipeline
# ============================================================
log "===== PRIORITY EVAL: 3 conditions ====="
start_vllm "$MODEL"

# 1. Finish hied-baseline (resumes from ~276 completed)
run_condition  "hied-baseline"       "hied"   "0"  "0"  "false"  ""

# 2. Single baseline (fast — ~1h 15m)
run_condition  "single-baseline"     "single" "0"  "0"  "false"  ""

# 3. HiED full pipeline (thinking + cot + evidence + somatization)
run_condition  "hied-full-pipeline"  "hied"   "1"  "1"  "true"   "cot"

# Cleanup
stop_vllm
log "===== PRIORITY EVAL COMPLETE ====="
log "Results directory: ${OUTPUT_BASE}"
for d in "$OUTPUT_BASE"/*/; do
    [[ "$(basename "$d")" == "logs" ]] && continue
    log "  $(basename "$d")"
done

# ============================================================
# Remaining conditions (queued after priority 3)
# ============================================================
log "===== REMAINING CONDITIONS ====="

# HiED ablations
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

# Other modes
run_condition  "psycot-evidence"       "psycot" "1"    "1"    "false"  ""
run_condition  "psycot-reasoning-cot"  "psycot" "1"    "1"    "true"   "cot"

log "===== ALL CONDITIONS COMPLETE ====="
