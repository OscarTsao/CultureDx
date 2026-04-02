#!/usr/bin/env bash
# Remaining eval conditions — runs after priority eval completes
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

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "FATAL: $*"; exit 1; }

stop_vllm() {
    local pids
    pids=$(pgrep -f "vllm.entrypoints" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        log "Stopping existing vLLM processes: $pids"
        kill $pids 2>/dev/null || true
        sleep 5
        for p in $pids; do kill -0 "$p" 2>/dev/null && kill -9 "$p" 2>/dev/null || true; done
        sleep 2
    fi
}

start_vllm() {
    local model=$1
    local logfile="${LOG_DIR}/vllm_$(echo "$model" | tr '/' '_').log"
    if curl -fsS "${VLLM_URL}/health" > /dev/null 2>&1; then
        log "vLLM already healthy at ${VLLM_URL}"; return 0
    fi
    stop_vllm; sleep 3
    log "Starting vLLM with model: $model"
    nohup vllm serve "$model" --port "$VLLM_PORT" --tensor-parallel-size 1 \
        --max-model-len 16384 --gpu-memory-utilization 0.90 --dtype auto \
        > "$logfile" 2>&1 &
    local vllm_pid=$! timeout=600 elapsed=0
    while [[ $elapsed -lt $timeout ]]; do
        curl -fsS "${VLLM_URL}/health" > /dev/null 2>&1 && { log "vLLM healthy after ${elapsed}s"; return 0; }
        kill -0 "$vllm_pid" 2>/dev/null || die "vLLM died. Check $logfile"
        sleep 10; elapsed=$((elapsed + 10))
    done
    die "vLLM not healthy within ${timeout}s"
}

run_condition() {
    local name="$1" mode="$2" with_evidence="$3" with_somat="$4" thinking="$5"
    local variant="${6:-}" extra_yaml="${7:-}"
    local output_dir="${OUTPUT_BASE}/${name}" log_file="${LOG_DIR}/${name}.log"
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

    log "=== Condition: ${name} (mode=${mode}, ev=${with_evidence}, som=${with_somat}, think=${thinking}, var=${variant}) ==="
    if "${eval_args[@]}" 2>&1 | tee "$log_file"; then
        log "=== Done: ${name} ==="
    else
        log "=== WARNING: ${name} exited with errors (continuing) ==="
    fi
}

# ============================================================
log "===== REMAINING EVAL CONDITIONS ====="
start_vllm "$MODEL"

# HiED ablations
run_condition  "hied-evidence"           "hied"   "1"  "1"  "false"  ""
run_condition  "hied-no-somat"           "hied"   "1"  "0"  "false"  ""
run_condition  "hied-mock-evidence"      "hied"   "1"  "1"  "false"  "" "evidence:
  retriever:
    name: mock"
run_condition  "hied-evidence-rerank"    "hied"   "1"  "1"  "false"  "" "evidence:
  rerank_enabled: true
  rerank_top_n: 5"
run_condition  "hied-reasoning"          "hied"   "0"  "0"  "true"   ""
run_condition  "hied-reasoning-evidence" "hied"   "1"  "1"  "true"   ""
run_condition  "hied-cot"               "hied"   "0"  "0"  "false"  "cot"
run_condition  "hied-reasoning-cot"     "hied"   "0"  "0"  "true"   "cot"

# Other modes
run_condition  "psycot-evidence"        "psycot"  "1"  "1"  "false"  ""
run_condition  "psycot-reasoning-cot"   "psycot"  "1"  "1"  "true"   "cot"

stop_vllm
log "===== ALL CONDITIONS COMPLETE ====="
