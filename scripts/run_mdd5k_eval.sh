#!/usr/bin/env bash
# MDD-5k backfill: all 13 conditions on mdd5k dataset
# Evidence conditions now use BGE-M3 on CPU (no CUDA OOM)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN=${PYTHON_BIN:-python3}
VLLM_PORT=${VLLM_PORT:-8000}
VLLM_URL="http://localhost:${VLLM_PORT}"
MODEL=${MODEL:-"Qwen/Qwen3-32B-AWQ"}
DATASETS="mdd5k"
EVAL_SCRIPT="scripts/run_full_eval.py"
BATCH_SIZE=${BATCH_SIZE:-100}
OUTPUT_BASE=${OUTPUT_BASE:-"outputs/eval/mdd5k_20260402"}
LOG_DIR="${OUTPUT_BASE}/logs"

mkdir -p "$LOG_DIR"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

start_vllm() {
    local model=$1
    if curl -fsS "${VLLM_URL}/health" > /dev/null 2>&1; then
        log "vLLM already healthy at ${VLLM_URL}"; return 0
    fi
    log "ERROR: vLLM not running at ${VLLM_URL}"; exit 1
}

run_condition() {
    local name="$1" mode="$2" with_evidence="$3" with_somat="$4" thinking="$5"
    local variant="${6:-}" extra_yaml="${7:-}"
    local output_dir="${OUTPUT_BASE}/${name}"
    local log_file="${LOG_DIR}/${name}-mdd5k.log"
    mkdir -p "$output_dir"

    local tmp_cfg="${output_dir}/eval_config_mdd5k.yaml"
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
  max_concurrent: 32
mode:
  name: ${mode}
  type: ${mode}
  prompt_variant: "${variant}"
YAML
    [[ -n "$extra_yaml" ]] && printf '\n%s\n' "$extra_yaml" >> "$tmp_cfg"

    local -a config_args=(--config configs/base.yaml)
    [[ -f "configs/${mode}.yaml" ]] && config_args+=(--config "configs/${mode}.yaml")
    config_args+=(--config configs/vllm_awq.yaml)
    [[ "$with_evidence" == "1" ]] && config_args+=(--config configs/evidence.yaml)
    [[ "$thinking" == "true" ]] && config_args+=(--config configs/reasoning.yaml)
    config_args+=(--config "$tmp_cfg")

    local -a eval_args=(
        "$PYTHON_BIN" "$EVAL_SCRIPT" "${config_args[@]}"
        --datasets "$DATASETS" --modes "$mode" --model-name "$MODEL"
        --batch-size "$BATCH_SIZE" --output-dir "$output_dir" --split validation --resume
    )
    [[ "$with_evidence" == "1" ]] && eval_args+=(--with-evidence)
    [[ "$with_evidence" == "1" && "$with_somat" == "1" ]] && eval_args+=(--with-somatization)

    log "=== Condition: ${name} mdd5k (mode=${mode}, ev=${with_evidence}, som=${with_somat}, think=${thinking}) ==="
    if "${eval_args[@]}" 2>&1 | tee "$log_file"; then
        log "=== Done: ${name} mdd5k ==="
    else
        log "=== WARNING: ${name} mdd5k exited with errors (continuing) ==="
    fi
}

log "===== MDD-5K BACKFILL: 13 conditions ====="
start_vllm "$MODEL"

# Priority 3
run_condition  "hied-baseline"       "hied"   "0"  "0"  "false"  ""
run_condition  "single-baseline"     "single" "0"  "0"  "false"  ""
run_condition  "hied-full-pipeline"  "hied"   "1"  "1"  "true"   "cot"

# HiED ablations
run_condition  "hied-evidence"          "hied"  "1"  "1"  "false"  ""
run_condition  "hied-no-somat"          "hied"  "1"  "0"  "false"  ""
run_condition  "hied-mock-evidence"     "hied"  "1"  "1"  "false"  "" "evidence:
  retriever:
    name: mock"
run_condition  "hied-evidence-rerank"   "hied"  "1"  "1"  "false"  "" "evidence:
  rerank_enabled: true
  rerank_top_n: 5"
run_condition  "hied-reasoning"         "hied"  "0"  "0"  "true"   ""
run_condition  "hied-reasoning-evidence" "hied" "1"  "1"  "true"   ""
run_condition  "hied-cot"              "hied"  "0"  "0"  "false"  "cot"
run_condition  "hied-reasoning-cot"    "hied"  "0"  "0"  "true"   "cot"

# Other modes
run_condition  "psycot-evidence"       "psycot" "1"  "1"  "false"  ""
run_condition  "psycot-reasoning-cot"  "psycot" "1"  "1"  "true"   "cot"

log "===== MDD-5K BACKFILL COMPLETE ====="
