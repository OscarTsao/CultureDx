#!/usr/bin/env bash
# Reasoning / Chain-of-Thought ablation experiment.
#
# Evaluates whether enabling Qwen3 native thinking mode and/or CoT prompts
# improves diagnostic accuracy compared to the baseline HiED pipeline.
#
# Conditions:
#   1. hied-baseline:        disable_thinking=true,  prompt_variant=""     (control)
#   2. hied-thinking:        disable_thinking=false, prompt_variant=""
#   3. hied-cot:             disable_thinking=true,  prompt_variant="cot"
#   4. hied-thinking-cot:    disable_thinking=false, prompt_variant="cot"
#   5. psycot-thinking-cot:  disable_thinking=false, prompt_variant="cot", mode=psycot
#
# Usage:
#   ./scripts/run_reasoning_eval.sh
#   MAX_CASES=100 ./scripts/run_reasoning_eval.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN=${PYTHON_BIN:-python3}
VLLM_BIN=${VLLM_BIN:-vllm}
MAX_CASES=${MAX_CASES:-200}
VLLM_PORT=${VLLM_PORT:-8000}
VLLM_URL=${VLLM_URL:-"http://localhost:${VLLM_PORT}"}
VLLM_HEALTH_URL="${VLLM_URL}/health"
VLLM_MODELS_URL="${VLLM_URL}/v1/models"
VLLM_MAX_MODEL_LEN=${VLLM_MAX_MODEL_LEN:-16384}
VLLM_GPU_MEMORY_UTILIZATION=${VLLM_GPU_MEMORY_UTILIZATION:-0.85}
VLLM_START_TIMEOUT=${VLLM_START_TIMEOUT:-900}
MODEL=${MODEL:-"Qwen/Qwen3-32B-AWQ"}
DATASETS=${DATASETS:-"lingxidiag,mdd5k"}
EVAL_SCRIPT=${EVAL_SCRIPT:-"scripts/run_full_eval.py"}
OUTPUT_BASE=${OUTPUT_BASE:-"outputs/eval/reasoning_ablation"}
LOG_DIR=${LOG_DIR:-"${OUTPUT_BASE}/logs"}
VLLM_LOG=${VLLM_LOG:-"${LOG_DIR}/vllm.log"}
BATCH_SIZE=${BATCH_SIZE:-50}
WITH_EVIDENCE=${WITH_EVIDENCE:-1}
WITH_SOMATIZATION=${WITH_SOMATIZATION:-1}

VLLM_STARTED_BY_SCRIPT=0
VLLM_PID=""

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
    log "ERROR: $*"
    exit 1
}

ensure_expected_model_hint() {
    local models_json
    if ! models_json="$(curl -fsS "${VLLM_MODELS_URL}" 2>/dev/null)"; then
        return 0
    fi
    if ! printf '%s' "$models_json" | grep -Fq "$MODEL"; then
        log "WARNING: vLLM is healthy at ${VLLM_URL}, but ${MODEL} was not listed by /v1/models."
    fi
}

cleanup() {
    if [[ "${VLLM_STARTED_BY_SCRIPT}" != "1" || -z "${VLLM_PID}" ]]; then
        return 0
    fi

    if kill -0 "${VLLM_PID}" 2>/dev/null; then
        log "Stopping vLLM PID ${VLLM_PID}"
        kill "${VLLM_PID}" 2>/dev/null || true
        wait "${VLLM_PID}" 2>/dev/null || true
    fi
}

trap cleanup EXIT

start_vllm() {
    mkdir -p "${LOG_DIR}" "${OUTPUT_BASE}"

    if curl -fsS "${VLLM_HEALTH_URL}" >/dev/null 2>&1; then
        log "Using existing vLLM at ${VLLM_URL}"
        ensure_expected_model_hint
        return 0
    fi

    command -v "${VLLM_BIN}" >/dev/null 2>&1 || die "vllm executable not found: ${VLLM_BIN}"

    log "Starting vLLM for ${MODEL} on port ${VLLM_PORT}"
    "${VLLM_BIN}" serve "${MODEL}" \
        --max-model-len "${VLLM_MAX_MODEL_LEN}" \
        --gpu-memory-utilization "${VLLM_GPU_MEMORY_UTILIZATION}" \
        --port "${VLLM_PORT}" \
        >"${VLLM_LOG}" 2>&1 &
    VLLM_PID=$!
    VLLM_STARTED_BY_SCRIPT=1

    local waited=0
    until curl -fsS "${VLLM_HEALTH_URL}" >/dev/null 2>&1; do
        if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
            die "vLLM exited before becoming healthy. See ${VLLM_LOG}"
        fi
        if (( waited >= VLLM_START_TIMEOUT )); then
            die "Timed out waiting for vLLM health after ${VLLM_START_TIMEOUT}s. See ${VLLM_LOG}"
        fi
        sleep 5
        waited=$((waited + 5))
    done

    log "vLLM is healthy at ${VLLM_URL}"
    ensure_expected_model_hint
}

