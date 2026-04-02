#!/usr/bin/env bash
# Paper-aligned LingxiDiag eval — OPTIMIZED: best system + baselines first
#
# Usage:
#   nohup ./scripts/run_paper_aligned_eval.sh > outputs/eval/paper_aligned.log 2>&1 &

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
OUTPUT_BASE=${OUTPUT_BASE:-"outputs/eval/paper_aligned_$(date +%Y%m%d_%H%M%S)"}
LOG_DIR="${OUTPUT_BASE}/logs"

mkdir -p "$LOG_DIR"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
    log "FATAL: $*"
    exit 1
}

start_vllm() {
    local model=$1
    local logfile="${LOG_DIR}/vllm_$(echo "$model" | tr '/' '_').log"
    if curl -fsS "${VLLM_URL}/health" > /dev/null 2>&1; then
        log "vLLM already healthy"; return 0
    fi
    local pids; pids=$(pgrep -f "vllm.entrypoints" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        kill $pids 2>/dev/null || true; sleep 5
        for p in $pids; do kill -9 "$p" 2>/dev/null || true; done; sleep 2
    fi
    log "Starting vLLM: $model"
    nohup vllm serve "$model" --port "$VLLM_PORT" --tensor-parallel-size 1 \
        --max-model-len 16384 --gpu-memory-utilization 0.90 --dtype auto \
        > "$logfile" 2>&1 &
    local vllm_pid=$! elapsed=0
    while [[ $elapsed -lt 600 ]]; do
        curl -fsS "${VLLM_URL}/health" > /dev/null 2>&1 && { log "vLLM healthy after ${elapsed}s"; return 0; }
        kill -0 "$vllm_pid" 2>/dev/null || die "vLLM died"
        sleep 10; elapsed=$((elapsed + 10))
    done
    die "vLLM timeout"
}

run_condition() {
    local name="$1" mode="$2" with_evidence="$3" with_somat="$4" thinking="$5"
    local variant="${6:-}" extra_yaml="${7:-}"
    local output_dir="${OUTPUT_BASE}/${name}"
    local log_file="${LOG_DIR}/${name}.log"
    mkdir -p "$output_dir"

    local tmp_cfg="${output_dir}/eval_config.yaml"
    local max_tokens temperature top_k disable_thinking
    if [[ "$thinking" == "true" ]]; then
        max_tokens=4096; temperature=0.6; top_k=20; disable_thinking=false
    else
        max_tokens=2048; temperature=0.0; top_k=1; disable_thinking=true
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
  max_concurrent: 48
mode:
  name: ${mode}
  type: ${mode}
  prompt_variant: "${variant}"
YAML

    [[ -n "$extra_yaml" ]] && printf '\n%s\n' "$extra_yaml" >> "$tmp_cfg"

    local -a config_args=(--config configs/base.yaml)
    [[ -f "configs/${mode}.yaml" ]] && config_args+=(--config "configs/${mode}.yaml")
    config_args+=(--config configs/vllm_awq.yaml --config configs/targets/lingxidiag_12class.yaml)
    [[ "$with_evidence" == "1" ]] && config_args+=(--config configs/evidence.yaml)
    [[ "$thinking" == "true" ]] && config_args+=(--config configs/reasoning.yaml)
    config_args+=(--config "$tmp_cfg")

    local -a eval_args=(
        "$PYTHON_BIN" "$EVAL_SCRIPT" "${config_args[@]}"
        --datasets "$DATASETS" --modes "$mode" --model-name "$MODEL"
        --batch-size "$BATCH_SIZE" --output-dir "$output_dir"
        --split validation --force-prediction --resume
    )
    [[ "$with_evidence" == "1" ]] && eval_args+=(--with-evidence)
    [[ "$with_evidence" == "1" && "$with_somat" == "1" ]] && eval_args+=(--with-somatization)

    log "=== START: ${name} (mode=${mode}, evi=${with_evidence}, somat=${with_somat}, think=${thinking}) ==="
    if "${eval_args[@]}" 2>&1 | tee "$log_file"; then
        log "=== DONE: ${name} ==="
    else
        log "=== WARN: ${name} exited with errors ==="
    fi
}

# ============================================================
log "===== PAPER-ALIGNED EVAL (optimized, best-first) ====="
log "7 conditions, 13 disorders, validation=test, force-prediction, 16 cases in-flight"
log "Output: ${OUTPUT_BASE}"
start_vllm "$MODEL"

# --- Phase 1: Best system + baselines (first results in ~20min) ---
run_condition  "single-baseline"     "single" "0"  "0"  "false"  ""
run_condition  "hied-full-pipeline"  "hied"   "1"  "1"  "true"   "cot"
run_condition  "hied-baseline"       "hied"   "0"  "0"  "false"  ""

# --- Phase 2: Ablations ---
run_condition  "hied-cot"           "hied"   "0"  "0"  "false"  "cot"
run_condition  "hied-evidence"       "hied"   "1"  "1"  "false"  ""
run_condition  "hied-no-somat"       "hied"   "1"  "0"  "false"  ""
run_condition  "psycot-evidence"     "psycot" "1"  "1"  "false"  ""

log "===== ALL 7 CONDITIONS COMPLETE ====="
log "Results: ${OUTPUT_BASE}"
for d in "$OUTPUT_BASE"/*/; do
    [[ "$(basename "$d")" == "logs" ]] && continue
    cnt=$(wc -l < "$d/results_lingxidiag.jsonl" 2>/dev/null || echo 0)
    log "  $(basename "$d"): ${cnt} results"
done
