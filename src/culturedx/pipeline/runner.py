"""Experiment runner: processes cases through a mode and emits canonical artifacts."""
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

from culturedx.core.models import ClinicalCase, DiagnosisResult
from culturedx.eval.metrics import compute_comorbidity_metrics, compute_diagnosis_metrics
from culturedx.evidence.pipeline import EvidencePipeline
from culturedx.modes.base import BaseModeOrchestrator
from culturedx.ontology.symptom_map import load_somatization_map
from culturedx.pipeline.artifacts import (
    MetricsSummary,
    RunManifest,
    build_failure_records,
    build_prediction_record,
    build_stage_timing_records,
    serialize_dataclass,
    stable_fingerprint,
)

logger = logging.getLogger(__name__)


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
        """Run the configured mode across cases with bounded concurrency."""
        if not cases:
            self._last_case_contexts = []
            self._save_predictions([])
            return []

        results: list[DiagnosisResult | None] = [None] * len(cases)
        evidences: list[Any] = [None] * len(cases)

        def _process_one(idx: int, case: ClinicalCase) -> tuple[int, Any, DiagnosisResult]:
            logger.info("Processing case %d/%d: %s", idx + 1, len(cases), case.case_id)
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
    ) -> None:
        """Save canonical and legacy run metadata."""
        manifest = RunManifest(
            run_id=self.run_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            git_hash=self._get_git_hash(),
            mode=mode_type,
            dataset=dataset_name,
            num_cases=num_cases,
            model_name=getattr(getattr(self.mode, "llm", None), "model", ""),
            config_fingerprint=stable_fingerprint(config_dict),
            config=config_dict,
        )
        self._last_manifest = manifest
        self._write_json(self.output_dir / "run_manifest.json", serialize_dataclass(manifest))

        legacy = {
            "timestamp": manifest.created_at,
            "git_hash": manifest.git_hash,
            "mode": manifest.mode,
            "dataset": manifest.dataset,
            "num_cases": manifest.num_cases,
            "config": config_dict,
            "config_fingerprint": manifest.config_fingerprint,
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
                    preds.append(pred_dx)
                    golds.append(c.diagnoses)
            metrics["diagnosis"] = compute_diagnosis_metrics(preds, golds)
            metrics["comorbidity"] = compute_comorbidity_metrics(preds, golds)

        slice_metrics = self._compute_slice_metrics(results, cases)
        summary = MetricsSummary(
            run_id=self.run_id,
            dataset=cases[0].dataset if cases else "",
            num_cases=len(cases),
            metrics=metrics,
            slice_metrics=slice_metrics,
        )
        self._save_metrics(metrics, summary)
        self._save_summary_markdown(summary)
        return metrics

    def _save_predictions(self, case_contexts: list[dict[str, Any]]) -> None:
        """Save canonical prediction, failure, and timing artifacts."""
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
        """Compute lightweight slice-aware reporting for common review slices."""
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
                    preds.append(pred_dx)
                    golds.append(case.diagnoses)
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
