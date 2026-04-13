#!/bin/bash
# Multi-backbone experiment runner for CultureDx paper
# RTX 5090 (32GB) — optimized for maximum throughput
#
# Usage: bash scripts/run_multi_backbone.sh [--start MODEL_TAG]
#
# Runs Single + DtV V2+RAG for each backbone, then computes Table 4.
# Models are ordered small→large for fastest first results.

set -euo pipefail

PYTHON="uv run"
BASE_CFG="configs/base.yaml"
DATA_PATH="data/raw/lingxidiag16k"
DATASET="lingxidiag16k"
N=1000
OUTPUT_BASE="outputs/eval/backbone"
VLLM_PORT=8000
VLLM_URL="http://localhost:${VLLM_PORT}"

# Parse --start flag to resume from a specific model
START_TAG="${1:-}"
if [[ "$START_TAG" == "--start" ]]; then
    START_TAG="${2:-}"
fi
STARTED=false
if [[ -z "$START_TAG" ]]; then
    STARTED=true
fi

# ── Model definitions ─────────────────────────────────────────────────
# Format: TAG|HF_MODEL_ID|MAX_MODEL_LEN|MAX_CONCURRENT|EXTRA_VLLM_FLAGS
MODELS=(
    "qwen3-8b|Qwen/Qwen3-8B|8192|32|--dtype bfloat16"
    "qwen3-14b|Qwen/Qwen3-14B-AWQ|8192|24|"
    "qwen3-30b-a3b|stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ|4096|8|"
    "qwen3.5-27b|QuantTrio/Qwen3.5-27B-AWQ|4096|8|"
    "gemma3-27b|google/gemma-3-27b-it|4096|6|--dtype bfloat16"
    "qwen3-32b|Qwen/Qwen3-32B-AWQ|4096|16|"
)

# ── Helper functions ──────────────────────────────────────────────────
stop_vllm() {
    echo "[$(date +%H:%M)] Stopping vLLM..."
    pkill -f "vllm serve" 2>/dev/null || true
    sleep 3
    # Force kill if still running
    pkill -9 -f "vllm serve" 2>/dev/null || true
    sleep 2
}

start_vllm() {
    local model_id="$1"
    local max_model_len="$2"
    local extra_flags="$3"

    echo "[$(date +%H:%M)] Starting vLLM: ${model_id} (ctx=${max_model_len})"

    # Determine chat template flag based on model family
    local chat_tmpl_flag=""
    if [[ "$model_id" == *"Qwen3"* ]] || [[ "$model_id" == *"qwen3"* ]]; then
        chat_tmpl_flag="--override-generation-config '{}'"
    fi

    nohup vllm serve "$model_id" \
        --tensor-parallel-size 1 \
        --max-model-len "$max_model_len" \
        --gpu-memory-utilization 0.95 \
        --port "$VLLM_PORT" \
        --disable-log-requests \
        $extra_flags \
        > "${OUTPUT_BASE}/vllm_${model_id//\//_}.log" 2>&1 &

    # Wait for server to be ready
    echo -n "  Waiting for vLLM..."
    for i in $(seq 1 120); do
        if curl -s "${VLLM_URL}/v1/models" >/dev/null 2>&1; then
            echo " ready! (${i}s)"
            return 0
        fi
        sleep 2
        echo -n "."
    done
    echo " TIMEOUT after 240s!"
    return 1
}

