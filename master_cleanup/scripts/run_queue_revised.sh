#!/bin/bash
# run_queue_revised.sh — Final 7-run queue (28 GPU hr)
#
# Based on whole-repo review findings:
#   - R17 dropped: low yield + needs code change
#   - R19 dropped: baseline already has no triage (scope_policy=manual)
#   - R11/R12 dropped: impossible at temperature=0.0
#
# All patches from master_cleanup/ must be applied first:
#   fix_cli_seed.patch, fix_test_triage.patch, r16_bypass_logic_engine.patch

set -e

REPO_ROOT="${REPO_ROOT:-$(pwd)}"
cd "$REPO_ROOT"
export PYTHONUNBUFFERED=1

mkdir -p outputs/queue_logs

# Helper for smoke test + full run pattern
smoke_and_full() {
    local name="$1"
    shift
    local configs=("$@")
    local cfg_args=()
    for c in "${configs[@]}"; do
        cfg_args+=("-c" "$c")
    done

    echo "========================================================"
    echo "$name starting at $(date)"
    echo "========================================================"

    # 20-case smoke
    uv run culturedx run \
        "${cfg_args[@]}" \
        -d lingxidiag16k --data-path data/raw/lingxidiag16k \
        -n 20 --run-name "${name}_smoke" \
        2>&1 | tee "outputs/queue_logs/${name}_smoke.log"

    # Verify smoke produced sensible output
    if [ ! -s "results/validation/${name}_smoke/predictions.jsonl" ]; then
        echo "FATAL: smoke test produced no predictions for $name"
        return 1
    fi

    local pred_count=$(wc -l < "results/validation/${name}_smoke/predictions.jsonl")
    echo "Smoke test produced $pred_count predictions (expected 20)"

    # Full 1000-case
    uv run culturedx run \
        "${cfg_args[@]}" \
        -d lingxidiag16k --data-path data/raw/lingxidiag16k \
        -n 1000 --run-name "$name" \
        2>&1 | tee "outputs/queue_logs/${name}_full.log"

    echo "$name completed at $(date)"
    echo ""
}

# =========================================
# Verify vLLM is running Qwen3-32B-AWQ
# =========================================
if ! curl -s http://localhost:8000/v1/models >/dev/null 2>&1; then
    echo "ERROR: vLLM server not responding on :8000"
    echo "Start with: vllm serve Qwen/Qwen3-32B-AWQ --port 8000 \\"
    echo "              --max-model-len 32768 --gpu-memory-utilization 0.88 &"
    exit 1
fi

