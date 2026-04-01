#!/usr/bin/env python3
"""Full-scale evaluation runner for CultureDx.

Runs one or more modes across the full LingxiDiag-16K and/or MDD-5k datasets
with batched checkpointing, resume support, mapped-code evaluation, and a
single consolidated report.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import shutil
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BOOTSTRAP_ENV = "CULTUREDX_FULL_EVAL_BOOTSTRAPPED"
if os.environ.get(BOOTSTRAP_ENV) != "1":
    try:
        import omegaconf  # noqa: F401
    except ModuleNotFoundError:
        uv_bin = shutil.which("uv")
        if uv_bin is not None:
            os.environ[BOOTSTRAP_ENV] = "1"
            os.execvp(
                uv_bin,
                [uv_bin, "run", "python3", os.path.abspath(sys.argv[0]), *sys.argv[1:]],
            )
        raise

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from culturedx.core.config import CultureDxConfig, load_config
from culturedx.core.models import ClinicalCase
from culturedx.data.adapters import get_adapter
from culturedx.eval.code_mapping import (
    AMBIGUOUS_MAP,
    EXCLUDED_CODES,
    is_correct_prediction,
    map_dataset_code,
)
from culturedx.eval.metrics import compute_comorbidity_metrics, compute_diagnosis_metrics
from culturedx.pipeline.artifacts import (
    build_failure_records,
    build_prediction_record,
    build_stage_timing_records,
    serialize_dataclass,
    stable_fingerprint,
)
from culturedx.pipeline.cli import _create_configured_llm
from culturedx.pipeline.runner import ExperimentRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("run_full_eval")

DEFAULT_DATASET_PATHS: dict[str, str] = {
    "lingxidiag": "data/raw/lingxidiag16k",
    "lingxidiag16k": "data/raw/lingxidiag16k",
    "mdd5k": "data/raw/mdd5k_repo",
}

DATASET_ALIASES: dict[str, str] = {
    "lingxidiag": "lingxidiag",
    "lingxidiag16k": "lingxidiag",
    "mdd5k": "mdd5k",
}

CHILD_TO_BUCKET = {
    child_code: parent_code
    for parent_code, child_codes in AMBIGUOUS_MAP.items()
    for child_code in child_codes
}

class ResumableExperimentRunner(ExperimentRunner):
    """ExperimentRunner variant that supports batch extraction without file writes."""

    def _save_predictions(self, case_contexts: list[dict[str, Any]]) -> None:
        """Suppress the default whole-run artifact writes for batch execution."""
        return None

    def run_batch(
        self,
        cases: list[ClinicalCase],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Run a batch and return successful contexts plus per-case exceptions."""
        if not cases:
            self._last_case_contexts = []
            return [], []

        results: list[dict[str, Any] | None] = [None] * len(cases)
        errors: list[dict[str, Any] | None] = [None] * len(cases)

        def _process_one(idx: int, case: ClinicalCase) -> tuple[int, dict[str, Any] | None, dict[str, Any] | None]:
            try:
                evidence = None
                evidence_start = time.monotonic()
                if self.evidence_pipeline is not None:
                    evidence = self.evidence_pipeline.extract(case)
                    if "total" not in evidence.stage_timings:
                        evidence.stage_timings["total"] = time.monotonic() - evidence_start

                diagnosis_start = time.monotonic()
                result = self.mode.diagnose(case, evidence=evidence)
                result.stage_timings.setdefault(
                    "diagnosis_total",
                    time.monotonic() - diagnosis_start,
                )
                context = {
                    "batch_index": idx,
                    "case": case,
                    "evidence": evidence,
                    "result": result,
                }
                return idx, context, None
            except Exception as exc:  # pragma: no cover - exercised by real failures
                return idx, None, {
                    "case_id": case.case_id,
                    "dataset": case.dataset,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }

        if self.max_cases_in_flight <= 1 or len(cases) == 1:
            for idx, case in enumerate(cases):
                out_idx, context, error = _process_one(idx, case)
                results[out_idx] = context
                errors[out_idx] = error
        else:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(
                max_workers=min(self.max_cases_in_flight, len(cases))
            ) as executor:
                futures = {
                    executor.submit(_process_one, idx, case): idx
                    for idx, case in enumerate(cases)
                }
                for future in as_completed(futures):
                    out_idx, context, error = future.result()
                    results[out_idx] = context
                    errors[out_idx] = error

        final_contexts = [context for context in results if context is not None]
        final_errors = [error for error in errors if error is not None]
        self._last_case_contexts = final_contexts
        return final_contexts, final_errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CultureDx full-scale evaluation runner")
    parser.add_argument(
        "--config",
        action="append",
        required=True,
        help="Base config YAML path. Repeat to apply overlays in order.",
    )
    parser.add_argument(
        "--datasets",
        required=True,
        help="Comma-separated datasets: lingxidiag,mdd5k",
    )
    parser.add_argument(
        "--modes",
        default="hied,single",
        help="Comma-separated modes: hied,single,psycot,mas,specialist,debate",
    )
    parser.add_argument(
        "--model-name",
        default=None,
        help=(
            "Override cfg.llm.model_id. Accepts one model ID or a comma-separated "
            "list to run sequentially with separate output directories."
        ),
    )
    parser.add_argument(
        "--adapter-path",
        default=None,
        help="Optional fine-tune adapter path recorded for provenance; current clients must already serve the adapted model.",
    )
    parser.add_argument("--with-evidence", action="store_true", help="Enable evidence pipeline")
    parser.add_argument(
        "--with-somatization",
        action="store_true",
        help="Enable somatization mapping when evidence is enabled",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Cases per progress/checkpoint batch",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=0,
        help="Maximum evaluable cases per dataset after filtering; 0 means all",
    )
    parser.add_argument("--output-dir", required=True, help="Evaluation output directory")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint/output files")
    parser.add_argument("--dry-run", action="store_true", help="Count cases and plan the run without executing inference")
    return parser.parse_args()