run_config() {
    local tag="$1"
    local config_overlay="$2"
    local config_name="$3"
    local max_concurrent="$4"
    local out_dir="${OUTPUT_BASE}/${tag}_${config_name}_${N}"

    if [[ -f "${out_dir}/metrics.json" ]]; then
        echo "  [SKIP] ${out_dir} already exists"
        return 0
    fi

    echo "[$(date +%H:%M)] Running ${tag} / ${config_name} (N=${N}, concurrent=${max_concurrent})"

    # Create temp vllm config with correct model_id and concurrency
    local model_id
    model_id=$(curl -s "${VLLM_URL}/v1/models" | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['id'])")

    local tmp_vllm="/tmp/vllm_${tag}.yaml"
    cat > "$tmp_vllm" << VLLMEOF
llm:
  provider: vllm
  model_id: "${model_id}"
  base_url: ${VLLM_URL}
  temperature: 0.0
  top_k: 1
  max_retries: 3
  disable_thinking: true
  max_concurrent: ${max_concurrent}
VLLMEOF

    $PYTHON culturedx run \
        -c "$BASE_CFG" -c "$tmp_vllm" -c "$config_overlay" \
        -d "$DATASET" --data-path "$DATA_PATH" -n "$N" \
        -o "$out_dir" 2>&1 | tail -3

    # Compute Table 4 retroactively
    if [[ -f "${out_dir}/predictions.jsonl" ]]; then
        $PYTHON python scripts/compute_table4.py --run-dir "$out_dir" --data-path "$DATA_PATH" 2>&1 | tail -3
    fi

    rm -f "$tmp_vllm"
}

# ── Main loop ─────────────────────────────────────────────────────────
mkdir -p "$OUTPUT_BASE"

echo "============================================================"
echo "Multi-backbone experiment: ${#MODELS[@]} models × 2 configs"
echo "N=${N}, GPU=RTX 5090 32GB"
echo "Start: $(date)"
echo "============================================================"
echo ""

for entry in "${MODELS[@]}"; do
    IFS='|' read -r tag model_id max_model_len max_concurrent extra_flags <<< "$entry"

    # Skip until we reach the --start model
    if [[ "$STARTED" == "false" ]]; then
        if [[ "$tag" == "$START_TAG" ]]; then
            STARTED=true
        else
            echo "[SKIP] ${tag} (before --start ${START_TAG})"
            continue
        fi
    fi

    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  Model: ${tag} (${model_id})"
    echo "║  Context: ${max_model_len}, Concurrent: ${max_concurrent}"
    echo "╚══════════════════════════════════════════════════════════╝"

    stop_vllm
    if ! start_vllm "$model_id" "$max_model_len" "$extra_flags"; then
        echo "  [ERROR] Failed to start vLLM for ${tag}, skipping"
        continue
    fi

    # Run Single baseline
    run_config "$tag" "configs/single_baseline.yaml" "single" "$max_concurrent"

    # Run DtV V2 + RAG (paper config)
    run_config "$tag" "configs/v2.4_final.yaml" "dtv_v2_rag" "$max_concurrent"

    echo "[$(date +%H:%M)] ${tag} complete!"
done

# ── Restore primary model ─────────────────────────────────────────────
echo ""
echo "Restoring Qwen3-32B-AWQ as primary model..."
stop_vllm
start_vllm "Qwen/Qwen3-32B-AWQ" 4096 ""

echo ""
echo "============================================================"
echo "All backbones complete! $(date)"
echo "Results in: ${OUTPUT_BASE}/"
echo "============================================================"

# Print summary table
echo ""
echo "=== Results Summary ==="
python3 -c "
import json, os
base = '${OUTPUT_BASE}'
configs = ['single', 'dtv_v2_rag']
print(f'{'Model':<20} {'Config':<15} {'Top-1':>6} {'Top-3':>6} {'F1-m':>6} {'T4_Over':>8}')
print('-' * 65)
for d in sorted(os.listdir(base)):
    mf = os.path.join(base, d, 'metrics.json')
    if not os.path.exists(mf): continue
    with open(mf) as f:
        m = json.load(f)
    dx = m['diagnosis']
    t4 = m.get('table4', {})
    ov = t4.get('Overall', dx.get('overall', 0))
    parts = d.rsplit('_', 1)[0].rsplit('_', 1)  # tag_config
    print(f'{d:<20} {\"\":>15} {dx[\"top1_accuracy\"]:>6.3f} {dx[\"top3_accuracy\"]:>6.3f} {dx[\"macro_f1\"]:>6.3f} {ov:>8.4f}')
" 2>/dev/null || true