MODEL_ID=$(curl -s http://localhost:8000/v1/models | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d['data'][0]['id'])
" 2>/dev/null)
echo "Current vLLM model: $MODEL_ID"

# =========================================
# Phase 1 — No code changes needed (16 GPU hr)
# =========================================

echo "### Phase 1: Prompt and config experiments ###"

# R6' — somatization + stress detection combined
smoke_and_full "r6_combined" \
    configs/base.yaml \
    configs/vllm_awq.yaml \
    configs/v2.4_final.yaml \
    configs/overlays/r6_combined.yaml

# R7 — triage top-5 -> top-8
smoke_and_full "r7_triage_top8" \
    configs/base.yaml \
    configs/vllm_awq.yaml \
    configs/v2.4_final.yaml \
    configs/overlays/r7_triage_top8.yaml

# R20 — NOS diagnostician variant
smoke_and_full "r20_nos_variant" \
    configs/base.yaml \
    configs/vllm_awq.yaml \
    configs/v2.4_final.yaml \
    configs/overlays/r20_nos_variant.yaml

# R21 — Evidence stacked (uses --with-evidence flag)
echo "========================================================"
echo "r21_evidence_stacked starting at $(date)"
echo "========================================================"
uv run culturedx run \
    -c configs/base.yaml \
    -c configs/vllm_awq.yaml \
    -c configs/v2.4_final.yaml \
    -c configs/overlays/r21_evidence_stacked.yaml \
    --with-evidence \
    -d lingxidiag16k --data-path data/raw/lingxidiag16k \
    -n 20 --run-name r21_evidence_smoke \
    2>&1 | tee outputs/queue_logs/r21_smoke.log

uv run culturedx run \
    -c configs/base.yaml \
    -c configs/vllm_awq.yaml \
    -c configs/v2.4_final.yaml \
    -c configs/overlays/r21_evidence_stacked.yaml \
    --with-evidence \
    -d lingxidiag16k --data-path data/raw/lingxidiag16k \
    -n 1000 --run-name r21_evidence_stacked \
    2>&1 | tee outputs/queue_logs/r21_full.log

echo "r21_evidence_stacked completed at $(date)"
echo ""

# =========================================
# Phase 2 — R16 (requires r16_bypass_logic_engine.patch applied)
# =========================================

echo "### Phase 2: Architecture ablation ###"
echo "IMPORTANT: Verify r16_bypass_logic_engine.patch was applied to hied.py"
read -p "Has the patch been applied? [y/N] " response
if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
    smoke_and_full "r16_bypass_logic" \
        configs/base.yaml \
        configs/vllm_awq.yaml \
        configs/v2.4_final.yaml \
        configs/overlays/r16_bypass_logic_engine.yaml
else
    echo "Skipping R16 until patch is applied."
fi

# =========================================
# Phase 3 — Backbone swaps (requires vLLM restart)
# =========================================

echo ""
echo "### Phase 3: Backbone bias diagnosis ###"
echo ""
echo "To run R13 (Qwen3-8B):"
echo "  1. Stop current vLLM: pkill -f vllm"
echo "  2. Start Qwen3-8B: vllm serve Qwen/Qwen3-8B-Instruct \\"
echo "         --port 8000 --max-model-len 32768 --gpu-memory-utilization 0.88 &"
echo "  3. Wait ~60s for server"
echo ""
read -p "Is Qwen3-8B running? [y/N] " response
if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
    smoke_and_full "r13_qwen3_8b" \
        configs/base.yaml \
        configs/vllm_qwen3_8b.yaml \
        configs/v2.4_final.yaml
else
    echo "Skipping R13."
fi

echo ""
echo "To run R14 (non-Qwen, e.g., Qwen2.5-32B-Instruct-AWQ or DeepSeek-V3):"
echo "  1. Edit configs/overlays/r14_non_qwen.yaml with your chosen model"
echo "  2. Stop current vLLM and start the chosen model"
echo ""
read -p "Is R14 model running and config updated? [y/N] " response
if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
    R14_MODEL_ID=$(curl -s http://localhost:8000/v1/models | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d['data'][0]['id'])
" 2>/dev/null)
    R14_RUN_NAME=$(echo "$R14_MODEL_ID" | tr '/' '_' | tr '[:upper:]' '[:lower:]')
    R14_RUN_NAME="r14_${R14_RUN_NAME}"

    smoke_and_full "$R14_RUN_NAME" \
        configs/base.yaml \
        configs/v2.4_final.yaml \
        configs/overlays/r14_non_qwen.yaml
else
    echo "Skipping R14."
fi

echo ""
echo "========================================================"
echo "Queue complete at $(date)"
echo "========================================================"
echo ""
echo "Next steps:"
echo "  1. Run post_hoc_analyze_all.sh to apply Stage 2-5 + oracle analysis"
echo "  2. Commit results:"
echo "     git add results/validation/r*/"
echo "     git commit -m 'data: revised 7-run queue results'"
echo "  3. Bundle metrics for analysis:"
echo "     tar czf ~/queue_results.tar.gz \\"
echo "       results/validation/r6_*/metrics.json \\"
echo "       results/validation/r7_*/metrics.json \\"
echo "       results/validation/r13_*/metrics.json \\"
echo "       results/validation/r14_*/metrics.json \\"
echo "       results/validation/r16_*/metrics.json \\"
echo "       results/validation/r20_*/metrics.json \\"
echo "       results/validation/r21_*/metrics.json \\"
echo "       results/validation/*_final/metrics_combined.json"
