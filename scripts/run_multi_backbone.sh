#!/bin/bash
# Multi-backbone experiment runner for CultureDx paper.
#
# Usage:
#   bash scripts/run_multi_backbone.sh
#   bash scripts/run_multi_backbone.sh --start qwen3.5-27b
#
# Environment overrides:
#   N=32 OUTPUT_BASE=outputs/eval/backbone_smoke bash scripts/run_multi_backbone.sh
#
# Runs Single + DtV V2+RAG for each backbone sequentially. The launcher is
# resumable, retries fragile runs once, archives stale outputs, and writes a
# small JSON status file for monitoring.

set -euo pipefail

PYTHON="${PYTHON:-uv run}"
BASE_CFG="${BASE_CFG:-configs/base.yaml}"
DATA_PATH="${DATA_PATH:-data/raw/lingxidiag16k}"
DATASET="${DATASET:-lingxidiag16k}"
N="${N:-1000}"
OUTPUT_BASE="${OUTPUT_BASE:-outputs/eval/backbone}"
VLLM_BIN="${VLLM_BIN:-vllm}"
VLLM_PORT="${VLLM_PORT:-8000}"
VLLM_URL="http://localhost:${VLLM_PORT}"
RESTORE_PRIMARY="${RESTORE_PRIMARY:-1}"
RUN_LOG="${OUTPUT_BASE}/run.log"
STATUS_FILE="${OUTPUT_BASE}/status.json"

mkdir -p "$OUTPUT_BASE"

# Parse --start flag to resume from a specific model.
START_TAG="${1:-}"
if [[ "$START_TAG" == "--start" ]]; then
    START_TAG="${2:-}"
fi
STARTED=false
if [[ -z "$START_TAG" ]]; then
    STARTED=true
fi

# Format:
#   TAG|HF_MODEL_ID|MAX_MODEL_LEN|MAX_NUM_SEQS|SINGLE_MAX_TOKENS|DTV_MAX_TOKENS|EXTRA_VLLM_FLAGS
MODELS=(
    "qwen3-8b|Qwen/Qwen3-8B|8192|8|1536|1536|--dtype bfloat16"
    "qwen3-14b|Qwen/Qwen3-14B-AWQ|8192|8|1536|1536|"
    "qwen3-30b-a3b|stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ|4608|4|1536|1536|"
    "qwen3.5-9b|QuantTrio/Qwen3.5-9B-AWQ|8192|6|1536|1536|"
    "qwen3.5-27b|QuantTrio/Qwen3.5-27B-AWQ|4096|2|1536|1024|--enforce-eager"
    "gemma4-31b|QuantTrio/gemma-4-31B-it-AWQ|4096|1|1024|1024|--enforce-eager"
)

ACTIVE_TAG=""
ACTIVE_MODEL_ID=""
ACTIVE_CONTEXT_WINDOW=""
ACTIVE_MAX_NUM_SEQS=""
ACTIVE_EXTRA_FLAGS=""

write_status() {
    local state="$1"
    local tag="${2:-}"
    local config_name="${3:-}"
    local message="${4:-}"
    python3 - "$STATUS_FILE" "$state" "$tag" "$config_name" "$message" <<'PY'
import json
import sys
from datetime import datetime, timezone

path, state, tag, config_name, message = sys.argv[1:6]
payload = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "state": state,
    "model": tag or None,
    "config": config_name or None,
    "message": message or None,
}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
PY
}

stop_vllm() {
    echo "[$(date +%H:%M)] Stopping vLLM..." | tee -a "$RUN_LOG"
    pkill -f "vllm" 2>/dev/null || true
    pkill -f "VLLM::" 2>/dev/null || true
    sleep 3
    pkill -9 -f "vllm" 2>/dev/null || true
    pkill -9 -f "VLLM::" 2>/dev/null || true
    sleep 2
    fuser -k "${VLLM_PORT}/tcp" 2>/dev/null || true
    sleep 1
}