run_condition() {
    local name="$1"
    local mode="$2"
    local thinking="$3"
    local variant="$4"
    local output_dir="${OUTPUT_BASE}/${name}"
    local log_file="${LOG_DIR}/${name}.log"
    local tmp_cfg
    local max_tokens
    local temperature
    local top_k
    local disable_thinking
    local -a config_args
    local -a eval_args

    mkdir -p "${output_dir}"
    tmp_cfg="$(mktemp "${TMPDIR:-/tmp}/culturedx_reasoning_XXXXXX.yaml")"

    if [[ "${thinking}" == "true" ]]; then
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

    cat > "${tmp_cfg}" <<YAML
llm:
  provider: vllm
  model_id: "${MODEL}"
  base_url: "${VLLM_URL}"
  temperature: ${temperature}
  top_k: ${top_k}
  disable_thinking: ${disable_thinking}
  max_tokens: ${max_tokens}
mode:
  name: ${mode}
  type: ${mode}
  prompt_variant: "${variant}"
YAML

    config_args=(
        --config configs/base.yaml
        --config "configs/${mode}.yaml"
        --config configs/vllm_awq.yaml
    )
    if [[ "${thinking}" == "true" ]]; then
        config_args+=(--config configs/reasoning.yaml)
    fi
    config_args+=(--config "${tmp_cfg}")

    eval_args=(
        "${PYTHON_BIN}" "${EVAL_SCRIPT}"
        "${config_args[@]}"
        --datasets "${DATASETS}"
        --modes "${mode}"
        --model-name "${MODEL}"
        --batch-size "${BATCH_SIZE}"
        --max-cases "${MAX_CASES}"
        --output-dir "${output_dir}"
    )
    if [[ "${WITH_EVIDENCE}" == "1" ]]; then
        eval_args+=(--with-evidence)
    fi
    if [[ "${WITH_EVIDENCE}" == "1" && "${WITH_SOMATIZATION}" == "1" ]]; then
        eval_args+=(--with-somatization)
    fi

    log "=== Condition: ${name} (mode=${mode}, thinking=${thinking}, variant=${variant}) ==="
    "${eval_args[@]}" 2>&1 | tee "${log_file}"
    rm -f "${tmp_cfg}"
    log "=== Done: ${name} ==="
}

