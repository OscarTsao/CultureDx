#!/usr/bin/env bash
# Auto-chain teacher data generation -> QLoRA finetune -> full evaluation.
#
# Usage:
#   TEACHER_PID=65479 ./scripts/auto_chain.sh
#
# Notes:
# - `run_full_eval.py` does not load LoRA adapters itself. `--adapter-path` is
#   provenance-only, so this script can optionally start an eval server via
#   `EVAL_SERVER_CMD`.
# - Example manual vLLM launch:
#     vllm serve Qwen/Qwen3-32B-AWQ --max-model-len 16384 --gpu-memory-utilization 0.85 --port 8000
# - Current vLLM docs support both AWQ quantization and Qwen3 MoE serving, but
#   the QuantTrio Qwen3.5 AWQ model card recommends a current/nightly vLLM build.
# - For Qwen3.5-35B-A3B-AWQ (MoE, ~20GB VRAM):
#     vllm serve QuantTrio/Qwen3.5-35B-A3B-AWQ --max-model-len 16384 --gpu-memory-utilization 0.85 --port 8000
# - `EVAL_SERVER_CMD` runs under `bash -lc` with these exported variables:
#     BEST_CHECKPOINT
#     BEST_ADAPTER_DIR
#     EVAL_ADAPTER_PATH
#     MODEL_NAME
#     EVAL_MODEL_NAME
#     VLLM_PORT

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# -----------------------------
# Configurable variables
# -----------------------------
PYTHON_BIN=${PYTHON_BIN:-python3}

TEACHER_PID=${TEACHER_PID:-65479}
TEACHER_DIR=${TEACHER_DIR:-"data/sft/teacher_v1"}
TEACHER_LOG=${TEACHER_LOG:-"outputs/finetune/teacher_generation.log"}
TEACHER_EXPECTED_PROMPTS=${TEACHER_EXPECTED_PROMPTS:-5000}
POLL_SECONDS=${POLL_SECONDS:-60}

TRAIN_FILE=${TRAIN_FILE:-"$TEACHER_DIR/criterion_checker_train.jsonl"}
VAL_FILE=${VAL_FILE:-"$TEACHER_DIR/criterion_checker_val.jsonl"}
MODEL_NAME=${MODEL_NAME:-"Qwen/Qwen3-8B"}

FINETUNE_SCRIPT=${FINETUNE_SCRIPT:-"scripts/finetune_checker.py"}
FINETUNE_OUTPUT_DIR=${FINETUNE_OUTPUT_DIR:-"outputs/finetune/qwen3_8b_teacher_v1"}
FINETUNE_LOG=${FINETUNE_LOG:-"outputs/finetune/qwen3_8b_finetune.log"}
FINETUNE_HELP_LOG=${FINETUNE_HELP_LOG:-"outputs/finetune/finetune_checker_help.txt"}
FINETUNE_EPOCHS=${FINETUNE_EPOCHS:-3}
FINETUNE_BATCH_SIZE=${FINETUNE_BATCH_SIZE:-4}
FINETUNE_GRAD_ACCUM=${FINETUNE_GRAD_ACCUM:-4}
FINETUNE_LR=${FINETUNE_LR:-"2e-4"}
FINETUNE_LORA_R=${FINETUNE_LORA_R:-16}
FINETUNE_LORA_ALPHA=${FINETUNE_LORA_ALPHA:-32}
FINETUNE_MAX_LENGTH=${FINETUNE_MAX_LENGTH:-8192}
FINETUNE_BF16=${FINETUNE_BF16:-1}
FINETUNE_LOAD_IN_4BIT=${FINETUNE_LOAD_IN_4BIT:-1}

VLLM_PORT=${VLLM_PORT:-8000}
VLLM_HEALTH_URL=${VLLM_HEALTH_URL:-"http://localhost:${VLLM_PORT}/health"}
VLLM_STOP_WAIT_SECONDS=${VLLM_STOP_WAIT_SECONDS:-10}

