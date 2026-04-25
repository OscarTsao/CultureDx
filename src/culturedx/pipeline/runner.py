"""Experiment runner for case execution and canonical artifact emission.

This module is the bridge between mode execution and reviewer-facing outputs:
it runs cases, preserves ordering under bounded concurrency, and writes both
legacy-compatible and canonical artifacts for evaluation/reporting.
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from culturedx.core.models import ClinicalCase, DiagnosisResult, FailureInfo
from culturedx.eval.code_mapping import map_code_list
from culturedx.eval.metrics import compute_comorbidity_metrics, compute_diagnosis_metrics
from culturedx.eval.lingxidiag_paper import compute_table4_metrics_v2, to_paper_parent
from culturedx.evidence.pipeline import EvidencePipeline
from culturedx.modes.base import BaseModeOrchestrator, case_execution_context
from culturedx.ontology.symptom_map import load_somatization_map
from culturedx.pipeline.artifacts import (
    CaseSelectionManifest,
    MetricsSummary,
    RunManifest,
    build_failure_records,
    build_prediction_record,
    build_stage_timing_records,
    serialize_dataclass,
    stable_fingerprint,
)

logger = logging.getLogger(__name__)


def _predict_four_class(codes: list[str]) -> str:
    """Map ICD-10 codes to LingxiDiag 4-class label."""
    has_dep = any(c.startswith("F32") or c.startswith("F33") for c in codes)
    has_anx = any(c.startswith("F40") or c.startswith("F41") for c in codes)
    if has_dep and has_anx:
        return "Mixed"
    if has_dep:
        return "Depression"
    if has_anx:
        return "Anxiety"
    return "Other"


class ExperimentRunner:
    """Run a mode on a list of cases and collect canonical artifacts."""

    def __init__(
        self,
        mode: BaseModeOrchestrator,
        output_dir: str | Path,
        evidence_pipeline: "EvidencePipeline | None" = None,
        max_cases_in_flight: int = 1,
    ) -> None:
        self.mode = mode
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_pipeline = evidence_pipeline
        self.max_cases_in_flight = max(1, max_cases_in_flight)
        self.run_id = self.output_dir.name
        self._last_case_contexts: list[dict[str, Any]] = []
        self._last_manifest: RunManifest | None = None

    @staticmethod
    def create_run_dir(
        base_dir: str | Path,
        mode_type: str,
        dataset_name: str,
    ) -> Path:
        """Create a timestamped run directory."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        name = f"{mode_type}_{dataset_name}_{ts}"
        run_dir = Path(base_dir) / name
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def run(self, cases: list[ClinicalCase]) -> list[DiagnosisResult]:
        """Run the configured mode across cases with bounded concurrency.

        Results are written in input order even when cases are processed in
        parallel. The method also captures the last case/evidence/result tuple
        set so later metric/report steps operate on the exact emitted payloads.
        """
        if not cases:
            self._last_case_contexts = []
            self._save_predictions([])
            return []

        results: list[DiagnosisResult | None] = [None] * len(cases)
        evidences: list[Any] = [None] * len(cases)

        def _process_one(idx: int, case: ClinicalCase) -> tuple[int, Any, DiagnosisResult]:
            logger.info("Processing case %d/%d: %s", idx + 1, len(cases), case.case_id)
            with case_execution_context(
                outer_parallelism=self.max_cases_in_flight > 1,
            ):
                evidence = None
                evidence_start = time.monotonic()
                if self.evidence_pipeline is not None:
                    evidence = self.evidence_pipeline.extract(case)
                    if "total" not in evidence.stage_timings:
                        evidence.stage_timings["total"] = time.monotonic() - evidence_start
                diagnosis_start = time.monotonic()
                try:
                    result = self.mode.diagnose(case, evidence=evidence)
                except Exception as exc:
                    logger.error(
                        "Case %s failed: %s", case.case_id, exc,
                    )
                    result = DiagnosisResult(
                        case_id=case.case_id,
                        primary_diagnosis=None,
                        comorbid_diagnoses=[],
                        confidence=0.0,
                        decision="abstain",
                        failure=FailureInfo(
                            code="runner_exception",
                            stage="diagnose",
                            message=str(exc),
                        ),
                    )
                result.stage_timings.setdefault(
                    "diagnosis_total",
                    time.monotonic() - diagnosis_start,
                )
                return idx, evidence, result

        if self.max_cases_in_flight <= 1 or len(cases) == 1:
            for idx, case in enumerate(cases):
                out_idx, evidence, result = _process_one(idx, case)
                evidences[out_idx] = evidence
                results[out_idx] = result
        else:
            with ThreadPoolExecutor(
                max_workers=min(self.max_cases_in_flight, len(cases))
            ) as executor:
                futures = {
                    executor.submit(_process_one, idx, case): idx
                    for idx, case in enumerate(cases)
                }
                for future in as_completed(futures):
                    out_idx, evidence, result = future.result()
                    evidences[out_idx] = evidence
                    results[out_idx] = result

        final_results = [result for result in results if result is not None]
        self._last_case_contexts = [
            {"case": case, "evidence": evidences[idx], "result": final_results[idx]}
            for idx, case in enumerate(cases)
        ]
        self._save_predictions(self._last_case_contexts)
        return final_results

    def save_run_info(
        self,
        config_dict: dict,
        dataset_name: str,
        num_cases: int,
        mode_type: str,
        *,
        case_ids: list[str] | None = None,
        runtime_context: dict[str, Any] | None = None,
    ) -> None:
        """Save canonical and legacy run metadata.

        ``run_manifest.json`` is the preferred schema; ``run_info.json`` stays
        for compatibility with older scripts and analysis notebooks.
        """
        normalized_case_ids = [str(case_id) for case_id in (case_ids or [])]
        normalized_runtime = dict(runtime_context or {})
        manifest = RunManifest(
            run_id=self.run_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            git_hash=self._get_git_hash(),
            mode=mode_type,
            dataset=dataset_name,
            num_cases=num_cases,
            model_name=getattr(getattr(self.mode, "llm", None), "model", ""),
            config_fingerprint=stable_fingerprint(config_dict),
            case_selection_fingerprint=stable_fingerprint(normalized_case_ids)
            if normalized_case_ids
            else "",
            config=config_dict,
            runtime_context=normalized_runtime,
        )
        self._last_manifest = manifest
        self._write_json(self.output_dir / "run_manifest.json", serialize_dataclass(manifest))
        if normalized_case_ids:
            case_selection = CaseSelectionManifest(
                run_id=self.run_id,
                dataset=dataset_name,
                num_cases=len(normalized_case_ids),
                case_ids=normalized_case_ids,
                case_order_fingerprint=manifest.case_selection_fingerprint,
                runtime_context=normalized_runtime,
            )
            self._write_json(
                self.output_dir / "case_selection.json",
                serialize_dataclass(case_selection),
            )

        legacy = {
            "timestamp": manifest.created_at,
            "git_hash": manifest.git_hash,
            "mode": manifest.mode,
            "dataset": manifest.dataset,
            "num_cases": manifest.num_cases,
            "config": config_dict,
            "config_fingerprint": manifest.config_fingerprint,
            "case_selection_fingerprint": manifest.case_selection_fingerprint,
            "runtime_context": normalized_runtime,
        }
        self._write_json(self.output_dir / "run_info.json", legacy)

    def evaluate(
        self, results: list[DiagnosisResult], cases: list[ClinicalCase]
    ) -> dict:
        """Evaluate results against ground truth and emit reviewer-friendly artifacts."""
        if len(results) != len(cases):
            raise ValueError(
                f"results ({len(results)}) and cases ({len(cases)}) must have same length"
            )

        metrics: dict[str, Any] = {}
        has_dx = [c for c in cases if c.diagnoses]
        if has_dx:
            preds = []
            golds = []
            for r, c in zip(results, cases):
                if c.diagnoses:
                    pred_dx = [r.primary_diagnosis] if r.primary_diagnosis else ["unknown"]
                    pred_dx += r.comorbid_diagnoses
                    mapped_gold = map_code_list(c.diagnoses)
                    if not mapped_gold:
                        continue
                    preds.append(map_code_list(pred_dx))
                    golds.append(mapped_gold)
            if preds:
                metrics["diagnosis"] = compute_diagnosis_metrics(preds, golds)
                metrics["comorbidity"] = compute_comorbidity_metrics(preds, golds)
                # 4-class evaluation (LingxiDiag-compatible)
                four_class_preds = []
                four_class_golds = []
                for r, c in zip(results, cases):
                    gold_label = (c.metadata or {}).get("four_class_label")
                    if gold_label and c.diagnoses:
                        pred_dx = [r.primary_diagnosis] if r.primary_diagnosis else []
                        pred_dx += r.comorbid_diagnoses
                        pred_label = _predict_four_class(pred_dx)
                        four_class_preds.append(pred_label)
                        four_class_golds.append(gold_label)
                if four_class_preds:
                    from sklearn.metrics import accuracy_score, f1_score as sk_f1

                    metrics["four_class"] = {
                        "accuracy": float(accuracy_score(four_class_golds, four_class_preds)),
                        "macro_f1": float(
                            sk_f1(
                                four_class_golds,
                                four_class_preds,
                                average="macro",
                                zero_division=0,
                            )
                        ),
                        "weighted_f1": float(
                            sk_f1(
                                four_class_golds,
                                four_class_preds,
                                average="weighted",
                                zero_division=0,
                            )
                        ),
                        "n_cases": len(four_class_preds),
                    }


        # ── Paper-official Table 4 metrics (2c/4c/12c + 11-metric Overall) ──
        # Computes the same 11-metric Overall used by the research branch,
        # giving every config a consistent cross-branch score.
        try:
            table4_cases = []
            has_raw_table4_source = any(
                bool((case.metadata or {}).get("diagnosis_code_full"))
                for case in cases
            )
            if cases and not has_raw_table4_source and all(
                case.dataset == "lingxidiag16k" for case in cases
            ):
                raise RuntimeError(
                    "diagnosis_code_full missing for LingxiDiag cases. "
                    "Required for F41.2 raw-code evaluation contract."
                )
            for r, c in zip(results, cases):
                raw_code = (c.metadata or {}).get("diagnosis_code_full", "")
                if not raw_code:
                    if has_raw_table4_source:
                        raise RuntimeError(
                            f"diagnosis_code_full missing for case {c.case_id}. "
                            "Required for F41.2 raw-code evaluation contract."
                        )
                    continue
                decision_trace = r.decision_trace or {}
                diagnostician_trace = decision_trace.get("diagnostician", {})
                ranked = (
                    decision_trace.get("diagnostician_ranked")
                    or (
                        diagnostician_trace.get("ranked_codes")
                        if isinstance(diagnostician_trace, dict)
                        else None
                    )
                    or list(r.candidate_disorders or [])
                    or ([r.primary_diagnosis] if r.primary_diagnosis else [])
                )
                table4_cases.append({
                    "case_id": c.case_id,
                    "raw_gold_code": raw_code,
                    "primary_diagnosis": r.primary_diagnosis,
                    "ranked_codes": ranked,
                    "comorbid_diagnoses": list(r.comorbid_diagnoses or []),
                })
            if table4_cases:
                def _primary(case: dict) -> str:
                    return to_paper_parent(case["primary_diagnosis"])

                def _ranked(case: dict) -> list[str]:
                    return [to_paper_parent(code) for code in case["ranked_codes"]]

                def _multilabel(case: dict) -> list[str]:
                    codes = [case["primary_diagnosis"]]
                    codes.extend(case["comorbid_diagnoses"])
                    return [to_paper_parent(code) for code in codes if code]

                def _raw_gold(case: dict) -> str:
                    return case["raw_gold_code"]

                def _raw_pred(case: dict) -> list[str]:
                    codes = [case["primary_diagnosis"]]
                    codes.extend(case["comorbid_diagnoses"])
                    return [code for code in codes if code]

                metrics["table4"] = compute_table4_metrics_v2(
                    cases=table4_cases,
                    get_primary_prediction=_primary,
                    get_ranked_prediction=_ranked,
                    get_multilabel_prediction=_multilabel,
                    get_raw_gold_code=_raw_gold,
                    get_raw_pred_codes=_raw_pred,
                )
                logger.info(
                    "Table 4 (contract v2): Top-1=%.3f Top-3=%.3f F1_m=%.3f Overall=%.4f",
                    metrics["table4"].get("12class_Top1", 0),
                    metrics["table4"].get("12class_Top3", 0),
                    metrics["table4"].get("12class_F1_macro", 0),
                    metrics["table4"].get("Overall", float("nan")),
                )
        except Exception:
            logger.warning("Table 4 computation failed", exc_info=True)
            raise
        slice_metrics = self._compute_slice_metrics(results, cases)
        summary_metrics = self._build_metrics_summary_payload(metrics)
        summary = MetricsSummary(
            run_id=self.run_id,
            dataset=cases[0].dataset if cases else "",
            num_cases=len(cases),
            metrics=summary_metrics,
            slice_metrics=slice_metrics,
        )
        self._save_metrics(metrics, summary)
        self._save_summary_markdown(summary)
        return metrics

    def _save_predictions(self, case_contexts: list[dict[str, Any]]) -> None:
        """Save canonical prediction, failure, and timing artifacts.

        The three files are emitted together so downstream tools can join them
        by ``run_id`` and ``case_id`` without depending on positional order.
        """
        pred_path = self.output_dir / "predictions.jsonl"
        failure_path = self.output_dir / "failures.jsonl"
        timing_path = self.output_dir / "stage_timings.jsonl"

        with open(pred_path, "w", encoding="utf-8") as pred_f, open(
            failure_path, "w", encoding="utf-8"
        ) as failure_f, open(timing_path, "w", encoding="utf-8") as timing_f:
            for idx, context in enumerate(case_contexts):
                case = context["case"]
                evidence = context["evidence"]
                result = context["result"]

                prediction = build_prediction_record(self.run_id, idx, case, result)
                pred_f.write(json.dumps(serialize_dataclass(prediction), ensure_ascii=False) + "\n")

                for failure in build_failure_records(self.run_id, case.case_id, evidence, result):
                    failure_f.write(
                        json.dumps(serialize_dataclass(failure), ensure_ascii=False) + "\n"
                    )

                for timing in build_stage_timing_records(self.run_id, case.case_id, evidence, result):
                    timing_f.write(
                        json.dumps(serialize_dataclass(timing), ensure_ascii=False) + "\n"
                    )

    def _save_metrics(self, metrics: dict[str, Any], summary: MetricsSummary) -> None:
        """Save legacy and canonical metrics artifacts."""
        self._write_json(self.output_dir / "metrics.json", metrics)
        self._write_json(
            self.output_dir / "metrics_summary.json",
            serialize_dataclass(summary),
        )

    @staticmethod
    def _build_metrics_summary_payload(metrics: dict[str, Any]) -> dict[str, Any]:
        """Build naming-aware canonical metrics_summary payload.

        ``metrics.json`` remains legacy-compatible. ``metrics_summary.json``
        separates paper-canonical Table 4 values from internal diagnostics so
        similarly named Top-1 fields are not treated as interchangeable.
        """
        payload: dict[str, Any] = {}
        table4 = metrics.get("table4")
        if isinstance(table4, dict):
            payload["table4"] = table4

        diagnostics = {
            name: value
            for name, value in metrics.items()
            if name != "table4"
        }
        if diagnostics:
            payload["diagnostics_internal"] = diagnostics

        payload["metric_definitions"] = {
            "paper_canonical_top1": "table4.12class_Top1 (multi-label paper alignment)",
            "diagnostics_internal.diagnosis.top1_accuracy": (
                "primary == first gold (single-label, deprecated for paper citation)"
            ),
            "diagnostics_internal.pilot_comparison_top1": (
                "parent(primary) == parent(first gold) (single-label parent)"
            ),
        }
        return payload

    def _save_summary_markdown(self, summary: MetricsSummary) -> None:
        """Write a short reviewer-friendly run summary."""
        lines = [
            f"# Run Summary: {self.run_id}",
            "",
            f"- Dataset: {summary.dataset}",
            f"- Cases: {summary.num_cases}",
            "",
            "## Metrics",
            "",
        ]

        if not summary.metrics:
            lines.append("No label-backed metrics were available.")
            lines.append("")
        else:
            for name, payload in summary.metrics.items():
                lines.append(f"### {name}")
                for metric_name, metric_value in payload.items():
                    if isinstance(metric_value, (int, float)):
                        lines.append(f"- {metric_name}: {metric_value:.4f}")
                    else:
                        lines.append(f"- {metric_name}: {metric_value}")
                lines.append("")

        if summary.slice_metrics:
            lines.append("## Slice Metrics")
            lines.append("")
            lines.append("| slice | cases | abstention_rate | top1_accuracy |")
            lines.append("|---|---:|---:|---:|")
            for item in summary.slice_metrics:
                top1 = item.get("top1_accuracy")
                top1_text = f"{top1:.4f}" if isinstance(top1, (int, float)) else "—"
                lines.append(
                    f"| {item['slice']} | {item['num_cases']} | "
                    f"{item['abstention_rate']:.4f} | {top1_text} |"
                )
            lines.append("")

        (self.output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    def _compute_slice_metrics(
        self,
        results: list[DiagnosisResult],
        cases: list[ClinicalCase],
    ) -> list[dict[str, Any]]:
        """Compute lightweight slice-aware reporting for common review slices.

        This is intentionally lightweight rather than a full stratified stats
        framework; it exists to flag obvious regime differences in reviewer
        summaries and regression checks.
        """
        somatic_terms = tuple(load_somatization_map().keys())
        transcript_texts = {
            case.case_id: " ".join(turn.text for turn in case.transcript)
            for case in cases
        }

        def _is_somatized(case: ClinicalCase) -> bool:
            if case.language != "zh":
                return False
            text = transcript_texts[case.case_id]
            return any(term in text for term in somatic_terms)

        slice_defs = {
            "F32": lambda c: "F32" in c.diagnoses,
            "F33": lambda c: "F33" in c.diagnoses,
            "F41.1": lambda c: "F41.1" in c.diagnoses,
            "F42": lambda c: "F42" in c.diagnoses,
            "F43.1": lambda c: "F43.1" in c.diagnoses,
            "F43.2": lambda c: "F43.2" in c.diagnoses,
            "somatized_expression": _is_somatized,
            "direct_expression": lambda c: c.language == "zh" and not _is_somatized(c),
            "short_case": lambda c: len(transcript_texts[c.case_id]) < 120,
        }

        slice_metrics: list[dict[str, Any]] = []
        for slice_name, predicate in slice_defs.items():
            pairs = [(result, case) for result, case in zip(results, cases) if predicate(case)]
            if not pairs:
                continue

            abstain_count = sum(1 for result, _ in pairs if result.decision == "abstain")
            item: dict[str, Any] = {
                "slice": slice_name,
                "num_cases": len(pairs),
                "abstention_rate": abstain_count / len(pairs),
            }

            if any(case.diagnoses for _, case in pairs):
                preds = []
                golds = []
                for result, case in pairs:
                    pred_dx = [result.primary_diagnosis] if result.primary_diagnosis else ["unknown"]
                    pred_dx += result.comorbid_diagnoses
                    mapped_gold = map_code_list(case.diagnoses)
                    if not mapped_gold:
                        continue
                    preds.append(map_code_list(pred_dx))
                    golds.append(mapped_gold)
                if preds:
                    item["top1_accuracy"] = compute_diagnosis_metrics(preds, golds)["top1_accuracy"]

            slice_metrics.append(item)

        return slice_metrics

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _get_git_hash() -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

        return result.stdout.strip() if result.returncode == 0 else ""