generate_report() {
    local report_md="${OUTPUT_BASE}/comparison_report.md"
    local report_json="${OUTPUT_BASE}/comparison_report.json"

    "${PYTHON_BIN}" - "${OUTPUT_BASE}" "${MODEL}" "${MAX_CASES}" "${DATASETS}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

output_base = Path(sys.argv[1])
model = sys.argv[2]
max_cases = int(sys.argv[3])
datasets = [item.strip() for item in sys.argv[4].split(",") if item.strip()]

conditions = [
    {
        "slug": "hied-baseline",
        "label": "HiED baseline",
        "mode": "hied",
        "thinking": False,
        "prompt_variant": "",
    },
    {
        "slug": "hied-thinking",
        "label": "HiED + thinking",
        "mode": "hied",
        "thinking": True,
        "prompt_variant": "",
    },
    {
        "slug": "hied-cot",
        "label": "HiED + CoT",
        "mode": "hied",
        "thinking": False,
        "prompt_variant": "cot",
    },
    {
        "slug": "hied-thinking-cot",
        "label": "HiED + thinking + CoT",
        "mode": "hied",
        "thinking": True,
        "prompt_variant": "cot",
    },
    {
        "slug": "psycot-thinking-cot",
        "label": "PsyCoT + thinking + CoT",
        "mode": "psycot",
        "thinking": True,
        "prompt_variant": "cot",
    },
]


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def fmt(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return str(value)
    return f"{value:.4f}"


rows = []
for condition in conditions:
    overall = load_json(output_base / condition["slug"] / "metrics_overall.json")
    per_dataset = load_json(output_base / condition["slug"] / "metrics_per_dataset.json")
    global_metrics = overall.get("global", {})

    row = {
        **condition,
        "global": {
            "num_cases": global_metrics.get("num_cases"),
            "top1_accuracy": global_metrics.get("top1_accuracy"),
            "top3_accuracy": global_metrics.get("top3_accuracy"),
            "exact_match": global_metrics.get("exact_match"),
            "macro_f1": global_metrics.get("macro_f1"),
            "abstention_rate": global_metrics.get("abstention_rate"),
        },
        "datasets": {},
    }

    for dataset in datasets:
        key = f"{condition['mode']}:{dataset}"
        dataset_metrics = per_dataset.get(key, {})
        row["datasets"][dataset] = {
            "num_cases": dataset_metrics.get("num_cases"),
            "top1_accuracy": dataset_metrics.get("top1_accuracy"),
            "top3_accuracy": dataset_metrics.get("top3_accuracy"),
            "exact_match": dataset_metrics.get("exact_match"),
            "macro_f1": dataset_metrics.get("macro_f1"),
            "abstention_rate": dataset_metrics.get("abstention_rate"),
        }
    rows.append(row)

baseline_top1 = rows[0]["global"].get("top1_accuracy")
for row in rows:
    top1 = row["global"].get("top1_accuracy")
    if baseline_top1 is None or top1 is None:
        row["global"]["delta_top1_vs_baseline"] = None
    else:
        row["global"]["delta_top1_vs_baseline"] = top1 - baseline_top1

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "model": model,
    "max_cases_per_dataset": max_cases,
    "datasets": datasets,
    "conditions": rows,
}

(output_base / "comparison_report.json").write_text(
    json.dumps(payload, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

lines = [
    "# Reasoning Ablation Report",
    "",
    f"- Generated at: {payload['generated_at']}",
    f"- Model: {model}",
    f"- Datasets: {', '.join(datasets)}",
    f"- Max cases per dataset: {max_cases}",
    "",
    "## Overall Comparison",
    "",
    "| Condition | Mode | Thinking | Prompt Variant | Cases | Top-1 | Delta vs Baseline | Top-3 | Exact Match | Macro F1 | Abstain Rate |",
    "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
]

for row in rows:
    global_metrics = row["global"]
    lines.append(
        "| "
        f"{row['label']} | "
        f"{row['mode']} | "
        f"{'on' if row['thinking'] else 'off'} | "
        f"{row['prompt_variant'] or 'none'} | "
        f"{fmt(global_metrics.get('num_cases'))} | "
        f"{fmt(global_metrics.get('top1_accuracy'))} | "
        f"{fmt(global_metrics.get('delta_top1_vs_baseline'))} | "
        f"{fmt(global_metrics.get('top3_accuracy'))} | "
        f"{fmt(global_metrics.get('exact_match'))} | "
        f"{fmt(global_metrics.get('macro_f1'))} | "
        f"{fmt(global_metrics.get('abstention_rate'))} |"
    )

for dataset in datasets:
    lines.extend(
        [
            "",
            f"## Dataset: {dataset}",
            "",
            "| Condition | Cases | Top-1 | Top-3 | Exact Match | Macro F1 | Abstain Rate |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        dataset_metrics = row["datasets"].get(dataset, {})
        lines.append(
            "| "
            f"{row['label']} | "
            f"{fmt(dataset_metrics.get('num_cases'))} | "
            f"{fmt(dataset_metrics.get('top1_accuracy'))} | "
            f"{fmt(dataset_metrics.get('top3_accuracy'))} | "
            f"{fmt(dataset_metrics.get('exact_match'))} | "
            f"{fmt(dataset_metrics.get('macro_f1'))} | "
            f"{fmt(dataset_metrics.get('abstention_rate'))} |"
        )

(output_base / "comparison_report.md").write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8",
)
PY

    log "Comparison report written to ${report_md}"
    log "Comparison JSON written to ${report_json}"
}

start_vllm

log "Starting reasoning ablation (N=${MAX_CASES} per dataset)"

run_condition "hied-baseline" "hied" "false" ""
run_condition "hied-thinking" "hied" "true" ""
run_condition "hied-cot" "hied" "false" "cot"
run_condition "hied-thinking-cot" "hied" "true" "cot"
run_condition "psycot-thinking-cot" "psycot" "true" "cot"

generate_report

log "Reasoning ablation complete. Results: ${OUTPUT_BASE}"
