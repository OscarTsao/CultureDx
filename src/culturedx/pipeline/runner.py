# src/culturedx/pipeline/runner.py
"""Experiment runner: processes cases through a mode and evaluates."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from culturedx.core.models import ClinicalCase, DiagnosisResult
from culturedx.eval.metrics import compute_diagnosis_metrics
from culturedx.modes.base import BaseModeOrchestrator

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Run a mode on a list of cases and collect results."""

    def __init__(
        self,
        mode: BaseModeOrchestrator,
        output_dir: str | Path,
    ) -> None:
        self.mode = mode
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, cases: list[ClinicalCase]) -> list[DiagnosisResult]:
        results = []
        for i, case in enumerate(cases):
            logger.info("Processing case %d/%d: %s", i + 1, len(cases), case.case_id)
            result = self.mode.diagnose(case)
            results.append(result)
        self._save_predictions(results)
        return results

    def evaluate(
        self, results: list[DiagnosisResult], cases: list[ClinicalCase]
    ) -> dict:
        """Evaluate results against ground truth."""
        metrics = {}

        # Diagnosis metrics (if cases have diagnoses)
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

        # Severity metrics deferred to Phase 2 — requires structured severity output
        # from LLM, not available in single-model baseline.

        self._save_metrics(metrics)
        return metrics

    def _save_predictions(self, results: list[DiagnosisResult]) -> None:
        path = self.output_dir / "predictions.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")

    def _save_metrics(self, metrics: dict) -> None:
        path = self.output_dir / "metrics.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
