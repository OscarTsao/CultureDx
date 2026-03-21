# src/culturedx/pipeline/runner.py
"""Experiment runner: processes cases through a mode and evaluates."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from culturedx.core.models import ClinicalCase, DiagnosisResult
from culturedx.eval.metrics import compute_comorbidity_metrics, compute_diagnosis_metrics
from culturedx.evidence.pipeline import EvidencePipeline
from culturedx.modes.base import BaseModeOrchestrator

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Run a mode on a list of cases and collect results."""

    def __init__(
        self,
        mode: BaseModeOrchestrator,
        output_dir: str | Path,
        evidence_pipeline: "EvidencePipeline | None" = None,
    ) -> None:
        self.mode = mode
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_pipeline = evidence_pipeline

    @staticmethod
    def create_run_dir(
        base_dir: str | Path,
        mode_type: str,
        dataset_name: str,
    ) -> Path:
        """Create a timestamped run directory.
        
        Returns path like: base_dir/mas_lingxidiag16k_20260318_210500/
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        name = f"{mode_type}_{dataset_name}_{ts}"
        run_dir = Path(base_dir) / name
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def run(self, cases: list[ClinicalCase]) -> list[DiagnosisResult]:
        results = []
        for i, case in enumerate(cases):
            logger.info("Processing case %d/%d: %s", i + 1, len(cases), case.case_id)
            evidence = None
            if self.evidence_pipeline is not None:
                evidence = self.evidence_pipeline.extract(case)
            result = self.mode.diagnose(case, evidence=evidence)
            results.append(result)
        self._save_predictions(results)
        return results

    def save_run_info(
        self,
        config_dict: dict,
        dataset_name: str,
        num_cases: int,
        mode_type: str,
    ) -> None:
        """Save experiment metadata to run_info.json."""
        import subprocess
        
        git_hash = ""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                git_hash = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        info = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_hash": git_hash,
            "mode": mode_type,
            "dataset": dataset_name,
            "num_cases": num_cases,
            "config": config_dict,
        }
        path = self.output_dir / "run_info.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2, ensure_ascii=False)

    def evaluate(
        self, results: list[DiagnosisResult], cases: list[ClinicalCase]
    ) -> dict:
        """Evaluate results against ground truth."""
        if len(results) != len(cases):
            raise ValueError(
                f"results ({len(results)}) and cases ({len(cases)}) must have same length"
            )
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

            # Comorbidity metrics (multi-label evaluation)
            comorbid_metrics = compute_comorbidity_metrics(preds, golds)
            metrics["comorbidity"] = comorbid_metrics

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