RUN_FULL_EVAL_SCRIPT=${RUN_FULL_EVAL_SCRIPT:-"scripts/run_full_eval.py"}
EVAL_CONFIGS=${EVAL_CONFIGS:-"configs/base.yaml,configs/vllm_awq.yaml"}
EVAL_DATASETS=${EVAL_DATASETS:-"lingxidiag,mdd5k"}
EVAL_MODES=${EVAL_MODES:-"hied,single"}
EVAL_WITH_EVIDENCE=${EVAL_WITH_EVIDENCE:-1}
EVAL_WITH_SOMATIZATION=${EVAL_WITH_SOMATIZATION:-1}
EVAL_BATCH_SIZE=${EVAL_BATCH_SIZE:-50}
EVAL_OUTPUT_DIR=${EVAL_OUTPUT_DIR:-"outputs/eval/full_qwen3_8b_v1"}
EVAL_LOG=${EVAL_LOG:-"outputs/eval/full_eval.log"}
EVAL_MODELS=${EVAL_MODELS:-"Qwen/Qwen3-32B-AWQ QuantTrio/Qwen3.5-35B-A3B-AWQ"}
EVAL_MODEL_NAME=${EVAL_MODEL_NAME:-"$MODEL_NAME"}
EVAL_ADAPTER_PATH=${EVAL_ADAPTER_PATH:-""}
EVAL_SERVER_CMD=${EVAL_SERVER_CMD:-""}
EVAL_SERVER_LOG=${EVAL_SERVER_LOG:-"outputs/eval/eval_model_server.log"}
EVAL_SERVER_READY_TIMEOUT=${EVAL_SERVER_READY_TIMEOUT:-600}
FORCE_RESTART_EVAL_SERVER=${FORCE_RESTART_EVAL_SERVER:-0}

ACTIVE_EVAL_MODEL_NAME=""
ACTIVE_EVAL_ADAPTER_PATH=""
CURRENT_EVAL_OUTPUT_DIR="$EVAL_OUTPUT_DIR"
CURRENT_EVAL_LOG="$EVAL_LOG"
CURRENT_EVAL_SERVER_LOG="$EVAL_SERVER_LOG"


log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}


die() {
    log "ERROR: $*"
    exit 1
}


model_slug() {
    local value="$1"
    value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
    value="$(printf '%s' "$value" | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g')"
    printf '%s\n' "${value:-model}"
}


eval_run_slug() {
    local model_name="$1"
    local adapter_path="${2:-}"
    local slug
    slug="$(model_slug "$model_name")"
    if [[ -n "$adapter_path" ]]; then
        slug="${slug}-adapter"
    fi
    printf '%s\n' "$slug"
}


path_with_suffix() {
    local path="$1"
    local suffix="$2"
    local dir
    local file
    local stem
    local ext=""

    dir="$(dirname "$path")"
    file="$(basename "$path")"
    if [[ "$file" == *.* && "$file" != .* ]]; then
        stem="${file%.*}"
        ext=".${file##*.}"
    else
        stem="$file"
    fi
    printf '%s/%s_%s%s\n' "$dir" "$stem" "$suffix" "$ext"
}


configure_eval_paths() {
    local model_name="$1"
    local adapter_path="${2:-}"
    local run_slug
    run_slug="$(eval_run_slug "$model_name" "$adapter_path")"
    CURRENT_EVAL_OUTPUT_DIR="${EVAL_OUTPUT_DIR}/${run_slug}"
    CURRENT_EVAL_LOG="$(path_with_suffix "$EVAL_LOG" "$run_slug")"
    CURRENT_EVAL_SERVER_LOG="$(path_with_suffix "$EVAL_SERVER_LOG" "$run_slug")"
}


require_file() {
    local path="$1"
    [[ -f "$path" ]] || die "Required file not found: $path"
}


teacher_progress_count() {
    grep -c 'HTTP/1.1 200 OK' "$TEACHER_LOG" 2>/dev/null || echo "0"
}


collect_vllm_pids() {
    {
        pgrep -f "vllm serve" || true
        pgrep -f "vllm.entrypoints.openai.api_server" || true
    } | awk '!seen[$0]++'
}