def load_culturedx_config(config_paths: list[str]) -> CultureDxConfig:
    base_path = config_paths[0]
    overrides = config_paths[1:] or None
    return load_config(base_path, overrides=overrides)


def normalize_name_list(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def normalize_model_name_list(raw_value: str | None, default_model: str) -> list[str]:
    raw_models = normalize_name_list(raw_value) if raw_value else [default_model]
    deduped_models: list[str] = []
    seen: set[str] = set()
    for model_name in raw_models:
        if model_name in seen:
            continue
        seen.add(model_name)
        deduped_models.append(model_name)
    return deduped_models or [default_model]


def sanitize_model_name_for_path(model_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", model_name.strip().lower()).strip("-")
    return slug or "model"


def resolve_model_output_dir(
    base_output_dir: Path,
    model_names: list[str],
    model_name: str,
) -> Path:
    if len(model_names) == 1:
        return base_output_dir
    return base_output_dir / sanitize_model_name_for_path(model_name)


def sanitize_for_json(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(k): sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_for_json(item) for item in value]
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(sanitize_for_json(payload), handle, indent=2, ensure_ascii=False)


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(sanitize_for_json(row), ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.0f}m"
    hours = int(minutes // 60)
    rem_minutes = int(round(minutes % 60))
    return f"{hours}h {rem_minutes}m"


def safe_rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def resolve_dataset_spec(dataset_name: str, cfg: CultureDxConfig) -> dict[str, Any]:
    requested = dataset_name.strip().lower()
    if requested not in DATASET_ALIASES:
        supported = ", ".join(sorted(DATASET_ALIASES))
        raise ValueError(f"Unsupported dataset '{dataset_name}'. Expected one of: {supported}")

    output_name = DATASET_ALIASES[requested]
    configured_name = (cfg.dataset.name or "").strip().lower()
    configured_path = (cfg.dataset.data_path or "").strip()
    use_configured_path = configured_path and configured_name in {"", requested, output_name}
    data_path = configured_path if use_configured_path else DEFAULT_DATASET_PATHS[requested]

    if output_name == "lingxidiag":
        return {
            "requested_name": dataset_name,
            "output_name": "lingxidiag",
            "adapter_name": "lingxidiag16k",
            "data_path": data_path,
            "split": "train",
        }

    data_path_obj = Path(data_path)
    adapter_name = "mdd5k" if data_path_obj.suffix.lower() == ".json" else "mdd5k_raw"
    return {
        "requested_name": dataset_name,
        "output_name": "mdd5k",
        "adapter_name": adapter_name,
        "data_path": data_path,
        "split": None,
    }


def clone_eval_config(
    cfg: CultureDxConfig,
    mode_name: str,
    model_name: str | None,
    with_evidence: bool,
    with_somatization: bool,
) -> CultureDxConfig:
    run_cfg = cfg.model_copy(deep=True)
    run_cfg.mode.name = mode_name
    run_cfg.mode.type = mode_name
    run_cfg.evidence.enabled = with_evidence
    run_cfg.evidence.somatization.enabled = with_evidence and with_somatization
    if model_name:
        run_cfg.llm.model_id = model_name
        if run_cfg.checker_llm is not None:
            run_cfg.checker_llm.model_id = model_name
    return run_cfg


def create_mode(cfg: CultureDxConfig):
    llm = _create_configured_llm(cfg, cfg.llm)
    checker_llm = _create_configured_llm(cfg, cfg.checker_llm) if cfg.checker_llm else None

    mode_type = cfg.mode.type
    if mode_type == "hied":
        from culturedx.modes.hied import HiEDMode

        mode_kwargs = dict(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
            scope_policy=cfg.mode.scope_policy,
            execution_mode=cfg.mode.execution_mode,
            contrastive_enabled=cfg.mode.contrastive_enabled,
            comorbid_min_ratio=cfg.mode.comorbid_min_ratio,
        )
        if checker_llm is not None:
            mode_kwargs["checker_llm_client"] = checker_llm
        mode = HiEDMode(**mode_kwargs)
    elif mode_type == "psycot":
        from culturedx.modes.psycot import PsyCoTMode

        mode_kwargs = dict(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
            comorbid_min_ratio=cfg.mode.comorbid_min_ratio,
        )
        if checker_llm is not None:
            mode_kwargs["checker_llm_client"] = checker_llm
        mode = PsyCoTMode(**mode_kwargs)
    elif mode_type == "mas":
        from culturedx.modes.mas import MASMode

        mode = MASMode(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
        )
    elif mode_type == "specialist":
        from culturedx.modes.specialist import SpecialistMode

        mode = SpecialistMode(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
        )
    elif mode_type == "debate":
        from culturedx.modes.debate import DebateMode

        mode = DebateMode(llm_client=llm)
    elif mode_type == "single":
        from culturedx.modes.single import SingleModelMode

        mode = SingleModelMode(llm_client=llm)
    else:
        llm.close()
        if checker_llm is not None and checker_llm is not llm:
            checker_llm.close()
        raise ValueError(f"Unsupported mode '{mode_type}'")

    return mode, llm, checker_llm


def create_evidence_pipeline(cfg: CultureDxConfig, llm_client):
    if not cfg.evidence.enabled:
        return None

    from culturedx.evidence.pipeline import EvidencePipeline
    from culturedx.evidence.retriever_factory import create_retriever

    retriever = create_retriever(cfg.evidence.retriever)
    evidence_scope_policy = cfg.evidence.scope_policy
    if evidence_scope_policy == "auto":
        evidence_scope_policy = "manual" if cfg.mode.target_disorders else "all_supported"

    return EvidencePipeline(
        llm_client=llm_client,
        retriever=retriever,
        target_disorders=cfg.mode.target_disorders,
        scope_policy=evidence_scope_policy,
        somatization_enabled=cfg.evidence.somatization.enabled,
        somatization_llm_fallback=cfg.evidence.somatization.llm_fallback,
        top_k=cfg.evidence.top_k_final,
        min_confidence=cfg.evidence.min_confidence,
    )


def to_eval_bucket(code: str) -> str | None:
    normalized = code.strip()
    if not normalized or normalized in EXCLUDED_CODES:
        return None
    if normalized in AMBIGUOUS_MAP:
        return normalized
    if normalized in CHILD_TO_BUCKET:
        return CHILD_TO_BUCKET[normalized]

    mapped = map_dataset_code(normalized)
    if not mapped:
        return None
    candidate = mapped[0]
    return CHILD_TO_BUCKET.get(candidate, candidate)


def map_eval_code_list(codes: list[str]) -> list[str]:
    buckets: list[str] = []
    seen: set[str] = set()
    for code in codes:
        bucket = to_eval_bucket(code)
        if bucket is None or bucket in seen:
            continue
        seen.add(bucket)
        buckets.append(bucket)
    return buckets


def load_filtered_cases(dataset_spec: dict[str, Any], max_cases: int) -> dict[str, Any]:
    adapter = get_adapter(dataset_spec["adapter_name"], dataset_spec["data_path"])
    split = dataset_spec["split"]
    all_cases = adapter.load(split=split) if split else adapter.load()

    skipped_cases: list[dict[str, Any]] = []
    eval_cases: list[ClinicalCase] = []
    for case in all_cases:
        gold_eval_codes = map_eval_code_list(case.diagnoses)
        if not gold_eval_codes:
            skipped_cases.append(
                {
                    "case_id": case.case_id,
                    "dataset": dataset_spec["output_name"],
                    "reason": "excluded_or_unmapped_gold",
                    "gold_diagnoses": list(case.diagnoses),
                }
            )
            continue
        eval_cases.append(case)

    if max_cases > 0:
        eval_cases = eval_cases[:max_cases]

    return {
        "adapter_name": dataset_spec["adapter_name"],
        "data_path": dataset_spec["data_path"],
        "split": split,
        "all_cases": len(all_cases),
        "eval_cases": eval_cases,
        "filtered_out": skipped_cases,
    }


def cleanup_output_dir(output_dir: Path, dataset_names: list[str]) -> None:
    known_files = [
        output_dir / "config.json",
        output_dir / "metrics_overall.json",
        output_dir / "metrics_per_disorder.json",
        output_dir / "metrics_per_dataset.json",
        output_dir / "confusion_matrix.json",
        output_dir / "report.md",
        output_dir / "checkpoint.json",
        output_dir / "errors.jsonl",
    ]
    for dataset_name in dataset_names:
        known_files.append(output_dir / f"results_{dataset_name}.jsonl")

    for path in known_files:
        if path.exists():
            path.unlink()


def build_eval_plan_payload(
    args: argparse.Namespace,
    cfg: CultureDxConfig,
    dataset_specs: list[dict[str, Any]],
    dataset_loads: dict[str, dict[str, Any]],
    model_name: str,
) -> dict[str, Any]:
    return {
        "config_paths": list(args.config),
        "datasets": [
            {
                **spec,
                "all_cases": dataset_loads[spec["output_name"]]["all_cases"],
                "eval_cases": len(dataset_loads[spec["output_name"]]["eval_cases"]),
                "filtered_out": len(dataset_loads[spec["output_name"]]["filtered_out"]),
            }
            for spec in dataset_specs
        ],
        "modes": normalize_name_list(args.modes),
        "model_name": model_name,
        "adapter_path": args.adapter_path,
        "with_evidence": args.with_evidence,
        "with_somatization": args.with_somatization and args.with_evidence,
        "max_cases": args.max_cases,
        "culturedx_config": cfg.model_dump(),
    }


def compute_config_hash(plan_payload: dict[str, Any]) -> str:
    return stable_fingerprint(plan_payload)


def load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_checkpoint(
    path: Path,
    *,
    config_hash: str,
    started_at: str,
    dataset: str | None,
    mode: str | None,
    last_completed_index: int,
    total_cases: int,
    completed_pairs: list[str],
    status: str,
) -> None:
    write_json(
        path,
        {
            "dataset": dataset,
            "mode": mode,
            "last_completed_index": last_completed_index,
            "total_cases": total_cases,
            "started_at": started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "config_hash": config_hash,
            "completed_pairs": completed_pairs,
            "status": status,
        },
    )


def count_attempted_cases(output_dir: Path, dataset_name: str, mode_name: str) -> int:
    results_path = output_dir / f"results_{dataset_name}.jsonl"
    errors_path = output_dir / "errors.jsonl"

    attempted: set[str] = set()
    for row in read_jsonl(results_path):
        if row.get("dataset") == dataset_name and row.get("mode") == mode_name:
            attempted.add(str(row["case_id"]))
    for row in read_jsonl(errors_path):
        if row.get("dataset") == dataset_name and row.get("mode") == mode_name:
            attempted.add(str(row["case_id"]))
    return len(attempted)


def load_existing_timing_summary(output_dir: Path) -> dict[str, dict[str, Any]]:
    metrics_path = output_dir / "metrics_per_dataset.json"
    if not metrics_path.exists():
        return {}
    with open(metrics_path, encoding="utf-8") as handle:
        metrics = json.load(handle)
    timing = metrics.get("timing_by_mode_dataset", {})
    return timing if isinstance(timing, dict) else {}


def estimate_sec_per_case(cfg: CultureDxConfig, output_dir: Path) -> float | None:
    timing_sections = load_existing_timing_summary(output_dir)
    observed = [
        entry.get("avg_elapsed_sec_per_case")
        for entry in timing_sections.values()
        if isinstance(entry, dict) and isinstance(entry.get("avg_elapsed_sec_per_case"), (int, float))
    ]
    observed = [value for value in observed if value is not None and value > 0]
    if observed:
        return sum(observed) / len(observed)

    if cfg.llm.provider == "vllm":
        return 30.0
    return 90.0


def serialize_case_result(
    *,
    run_id: str,
    order_index: int,
    mode_name: str,
    dataset_name: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    case = context["case"]
    evidence = context["evidence"]
    result = context["result"]

    prediction_record = serialize_dataclass(
        build_prediction_record(run_id, order_index, case, result)
    )
    prediction_record["dataset"] = dataset_name
    prediction_record["mode"] = mode_name
    prediction_record["gold_eval_codes"] = map_eval_code_list(case.diagnoses)

    predicted_codes = []
    if result.primary_diagnosis:
        predicted_codes.append(result.primary_diagnosis)
    predicted_codes.extend(result.comorbid_diagnoses)
    prediction_record["pred_eval_codes"] = map_eval_code_list(predicted_codes)
    prediction_record["primary_correct_mapped"] = is_correct_prediction(
        [result.primary_diagnosis] if result.primary_diagnosis else [],
        case.diagnoses,
    )
    prediction_record["top3_correct_mapped"] = is_correct_prediction(
        predicted_codes[:3],
        case.diagnoses,
    )
    evidence_total = evidence.stage_timings.get("total", 0.0) if evidence else 0.0
    diagnosis_total = result.stage_timings.get("diagnosis_total", 0.0)
    prediction_record["approx_case_elapsed_sec"] = evidence_total + diagnosis_total
    prediction_record["failure_records"] = [
        serialize_dataclass(item)
        for item in build_failure_records(run_id, case.case_id, evidence, result)
    ]
    prediction_record["stage_timing_records"] = [
        serialize_dataclass(item)
        for item in build_stage_timing_records(run_id, case.case_id, evidence, result)
    ]
    return prediction_record


def compute_per_disorder_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    label_set = {
        label
        for row in rows
        for label in row.get("gold_eval_codes", []) + row.get("pred_eval_codes", [])
    }
    metrics: dict[str, dict[str, float | int]] = {}
    for label in sorted(label_set):
        tp = fp = fn = tn = 0
        for row in rows:
            pred = label in set(row.get("pred_eval_codes", []))
            gold = label in set(row.get("gold_eval_codes", []))
            if pred and gold:
                tp += 1
            elif pred and not gold:
                fp += 1
            elif gold and not pred:
                fn += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
        metrics[label] = {
            "support": tp + fn,
            "predicted_positive": tp + fp,
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return metrics


def compute_group_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "num_cases": 0,
            "num_abstained": 0,
            "abstention_rate": 0.0,
            "top1_accuracy": 0.0,
            "top3_accuracy": 0.0,
            "exact_match": 0.0,
            "hamming_loss": 0.0,
            "macro_f1": 0.0,
            "reference_top1_accuracy_bucketed": 0.0,
            "reference_top3_accuracy_bucketed": 0.0,
        }

    preds = [row.get("pred_eval_codes", []) for row in rows]
    golds = [row.get("gold_eval_codes", []) for row in rows]
    diagnosis_metrics = compute_diagnosis_metrics(preds, golds, normalize=None)
    comorbidity_metrics = compute_comorbidity_metrics(preds, golds, normalize=None)

    num_cases = len(rows)
    num_abstained = sum(1 for row in rows if row.get("decision") == "abstain")
    top1_accuracy = sum(1 for row in rows if row.get("primary_correct_mapped")) / num_cases
    top3_accuracy = sum(1 for row in rows if row.get("top3_correct_mapped")) / num_cases
    hamming_accuracy = comorbidity_metrics.get("hamming_accuracy", 1.0)

    return {
        "num_cases": num_cases,
        "num_abstained": num_abstained,
        "abstention_rate": num_abstained / num_cases,
        "top1_accuracy": top1_accuracy,
        "top3_accuracy": top3_accuracy,
        "exact_match": comorbidity_metrics.get("subset_accuracy", 0.0),
        "hamming_loss": 1.0 - hamming_accuracy if hamming_accuracy is not None else None,
        "macro_f1": diagnosis_metrics.get("macro_f1", 0.0),
        "reference_top1_accuracy_bucketed": diagnosis_metrics.get("top1_accuracy", 0.0),
        "reference_top3_accuracy_bucketed": diagnosis_metrics.get("top3_accuracy", 0.0),
        "diagnosis_metrics": diagnosis_metrics,
        "comorbidity_metrics": comorbidity_metrics,
    }


def compute_confusion(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = {
        label
        for row in rows
        for label in row.get("gold_eval_codes", []) + row.get("pred_eval_codes", [])
    }
    ordered_labels = sorted(labels)
    if "ABSTAIN" not in ordered_labels:
        ordered_labels.append("ABSTAIN")

    matrix: dict[str, dict[str, int]] = {
        gold_label: {pred_label: 0 for pred_label in ordered_labels}
        for gold_label in ordered_labels
        if gold_label != "ABSTAIN"
    }

    for row in rows:
        gold_label = row.get("gold_eval_codes", ["ABSTAIN"])[0]
        pred_label = row.get("pred_eval_codes", ["ABSTAIN"])[0]
        if not row.get("pred_eval_codes"):
            pred_label = "ABSTAIN"
        matrix.setdefault(gold_label, {label: 0 for label in ordered_labels})
        if pred_label not in matrix[gold_label]:
            for gold_row in matrix.values():
                gold_row[pred_label] = gold_row.get(pred_label, 0)
            ordered_labels.append(pred_label)
        matrix[gold_label][pred_label] = matrix[gold_label].get(pred_label, 0) + 1

    return {"labels": ordered_labels, "matrix": matrix}


def compute_error_patterns(rows: list[dict[str, Any]], limit: int = 15) -> list[dict[str, Any]]:
    counter: Counter[tuple[str, str, str, str]] = Counter()
    examples: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)

    for row in rows:
        if row.get("primary_correct_mapped"):
            continue
        gold_label = row.get("gold_eval_codes", ["ABSTAIN"])[0]
        pred_label = row.get("pred_eval_codes", ["ABSTAIN"])[0] if row.get("pred_eval_codes") else "ABSTAIN"
        key = (
            str(row.get("mode")),
            str(row.get("dataset")),
            gold_label,
            pred_label,
        )
        counter[key] += 1
        if len(examples[key]) < 5:
            examples[key].append(str(row.get("case_id")))

    patterns = []
    for (mode_name, dataset_name, gold_label, pred_label), count in counter.most_common(limit):
        patterns.append(
            {
                "mode": mode_name,
                "dataset": dataset_name,
                "gold": gold_label,
                "predicted": pred_label,
                "count": count,
                "example_case_ids": examples[(mode_name, dataset_name, gold_label, pred_label)],
            }
        )
    return patterns


def aggregate_metrics(
    rows: list[dict[str, Any]],
    timing_by_pair: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    overall = {
        "global": compute_group_metrics(rows),
        "by_mode": {},
    }
    per_dataset: dict[str, Any] = {}
    per_disorder: dict[str, Any] = {
        "global": compute_per_disorder_metrics(rows),
        "by_mode": {},
        "by_dataset": {},
        "by_mode_dataset": {},
    }
    confusion: dict[str, Any] = {
        "global": compute_confusion(rows),
        "by_mode": {},
        "by_dataset": {},
        "by_mode_dataset": {},
    }

    rows_by_mode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows_by_dataset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        mode_name = str(row["mode"])
        dataset_name = str(row["dataset"])
        pair_key = f"{mode_name}:{dataset_name}"
        rows_by_mode[mode_name].append(row)
        rows_by_dataset[dataset_name].append(row)
        rows_by_pair[pair_key].append(row)

    for mode_name, mode_rows in sorted(rows_by_mode.items()):
        overall["by_mode"][mode_name] = compute_group_metrics(mode_rows)
        per_disorder["by_mode"][mode_name] = compute_per_disorder_metrics(mode_rows)
        confusion["by_mode"][mode_name] = compute_confusion(mode_rows)

    for dataset_name, dataset_rows in sorted(rows_by_dataset.items()):
        per_disorder["by_dataset"][dataset_name] = compute_per_disorder_metrics(dataset_rows)
        confusion["by_dataset"][dataset_name] = compute_confusion(dataset_rows)

    timing_summary: dict[str, Any] = {}
    for pair_key, pair_rows in sorted(rows_by_pair.items()):
        mode_name, dataset_name = pair_key.split(":", 1)
        metrics = compute_group_metrics(pair_rows)
        metrics["timing"] = timing_by_pair.get(pair_key, {})
        per_dataset[pair_key] = metrics
        per_disorder["by_mode_dataset"][pair_key] = compute_per_disorder_metrics(pair_rows)
        confusion["by_mode_dataset"][pair_key] = compute_confusion(pair_rows)
        timing_summary[pair_key] = timing_by_pair.get(pair_key, {})

    per_dataset["timing_by_mode_dataset"] = timing_summary
    return overall, per_disorder, per_dataset, confusion


def render_markdown_report(
    *,
    plan_payload: dict[str, Any],
    overall: dict[str, Any],
    per_disorder: dict[str, Any],
    per_dataset: dict[str, Any],
    error_patterns: list[dict[str, Any]],
    timing_by_pair: dict[str, dict[str, Any]],
    total_wall_time_sec: float,
) -> str:
    lines = [
        "# CultureDx Full Evaluation Report",
        "",
        "## Config Summary",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Config files: {', '.join(plan_payload['config_paths'])}",
        f"- Modes: {', '.join(plan_payload['modes'])}",
        f"- Datasets: {', '.join(item['output_name'] for item in plan_payload['datasets'])}",
        f"- Model: {plan_payload['model_name']}",
        f"- Adapter path: {plan_payload.get('adapter_path') or 'not provided'}",
        f"- Evidence: {'enabled' if plan_payload['with_evidence'] else 'disabled'}",
        f"- Somatization: {'enabled' if plan_payload['with_somatization'] else 'disabled'}",
        f"- Max cases per dataset: {plan_payload['max_cases'] or 'all'}",
        "",
        "## Overall Metrics",
        "",
        "| Scope | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    global_metrics = overall["global"]
    lines.append(
        "| global | "
        f"{global_metrics['num_cases']} | "
        f"{global_metrics['top1_accuracy']:.4f} | "
        f"{global_metrics['top3_accuracy']:.4f} | "
        f"{global_metrics['exact_match']:.4f} | "
        f"{global_metrics['hamming_loss']:.4f} | "
        f"{global_metrics['macro_f1']:.4f} | "
        f"{global_metrics['abstention_rate']:.4f} |"
    )
    for mode_name, metrics in sorted(overall["by_mode"].items()):
        lines.append(
            "| "
            f"{mode_name} | "
            f"{metrics['num_cases']} | "
            f"{metrics['top1_accuracy']:.4f} | "
            f"{metrics['top3_accuracy']:.4f} | "
            f"{metrics['exact_match']:.4f} | "
            f"{metrics['hamming_loss']:.4f} | "
            f"{metrics['macro_f1']:.4f} | "
            f"{metrics['abstention_rate']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Per-Dataset Comparison",
            "",
            "| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for pair_key, metrics in sorted(
        ((key, value) for key, value in per_dataset.items() if key != "timing_by_mode_dataset"),
        key=lambda item: item[0],
    ):
        timing = metrics.get("timing", {})
        lines.append(
            "| "
            f"{pair_key} | "
            f"{metrics['num_cases']} | "
            f"{metrics['top1_accuracy']:.4f} | "
            f"{metrics['top3_accuracy']:.4f} | "
            f"{metrics['exact_match']:.4f} | "
            f"{metrics['hamming_loss']:.4f} | "
            f"{metrics['macro_f1']:.4f} | "
            f"{metrics['abstention_rate']:.4f} | "
            f"{format_duration(timing.get('elapsed_sec', 0.0))} | "
            f"{timing.get('cases_per_sec', 0.0):.3f} |"
        )

    lines.extend(
        [
            "",
            "## Per-Disorder Metrics",
            "",
            "| Mode | Disorder | Support | Precision | Recall | F1 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )

    for mode_name, metrics_by_code in sorted(per_disorder["by_mode"].items()):
        for disorder_code, metrics in sorted(metrics_by_code.items()):
            lines.append(
                "| "
                f"{mode_name} | "
                f"{disorder_code} | "
                f"{metrics['support']} | "
                f"{metrics['precision']:.4f} | "
                f"{metrics['recall']:.4f} | "
                f"{metrics['f1']:.4f} |"
            )

    lines.extend(
        [
            "",
            "## Top Error Patterns",
            "",
            "| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |",
            "|---|---|---|---|---:|---|",
        ]
    )
    if not error_patterns:
        lines.append("| — | — | — | — | 0 | — |")
    else:
        for pattern in error_patterns:
            lines.append(
                "| "
                f"{pattern['mode']} | "
                f"{pattern['dataset']} | "
                f"{pattern['gold']} | "
                f"{pattern['predicted']} | "
                f"{pattern['count']} | "
                f"{', '.join(pattern['example_case_ids'])} |"
            )

    total_cases = overall["global"]["num_cases"]
    total_cases_per_sec = safe_rate(total_cases, total_wall_time_sec)
    lines.extend(
        [
            "",
            "## Timing Statistics",
            "",
            f"- Total wall time: {format_duration(total_wall_time_sec)}",
            f"- Total evaluated cases: {total_cases}",
            f"- Overall cases/sec: {total_cases_per_sec:.3f}",
            "",
            "| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for pair_key, timing in sorted(timing_by_pair.items()):
        lines.append(
            "| "
            f"{pair_key} | "
            f"{format_duration(timing.get('elapsed_sec', 0.0))} | "
            f"{timing.get('cases_per_sec', 0.0):.3f} | "
            f"{timing.get('avg_elapsed_sec_per_case', 0.0):.3f} | "
            f"{timing.get('batch_count', 0)} |"
        )

    return "\n".join(lines) + "\n"


def run_mode_dataset(
    *,
    output_dir: Path,
    base_cfg: CultureDxConfig,
    dataset_spec: dict[str, Any],
    cases: list[ClinicalCase],
    mode_name: str,
    model_name: str | None,
    with_evidence: bool,
    with_somatization: bool,
    adapter_path: str | None,
    batch_size: int,
    resume: bool,
    started_at: str,
    config_hash: str,
    completed_pairs: list[str],
    prior_timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dataset_name = dataset_spec["output_name"]
    pair_key = f"{mode_name}:{dataset_name}"
    runner_dir = output_dir / ".runner" / pair_key.replace(":", "_")
    runner_dir.mkdir(parents=True, exist_ok=True)

    run_cfg = clone_eval_config(
        base_cfg,
        mode_name=mode_name,
        model_name=model_name,
        with_evidence=with_evidence,
        with_somatization=with_somatization,
    )
    mode, llm_client, checker_llm = create_mode(run_cfg)
    evidence_pipeline = create_evidence_pipeline(run_cfg, llm_client)
    max_cases_in_flight = max(1, min(batch_size, getattr(run_cfg.llm, "max_concurrent", 4)))
    runner = ResumableExperimentRunner(
        mode=mode,
        output_dir=runner_dir,
        evidence_pipeline=evidence_pipeline,
        max_cases_in_flight=max_cases_in_flight,
    )

    results_path = output_dir / f"results_{dataset_name}.jsonl"
    checkpoint_path = output_dir / "checkpoint.json"
    total_cases = len(cases)
    resume_from = count_attempted_cases(output_dir, dataset_name, mode_name) if resume else 0
    if resume_from >= total_cases:
        logger.info("Skipping %s (%d/%d cases already attempted)", pair_key, resume_from, total_cases)
        if llm_client is not None:
            llm_client.close()
        if checker_llm is not None and checker_llm is not llm_client:
            checker_llm.close()
        return prior_timing or {
            "pair_key": pair_key,
            "elapsed_sec": 0.0,
            "cases_per_sec": 0.0,
            "avg_elapsed_sec_per_case": 0.0,
            "batch_count": 0,
            "resume_from": resume_from,
            "num_cases": total_cases,
        }

    logger.info(
        "Running %s on %d cases (resume_from=%d, evidence=%s, somatization=%s)",
        pair_key,
        total_cases,
        resume_from,
        "yes" if with_evidence else "no",
        "yes" if with_evidence and with_somatization else "no",
    )
    if adapter_path:
        logger.info(
            "adapter_path is provenance-only for current clients; ensure the served model already includes %s",
            adapter_path,
        )

    pair_start = time.monotonic()
    batch_count = 0

    try:
        for batch_start in range(resume_from, total_cases, batch_size):
            batch_end = min(batch_start + batch_size, total_cases)
            batch = cases[batch_start:batch_end]
            contexts, batch_errors = runner.run_batch(batch)

            result_rows = []
            for context in contexts:
                order_index = batch_start + int(context["batch_index"])
                result_rows.append(
                    serialize_case_result(
                        run_id=pair_key.replace(":", "_"),
                        order_index=order_index,
                        mode_name=mode_name,
                        dataset_name=dataset_name,
                        context=context,
                    )
                )
            append_jsonl(results_path, result_rows)

            error_rows = []
            for error in batch_errors:
                error_rows.append(
                    {
                        "dataset": dataset_name,
                        "mode": mode_name,
                        "case_id": error["case_id"],
                        "batch_start": batch_start,
                        "batch_end": batch_end,
                        "error": error["error"],
                        "traceback": error["traceback"],
                    }
                )
            append_jsonl(output_dir / "errors.jsonl", error_rows)

            batch_count += 1
            elapsed = time.monotonic() - pair_start
            processed = batch_end - resume_from
            rate = safe_rate(processed, elapsed)
            eta = safe_rate(total_cases - batch_end, rate)
            logger.info(
                "Batch %d/%d (%.1f%%) | mode=%s dataset=%s | elapsed: %s | ETA: %s",
                batch_end,
                total_cases,
                batch_end / total_cases * 100.0 if total_cases else 100.0,
                mode_name,
                dataset_name,
                format_duration(elapsed),
                format_duration(eta),
            )
            save_checkpoint(
                checkpoint_path,
                config_hash=config_hash,
                started_at=started_at,
                dataset=dataset_name,
                mode=mode_name,
                last_completed_index=batch_end,
                total_cases=total_cases,
                completed_pairs=completed_pairs,
                status="running",
            )
    finally:
        if llm_client is not None:
            llm_client.close()
        if checker_llm is not None and checker_llm is not llm_client:
            checker_llm.close()

    pair_elapsed = time.monotonic() - pair_start
    cases_processed = total_cases - resume_from
    timing = {
        "pair_key": pair_key,
        "elapsed_sec": pair_elapsed,
        "cases_per_sec": safe_rate(cases_processed, pair_elapsed),
        "avg_elapsed_sec_per_case": safe_rate(pair_elapsed, cases_processed),
        "batch_count": batch_count,
        "resume_from": resume_from,
        "num_cases": total_cases,
    }
    logger.info(
        "Completed %s | cases=%d | elapsed=%s | cases/sec=%.3f",
        pair_key,
        total_cases,
        format_duration(pair_elapsed),
        timing["cases_per_sec"],
    )
    return timing


def run_eval_for_model(
    *,
    args: argparse.Namespace,
    cfg: CultureDxConfig,
    dataset_specs: list[dict[str, Any]],
    dataset_loads: dict[str, dict[str, Any]],
    mode_names: list[str],
    model_name: str,
    output_dir: Path,
) -> int:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not args.resume:
        cleanup_output_dir(output_dir, [spec["output_name"] for spec in dataset_specs])
    logger.info("Preparing evaluation for model=%s output_dir=%s", model_name, output_dir)

    plan_payload = build_eval_plan_payload(
        args,
        cfg,
        dataset_specs,
        dataset_loads,
        model_name=model_name,
    )
    config_hash = compute_config_hash(plan_payload)
    config_json_path = output_dir / "config.json"
    write_json(
        config_json_path,
        {
            **plan_payload,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "config_hash": config_hash,
            "output_dir": str(output_dir),
            "batch_size": args.batch_size,
            "dry_run": args.dry_run,
        },
    )

    checkpoint_path = output_dir / "checkpoint.json"
    checkpoint = load_checkpoint(checkpoint_path)
    if args.resume:
        if checkpoint is None:
            raise SystemExit(f"--resume requested but no checkpoint found at {checkpoint_path}")
        if checkpoint.get("config_hash") != config_hash:
            raise SystemExit(
                "Checkpoint config hash does not match current config. "
                "Use a fresh output directory or rerun with the original settings."
            )

    if args.dry_run:
        heuristic_sec_per_case = estimate_sec_per_case(cfg, output_dir)
        total_cases = sum(len(dataset_loads[spec["output_name"]]["eval_cases"]) for spec in dataset_specs)
        total_pairs = len(dataset_specs) * len(mode_names)
        logger.info("Dry run summary for model=%s:", model_name)
        for spec in dataset_specs:
            load_info = dataset_loads[spec["output_name"]]
            eval_count = len(load_info["eval_cases"])
            logger.info(
                "  dataset=%s adapter=%s raw=%d evaluable=%d filtered=%d",
                spec["output_name"],
                spec["adapter_name"],
                load_info["all_cases"],
                eval_count,
                len(load_info["filtered_out"]),
            )
        logger.info(
            "  modes=%s pairs=%d batch_size=%d max_cases=%s",
            ",".join(mode_names),
            total_pairs,
            args.batch_size,
            args.max_cases or "all",
        )
        logger.info("  output_dir=%s", output_dir)
        if heuristic_sec_per_case is not None:
            est_total_sec = total_cases * len(mode_names) * heuristic_sec_per_case
            logger.info(
                "  estimated time (heuristic %.1fs/case): %s",
                heuristic_sec_per_case,
                format_duration(est_total_sec),
            )
        else:
            logger.info("  estimated time: unavailable (no historical timing data)")
        logger.info("Dry run complete. No inference executed.")
        return 0

    started_at = checkpoint["started_at"] if checkpoint else datetime.now(timezone.utc).isoformat()
    completed_pairs: list[str] = list(checkpoint.get("completed_pairs", [])) if checkpoint else []
    total_wall_start = time.monotonic()
    timing_by_pair: dict[str, dict[str, Any]] = load_existing_timing_summary(output_dir) if args.resume else {}

    for mode_name in mode_names:
        for spec in dataset_specs:
            dataset_name = spec["output_name"]
            pair_key = f"{mode_name}:{dataset_name}"
            cases = dataset_loads[dataset_name]["eval_cases"]
            if pair_key in completed_pairs:
                logger.info("Skipping %s (marked complete in checkpoint)", pair_key)
                timing_by_pair.setdefault(pair_key, {
                    "pair_key": pair_key,
                    "elapsed_sec": 0.0,
                    "cases_per_sec": 0.0,
                    "avg_elapsed_sec_per_case": 0.0,
                    "batch_count": 0,
                    "resume_from": len(cases),
                    "num_cases": len(cases),
                })
                continue

            timing_by_pair[pair_key] = run_mode_dataset(
                output_dir=output_dir,
                base_cfg=cfg,
                dataset_spec=spec,
                cases=cases,
                mode_name=mode_name,
                model_name=model_name,
                with_evidence=args.with_evidence,
                with_somatization=args.with_somatization,
                adapter_path=args.adapter_path,
                batch_size=args.batch_size,
                resume=args.resume,
                started_at=started_at,
                config_hash=config_hash,
                completed_pairs=completed_pairs,
                prior_timing=timing_by_pair.get(pair_key),
            )
            if pair_key not in completed_pairs:
                completed_pairs.append(pair_key)
            save_checkpoint(
                checkpoint_path,
                config_hash=config_hash,
                started_at=started_at,
                dataset=dataset_name,
                mode=mode_name,
                last_completed_index=len(cases),
                total_cases=len(cases),
                completed_pairs=completed_pairs,
                status="running",
            )

    result_rows: list[dict[str, Any]] = []
    for spec in dataset_specs:
        result_rows.extend(read_jsonl(output_dir / f"results_{spec['output_name']}.jsonl"))

    overall, per_disorder, per_dataset, confusion = aggregate_metrics(result_rows, timing_by_pair)
    error_patterns = compute_error_patterns(result_rows)
    total_wall_time_sec = time.monotonic() - total_wall_start

    write_json(output_dir / "metrics_overall.json", overall)
    write_json(output_dir / "metrics_per_disorder.json", per_disorder)
    write_json(output_dir / "metrics_per_dataset.json", per_dataset)
    write_json(output_dir / "confusion_matrix.json", confusion)

    report_text = render_markdown_report(
        plan_payload=plan_payload,
        overall=overall,
        per_disorder=per_disorder,
        per_dataset=per_dataset,
        error_patterns=error_patterns,
        timing_by_pair=timing_by_pair,
        total_wall_time_sec=total_wall_time_sec,
    )
    (output_dir / "report.md").write_text(report_text, encoding="utf-8")

    save_checkpoint(
        checkpoint_path,
        config_hash=config_hash,
        started_at=started_at,
        dataset=None,
        mode=None,
        last_completed_index=0,
        total_cases=sum(len(dataset_loads[spec["output_name"]]["eval_cases"]) for spec in dataset_specs),
        completed_pairs=completed_pairs,
        status="completed",
    )

    logger.info("Full evaluation complete.")
    logger.info("Results written to %s", output_dir)
    return 0


def main() -> int:
    args = parse_args()
    cfg = load_culturedx_config(args.config)

    dataset_specs = [resolve_dataset_spec(name, cfg) for name in normalize_name_list(args.datasets)]
    mode_names = normalize_name_list(args.modes)
    model_names = normalize_model_name_list(args.model_name, cfg.llm.model_id)
    base_output_dir = Path(args.output_dir)
    base_output_dir.mkdir(parents=True, exist_ok=True)

    dataset_loads: dict[str, dict[str, Any]] = {}
    for spec in dataset_specs:
        logger.info(
            "Loading dataset %s via adapter=%s from %s",
            spec["output_name"],
            spec["adapter_name"],
            spec["data_path"],
        )
        dataset_loads[spec["output_name"]] = load_filtered_cases(spec, args.max_cases)

    for model_name in model_names:
        run_output_dir = resolve_model_output_dir(base_output_dir, model_names, model_name)
        run_eval_for_model(
            args=args,
            cfg=cfg,
            dataset_specs=dataset_specs,
            dataset_loads=dataset_loads,
            mode_names=mode_names,
            model_name=model_name,
            output_dir=run_output_dir,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