start_vllm() {
    local model_id="$1"
    local max_model_len="$2"
    local max_num_seqs="$3"
    local extra_flags="$4"

    echo "[$(date +%H:%M)] Starting vLLM: ${model_id} (ctx=${max_model_len}, max_num_seqs=${max_num_seqs})" | tee -a "$RUN_LOG"

    nohup env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$VLLM_BIN" serve "$model_id" \
        --tensor-parallel-size 1 \
        --max-model-len "$max_model_len" \
        --max-num-seqs "$max_num_seqs" \
        --gpu-memory-utilization 0.85 \
        --generation-config vllm \
        --port "$VLLM_PORT" \
        $extra_flags \
        > "${OUTPUT_BASE}/vllm_${model_id//\//_}.log" 2>&1 &

    echo -n "  Waiting for vLLM..." | tee -a "$RUN_LOG"
    for i in $(seq 1 120); do
        if curl -fsS "${VLLM_URL}/health" >/dev/null 2>&1 && \
           curl -fsS "${VLLM_URL}/v1/models" | python3 -c "import json,sys; data=json.load(sys.stdin); sys.exit(0 if data.get('data') else 1)" >/dev/null 2>&1; then
            echo " ready! (${i}s)" | tee -a "$RUN_LOG"
            return 0
        fi
        sleep 2
        echo -n "." | tee -a "$RUN_LOG"
    done

    echo " TIMEOUT after 240s!" | tee -a "$RUN_LOG"
    return 1
}

start_vllm_with_fallback() {
    local model_id="$1"
    local max_model_len="$2"
    local requested_max_num_seqs="$3"
    local extra_flags="$4"
    local try_max_num_seqs="$requested_max_num_seqs"
    local try_flags="$extra_flags"

    while true; do
        write_status "starting_vllm" "$ACTIVE_TAG" "" "ctx=${max_model_len}, max_num_seqs=${try_max_num_seqs}"
        if start_vllm "$model_id" "$max_model_len" "$try_max_num_seqs" "$try_flags"; then
            ACTIVE_MAX_NUM_SEQS="$try_max_num_seqs"
            ACTIVE_EXTRA_FLAGS="$try_flags"
            return 0
        fi

        stop_vllm

        if (( try_max_num_seqs > 1 )); then
            try_max_num_seqs=$(( (try_max_num_seqs + 1) / 2 ))
            echo "  [RETRY] ${model_id} with max_num_seqs=${try_max_num_seqs}" | tee -a "$RUN_LOG"
            continue
        fi

        if [[ "$try_flags" != *"--enforce-eager"* ]]; then
            try_flags="${try_flags} --enforce-eager"
            echo "  [RETRY] ${model_id} with --enforce-eager" | tee -a "$RUN_LOG"
            continue
        fi

        return 1
    done
}

served_model_id() {
    local fallback_model_id="$1"
    local served
    if served=$(curl -fsS "${VLLM_URL}/v1/models" | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null); then
        printf '%s\n' "$served"
    else
        printf '%s\n' "$fallback_model_id"
    fi
}

run_is_complete() {
    local out_dir="$1"
    python3 - "$out_dir" "$N" <<'PY'
import json
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
expected = int(sys.argv[2])
metrics_path = out_dir / "metrics.json"
predictions_path = out_dir / "predictions.jsonl"
if not metrics_path.exists() or not predictions_path.exists():
    raise SystemExit(1)

with open(predictions_path, "r", encoding="utf-8") as fh:
    prediction_count = sum(1 for _ in fh)
if prediction_count != expected:
    raise SystemExit(2)

summary_path = out_dir / "metrics_summary.json"
payload_path = summary_path if summary_path.exists() else metrics_path
with open(payload_path, "r", encoding="utf-8") as fh:
    payload = json.load(fh)
metrics = payload.get("metrics", payload)
slice_metrics = payload.get("slice_metrics", [])

if slice_metrics and all(float(item.get("abstention_rate", 0.0)) >= 0.999 for item in slice_metrics):
    raise SystemExit(3)

diagnosis = metrics.get("diagnosis", {})
table4 = metrics.get("table4", {})
if (
    float(table4.get("Overall", 1.0)) <= 0.08
    and float(diagnosis.get("top1_accuracy", 1.0)) <= 0.095
    and float(diagnosis.get("top3_accuracy", 1.0)) <= 0.095
):
    raise SystemExit(4)
PY
}

archive_stale_run() {
    local out_dir="$1"
    local reason="$2"
    local ts
    ts="$(date +%Y%m%d_%H%M%S)"
    local archived="${out_dir}.stale_${ts}"
    echo "  [RESET] Archiving ${out_dir} -> ${archived} (${reason})" | tee -a "$RUN_LOG"
    mv "$out_dir" "$archived"
}

run_config() {
    local tag="$1"
    local config_overlay="$2"
    local config_name="$3"
    local max_concurrent="$4"
    local max_tokens="$5"
    local fallback_model_id="$6"
    local context_window="$7"
    local out_dir="${OUTPUT_BASE}/${tag}_${config_name}_${N}"
    local launcher_log="${out_dir}/launcher_tail.log"

    if [[ -d "$out_dir" ]]; then
        if run_is_complete "$out_dir"; then
            echo "  [SKIP] ${out_dir} already has valid metrics" | tee -a "$RUN_LOG"
            write_status "skipped" "$tag" "$config_name" "valid existing run"
            return 0
        fi
        archive_stale_run "$out_dir" "partial_or_invalid"
    fi
    mkdir -p "$out_dir"

    echo "[$(date +%H:%M)] Running ${tag} / ${config_name} (N=${N}, concurrent=${max_concurrent}, max_tokens=${max_tokens})" | tee -a "$RUN_LOG"
    write_status "running" "$tag" "$config_name" "concurrent=${max_concurrent}, max_tokens=${max_tokens}"

    local model_id
    model_id=$(served_model_id "$fallback_model_id")
    local tmp_vllm="/tmp/vllm_${tag}.yaml"
    cat > "$tmp_vllm" <<VLLMEOF
llm:
  provider: vllm
  model_id: "${model_id}"
  base_url: ${VLLM_URL}
  temperature: 0.0
  top_k: 1
  context_window: ${context_window}
  max_tokens: ${max_tokens}
  max_retries: 3
  disable_thinking: true
  max_concurrent: ${max_concurrent}
VLLMEOF

    local attempt
    for attempt in 1 2; do
        if [[ "$attempt" -gt 1 ]]; then
            echo "  [RETRY] ${tag}/${config_name} attempt ${attempt} after server restart" | tee -a "$RUN_LOG"
            write_status "retrying" "$tag" "$config_name" "attempt=${attempt}"
            stop_vllm
            if ! start_vllm "$fallback_model_id" "$context_window" "$ACTIVE_MAX_NUM_SEQS" "$ACTIVE_EXTRA_FLAGS"; then
                echo "  [ERROR] Could not restart vLLM for retry" | tee -a "$RUN_LOG"
                rm -f "$tmp_vllm"
                write_status "failed" "$tag" "$config_name" "server restart failed"
                return 1
            fi
            model_id=$(served_model_id "$fallback_model_id")
            cat > "$tmp_vllm" <<VLLMEOF
llm:
  provider: vllm
  model_id: "${model_id}"
  base_url: ${VLLM_URL}
  temperature: 0.0
  top_k: 1
  context_window: ${context_window}
  max_tokens: ${max_tokens}
  max_retries: 3
  disable_thinking: true
  max_concurrent: ${max_concurrent}
VLLMEOF
        fi

        if $PYTHON culturedx run \
            -c "$BASE_CFG" -c "$config_overlay" -c "$tmp_vllm" \
            -d "$DATASET" --data-path "$DATA_PATH" -n "$N" \
            -o "$out_dir" 2>&1 | tee "$launcher_log" | tail -3; then
            if run_is_complete "$out_dir"; then
                break
            fi
            echo "  [WARN] ${tag}/${config_name} produced incomplete or degenerate artifacts" | tee -a "$RUN_LOG"
        else
            echo "  [WARN] culturedx run failed for ${tag}/${config_name} (attempt ${attempt})" | tee -a "$RUN_LOG"
        fi

        if [[ "$attempt" -eq 1 ]]; then
            archive_stale_run "$out_dir" "retry_after_failed_attempt"
            mkdir -p "$out_dir"
        else
            echo "  [ERROR] ${tag}/${config_name} failed after retry" | tee -a "$RUN_LOG"
            write_status "failed" "$tag" "$config_name" "run failed after retry"
            rm -f "$tmp_vllm"
            return 1
        fi
    done

    if [[ -f "${out_dir}/predictions.jsonl" ]]; then
        $PYTHON python scripts/compute_table4.py --run-dir "$out_dir" --data-path "$DATA_PATH" 2>&1 | tail -3 || true
    else
        echo "  [WARN] ${out_dir} has no predictions.jsonl" | tee -a "$RUN_LOG"
    fi

    rm -f "$tmp_vllm"
    write_status "completed" "$tag" "$config_name" "artifacts ready"
}

cleanup() {
    write_status "stopped" "$ACTIVE_TAG" "" "launcher exited"
}
trap cleanup EXIT

echo "============================================================" | tee -a "$RUN_LOG"
echo "Multi-backbone experiment: ${#MODELS[@]} models × 2 configs" | tee -a "$RUN_LOG"
echo "N=${N}, GPU=RTX 5090 32GB" | tee -a "$RUN_LOG"
echo "Start: $(date)" | tee -a "$RUN_LOG"
echo "Output base: ${OUTPUT_BASE}" | tee -a "$RUN_LOG"
echo "============================================================" | tee -a "$RUN_LOG"
echo "" | tee -a "$RUN_LOG"
write_status "starting" "" "" "launcher booted"

for entry in "${MODELS[@]}"; do
    IFS='|' read -r tag model_id max_model_len max_num_seqs single_max_tokens dtv_max_tokens extra_flags <<< "$entry"

    if [[ "$STARTED" == "false" ]]; then
        if [[ "$tag" == "$START_TAG" ]]; then
            STARTED=true
        else
            echo "[SKIP] ${tag} (before --start ${START_TAG})" | tee -a "$RUN_LOG"
            continue
        fi
    fi

    ACTIVE_TAG="$tag"
    ACTIVE_MODEL_ID="$model_id"
    ACTIVE_CONTEXT_WINDOW="$max_model_len"

    echo "" | tee -a "$RUN_LOG"
    echo "╔══════════════════════════════════════════════════════════╗" | tee -a "$RUN_LOG"
    echo "║  Model: ${tag} (${model_id})" | tee -a "$RUN_LOG"
    echo "║  Context: ${max_model_len}, Concurrent: ${max_num_seqs}, SingleMax: ${single_max_tokens}, DtVMax: ${dtv_max_tokens}" | tee -a "$RUN_LOG"
    echo "╚══════════════════════════════════════════════════════════╝" | tee -a "$RUN_LOG"

    write_status "model_start" "$tag" "" "ctx=${max_model_len}, max_num_seqs=${max_num_seqs}"
    stop_vllm
    if ! start_vllm_with_fallback "$model_id" "$max_model_len" "$max_num_seqs" "$extra_flags"; then
        echo "  [ERROR] Failed to start vLLM for ${tag}, skipping" | tee -a "$RUN_LOG"
        write_status "failed" "$tag" "" "vllm startup failed"
        continue
    fi

    run_config "$tag" "configs/single_baseline.yaml" "single" "$max_num_seqs" "$single_max_tokens" "$model_id" "$max_model_len" || true
    run_config "$tag" "configs/v2.4_final.yaml" "dtv_v2_rag" "$max_num_seqs" "$dtv_max_tokens" "$model_id" "$max_model_len" || true

    echo "[$(date +%H:%M)] ${tag} complete!" | tee -a "$RUN_LOG"
    write_status "model_complete" "$tag" "" "single+dtv finished"
done

if [[ "$RESTORE_PRIMARY" == "1" ]]; then
    echo "" | tee -a "$RUN_LOG"
    echo "Restoring Qwen3-32B-AWQ as primary model..." | tee -a "$RUN_LOG"
    write_status "restoring_primary" "" "" "restoring Qwen/Qwen3-32B-AWQ"
    stop_vllm
    start_vllm "Qwen/Qwen3-32B-AWQ" 4096 16 "" || true
fi

echo "" | tee -a "$RUN_LOG"
echo "============================================================" | tee -a "$RUN_LOG"
echo "All backbones complete! $(date)" | tee -a "$RUN_LOG"
echo "Results in: ${OUTPUT_BASE}/" | tee -a "$RUN_LOG"
echo "============================================================" | tee -a "$RUN_LOG"
write_status "all_complete" "" "" "all configured backbones processed"

echo "" | tee -a "$RUN_LOG"
echo "=== Results Summary ===" | tee -a "$RUN_LOG"
python3 - "$OUTPUT_BASE" <<'PY' 2>/dev/null || true
import json
import os
import sys

base = sys.argv[1]
print(f"{'Model':<20} {'Config':<15} {'Top-1':>6} {'Top-3':>6} {'F1-m':>6} {'T4_Over':>8}")
print("-" * 65)
for name in sorted(os.listdir(base)):
    metrics_path = os.path.join(base, name, "metrics.json")
    if not os.path.exists(metrics_path):
        continue
    with open(metrics_path, "r", encoding="utf-8") as fh:
        metrics = json.load(fh)
    diagnosis = metrics["diagnosis"]
    table4 = metrics.get("table4", {})
    overall = table4.get("Overall", diagnosis.get("overall", 0.0))
    if name.endswith(f"_{os.environ.get('N', '1000')}"):
        stem = name[: -(len(os.environ.get('N', '1000')) + 1)]
    else:
        stem = name
    if "_dtv_v2_rag" in stem:
        model, config = stem.split("_dtv_v2_rag", 1)
        config = "dtv_v2_rag"
    elif stem.endswith("_single"):
        model = stem[: -len("_single")]
        config = "single"
    else:
        model = stem
        config = ""
    print(f"{model:<20} {config:<15} {diagnosis['top1_accuracy']:>6.3f} {diagnosis['top3_accuracy']:>6.3f} {diagnosis['macro_f1']:>6.3f} {overall:>8.4f}")
PY