wait_for_teacher_generation() {
    log "Waiting for teacher data generation (PID $TEACHER_PID)..."
    if kill -0 "$TEACHER_PID" 2>/dev/null; then
        while kill -0 "$TEACHER_PID" 2>/dev/null; do
            local count
            count="$(teacher_progress_count)"
            log "Teacher gen: ${count}/${TEACHER_EXPECTED_PROMPTS} prompts completed"
            sleep "$POLL_SECONDS"
        done
    else
        log "Teacher PID $TEACHER_PID is not running; proceeding to output validation."
    fi
    log "Teacher gen complete!"
}


verify_teacher_output() {
    require_file "$TRAIN_FILE"
    require_file "$VAL_FILE"

    local train_count
    local val_count
    train_count="$(wc -l < "$TRAIN_FILE")"
    val_count="$(wc -l < "$VAL_FILE")"

    if [[ "$train_count" -eq 0 ]]; then
        die "Teacher train file is empty: $TRAIN_FILE"
    fi
    if [[ "$val_count" -eq 0 ]]; then
        die "Teacher val file is empty: $VAL_FILE"
    fi

    log "Teacher data: ${train_count} training examples, ${val_count} validation examples"
}


stop_vllm() {
    log "Stopping vLLM..."

    local pids=()
    mapfile -t pids < <(collect_vllm_pids)

    if [[ "${#pids[@]}" -eq 0 ]]; then
        log "No vLLM process found."
    else
        log "Stopping vLLM PID(s): ${pids[*]}"
        kill "${pids[@]}" 2>/dev/null || true
        sleep "$VLLM_STOP_WAIT_SECONDS"

        local remaining=()
        mapfile -t remaining < <(collect_vllm_pids)
        if [[ "${#remaining[@]}" -ne 0 ]]; then
            die "vLLM still running after ${VLLM_STOP_WAIT_SECONDS}s: ${remaining[*]}"
        fi
    fi

    if command -v nvidia-smi >/dev/null 2>&1; then
        log "GPU memory used after stop:"
        nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits || true
    fi
}


verify_finetune_cli() {
    require_file "$FINETUNE_SCRIPT"
    mkdir -p "$(dirname "$FINETUNE_HELP_LOG")"

    log "Verifying finetune script CLI..."
    "$PYTHON_BIN" "$FINETUNE_SCRIPT" --help 2>&1 | head -20 | tee "$FINETUNE_HELP_LOG"
}


run_finetune() {
    mkdir -p "$(dirname "$FINETUNE_LOG")" "$FINETUNE_OUTPUT_DIR"

    local -a cmd=(
        "$PYTHON_BIN" "$FINETUNE_SCRIPT"
        --model-name "$MODEL_NAME"
        --train-file "$TRAIN_FILE"
        --val-file "$VAL_FILE"
        --output-dir "$FINETUNE_OUTPUT_DIR"
        --epochs "$FINETUNE_EPOCHS"
        --batch-size "$FINETUNE_BATCH_SIZE"
        --gradient-accumulation-steps "$FINETUNE_GRAD_ACCUM"
        --lr "$FINETUNE_LR"
        --lora-r "$FINETUNE_LORA_R"
        --lora-alpha "$FINETUNE_LORA_ALPHA"
        --max-length "$FINETUNE_MAX_LENGTH"
    )

    if [[ "$FINETUNE_BF16" == "1" ]]; then
        cmd+=(--bf16)
    fi
    if [[ "$FINETUNE_LOAD_IN_4BIT" == "1" ]]; then
        cmd+=(--load-in-4bit)
    fi

    local cmd_str
    printf -v cmd_str '%q ' "${cmd[@]}"
    log "Starting finetune:"
    log "$cmd_str"
    "${cmd[@]}" 2>&1 | tee "$FINETUNE_LOG"
}


find_best_checkpoint() {
    local trainer_state="$FINETUNE_OUTPUT_DIR/trainer_state.json"
    if [[ -f "$trainer_state" ]]; then
        local trainer_best
        trainer_best="$("$PYTHON_BIN" - "$trainer_state" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    payload = json.load(handle)

value = payload.get("best_model_checkpoint")
if value:
    print(value)
PY
)"
        if [[ -n "$trainer_best" ]]; then
            printf '%s\n' "$trainer_best"
            return
        fi
    fi

    find "$FINETUNE_OUTPUT_DIR" -maxdepth 1 -type d -name 'checkpoint-*' -printf '%T@ %p\n' \
        | sort -nr \
        | awk 'NR == 1 { print $2 }'
}


wait_for_eval_server() {
    local launcher_pid="$1"
    local server_log="${CURRENT_EVAL_SERVER_LOG:-$EVAL_SERVER_LOG}"
    local start_ts
    start_ts="$(date +%s)"

    while true; do
        if curl -fsS "$VLLM_HEALTH_URL" >/dev/null 2>&1; then
            log "Eval server is healthy at $VLLM_HEALTH_URL"
            return 0
        fi
        if ! kill -0 "$launcher_pid" 2>/dev/null; then
            die "Eval server launcher exited before health check passed. See $server_log"
        fi
        if (( $(date +%s) - start_ts >= EVAL_SERVER_READY_TIMEOUT )); then
            die "Eval server did not become healthy within ${EVAL_SERVER_READY_TIMEOUT}s. See $server_log"
        fi
        sleep 5
    done
}


ensure_eval_server() {
    if [[ "$FORCE_RESTART_EVAL_SERVER" == "1" ]]; then
        stop_vllm
    fi

    if curl -fsS "$VLLM_HEALTH_URL" >/dev/null 2>&1; then
        log "Eval server already running at $VLLM_HEALTH_URL"
        return 0
    fi

    if [[ -z "$EVAL_SERVER_CMD" ]]; then
        die "No eval server is running and EVAL_SERVER_CMD is empty. run_full_eval.py cannot load the LoRA adapter itself."
    fi

    local server_log="${CURRENT_EVAL_SERVER_LOG:-$EVAL_SERVER_LOG}"
    mkdir -p "$(dirname "$server_log")"
    log "Starting eval server with EVAL_SERVER_CMD..."
    log "$EVAL_SERVER_CMD"

    BEST_CHECKPOINT="${BEST_CHECKPOINT:-}" \
    BEST_ADAPTER_DIR="${BEST_ADAPTER_DIR:-}" \
    EVAL_ADAPTER_PATH="${EVAL_ADAPTER_PATH:-}" \
    MODEL_NAME="$MODEL_NAME" \
    EVAL_MODEL_NAME="$EVAL_MODEL_NAME" \
    VLLM_PORT="$VLLM_PORT" \
    bash -lc "$EVAL_SERVER_CMD" >"$server_log" 2>&1 &

    local launcher_pid=$!
    log "Eval server launcher PID: $launcher_pid"
    wait_for_eval_server "$launcher_pid"
}


prepare_eval_server_for_target() {
    local target_model="$1"
    local target_adapter="${2:-}"

    EVAL_MODEL_NAME="$target_model"
    EVAL_ADAPTER_PATH="$target_adapter"

    if [[ "$FORCE_RESTART_EVAL_SERVER" == "1" ]]; then
        ACTIVE_EVAL_MODEL_NAME=""
        ACTIVE_EVAL_ADAPTER_PATH=""
    fi

    if [[ -n "$EVAL_SERVER_CMD" ]]; then
        if [[ "$ACTIVE_EVAL_MODEL_NAME" != "$target_model" || "$ACTIVE_EVAL_ADAPTER_PATH" != "$target_adapter" ]]; then
            if curl -fsS "$VLLM_HEALTH_URL" >/dev/null 2>&1; then
                log "Restarting eval server for model: $target_model"
                stop_vllm
            fi
        fi
    elif [[ -n "$ACTIVE_EVAL_MODEL_NAME" && "$ACTIVE_EVAL_MODEL_NAME" != "$target_model" ]] \
        || [[ -n "$ACTIVE_EVAL_MODEL_NAME" && "$ACTIVE_EVAL_ADAPTER_PATH" != "$target_adapter" ]]; then
        log "Eval target changed to $target_model, but EVAL_SERVER_CMD is empty. Ensure the server at $VLLM_HEALTH_URL is serving the requested model."
    fi

    ensure_eval_server
    ACTIVE_EVAL_MODEL_NAME="$target_model"
    ACTIVE_EVAL_ADAPTER_PATH="$target_adapter"
}


run_full_eval() {
    require_file "$RUN_FULL_EVAL_SCRIPT"
    local output_dir="${CURRENT_EVAL_OUTPUT_DIR:-$EVAL_OUTPUT_DIR}"
    local eval_log="${CURRENT_EVAL_LOG:-$EVAL_LOG}"
    mkdir -p "$(dirname "$eval_log")" "$output_dir"

    local -a eval_config_args=()
    local -a eval_configs=()
    IFS=',' read -r -a eval_configs <<< "$EVAL_CONFIGS"
    for cfg in "${eval_configs[@]}"; do
        cfg="${cfg#"${cfg%%[![:space:]]*}"}"
        cfg="${cfg%"${cfg##*[![:space:]]}"}"
        [[ -n "$cfg" ]] || continue
        eval_config_args+=(--config "$cfg")
    done
    if [[ "${#eval_config_args[@]}" -eq 0 ]]; then
        die "EVAL_CONFIGS resolved to no config paths."
    fi

    local -a cmd=(
        "$PYTHON_BIN" "$RUN_FULL_EVAL_SCRIPT"
        "${eval_config_args[@]}"
        --datasets "$EVAL_DATASETS"
        --modes "$EVAL_MODES"
        --model-name "$EVAL_MODEL_NAME"
        --batch-size "$EVAL_BATCH_SIZE"
        --output-dir "$output_dir"
    )
    if [[ -n "$EVAL_ADAPTER_PATH" ]]; then
        cmd+=(--adapter-path "$EVAL_ADAPTER_PATH")
    fi

    if [[ "$EVAL_WITH_EVIDENCE" == "1" ]]; then
        cmd+=(--with-evidence)
    fi
    if [[ "$EVAL_WITH_EVIDENCE" == "1" && "$EVAL_WITH_SOMATIZATION" == "1" ]]; then
        cmd+=(--with-somatization)
    fi

    local cmd_str
    printf -v cmd_str '%q ' "${cmd[@]}"
    log "Starting full eval:"
    log "$cmd_str"
    "${cmd[@]}" 2>&1 | tee "$eval_log"
}


run_eval_for_target() {
    local target_model="$1"
    local target_adapter="${2:-}"
    local label="$3"

    configure_eval_paths "$target_model" "$target_adapter"
    log "${label}: model=${target_model} adapter=${target_adapter:-none}"
    log "Eval output dir: $CURRENT_EVAL_OUTPUT_DIR"
    prepare_eval_server_for_target "$target_model" "$target_adapter"
    run_full_eval
}


run_reference_model_evals() {
    local eval_model
    for eval_model in $EVAL_MODELS; do
        run_eval_for_target "$eval_model" "" "Reference eval"
    done
}


run_finetuned_model_eval() {
    run_eval_for_target "$EVAL_MODEL_NAME" "$EVAL_ADAPTER_PATH" "Finetuned eval"
}


main() {
    wait_for_teacher_generation
    verify_teacher_output
    stop_vllm
    verify_finetune_cli
    run_finetune

    BEST_CHECKPOINT="$(find_best_checkpoint)"
    BEST_ADAPTER_DIR="$FINETUNE_OUTPUT_DIR"
    if [[ -z "$EVAL_ADAPTER_PATH" ]]; then
        if [[ -n "$BEST_CHECKPOINT" ]]; then
            EVAL_ADAPTER_PATH="$BEST_CHECKPOINT"
        else
            EVAL_ADAPTER_PATH="$BEST_ADAPTER_DIR"
        fi
    fi

    if [[ -n "$BEST_CHECKPOINT" ]]; then
        log "Best checkpoint: $BEST_CHECKPOINT"
    else
        log "No checkpoint directory found; using exported adapter dir: $BEST_ADAPTER_DIR"
    fi
    log "Eval adapter provenance path: $EVAL_ADAPTER_PATH"

    export BEST_CHECKPOINT
    export BEST_ADAPTER_DIR
    export EVAL_ADAPTER_PATH

    run_reference_model_evals
    run_finetuned_model_eval

    echo "=========================================="
    echo "AUTO-CHAIN COMPLETE"
    echo "Teacher data: $TEACHER_DIR"
    echo "Finetune: $FINETUNE_OUTPUT_DIR"
    echo "Eval: $EVAL_OUTPUT_DIR"
    echo "=========================================="
}


main "$@"
