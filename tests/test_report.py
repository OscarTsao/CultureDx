"""Tests for evaluation report generator."""
from __future__ import annotations

import json
import pytest

from culturedx.eval.report import (
    AblationTable,
    EvalReport,
    MetricComparison,
    ReportGenerator,
)


class TestReportGenerator:
    def test_from_sweep_report(self, tmp_path):
        """Generate report from a sweep result file."""
        sweep_data = {
            "sweep_name": "test_ablation",
            "conditions": [
                {
                    "name": "hied_full",
                    "mode_type": "hied",
                    "with_evidence": True,
                    "with_somatization": True,
                    "num_cases": 100,
                    "num_diagnosed": 85,
                    "num_abstained": 15,
                    "metrics": {"accuracy": 0.85, "macro_f1": 0.78},
                    "duration_sec": 120.5,
                    "output_dir": "/tmp/test",
                },
                {
                    "name": "single_full",
                    "mode_type": "single",
                    "with_evidence": True,
                    "with_somatization": True,
                    "num_cases": 100,
                    "num_diagnosed": 100,
                    "num_abstained": 0,
                    "metrics": {"accuracy": 0.72, "macro_f1": 0.65},
                    "duration_sec": 60.0,
                    "output_dir": "/tmp/test2",
                },
            ],
        }

        report_file = tmp_path / "sweep_report.json"
        report_file.write_text(json.dumps(sweep_data), encoding="utf-8")

        report = ReportGenerator.from_sweep_report(report_file)

        assert report.experiment_name == "test_ablation"
        assert len(report.comparisons) == 2
        # Best accuracy should be hied_full
        acc_comp = next(c for c in report.comparisons if c.metric_name == "accuracy")
        assert acc_comp.best_condition == "hied_full"
        assert acc_comp.best_value == 0.85

    def test_format_markdown(self):
        report = EvalReport(
            experiment_name="test",
            num_cases=50,
            comparisons=[
                MetricComparison(
                    metric_name="accuracy",
                    values={"a": 0.85, "b": 0.72},
                    best_condition="a",
                    best_value=0.85,
                ),
            ],
        )
        md = ReportGenerator.format_markdown(report)
        assert "# Evaluation Report: test" in md
        assert "accuracy" in md
        assert "0.8500" in md

    def test_format_json(self):
        report = EvalReport(experiment_name="test", num_cases=10)
        j = ReportGenerator.format_json(report)
        data = json.loads(j)
        assert data["experiment_name"] == "test"

    def test_save_both(self, tmp_path):
        report = EvalReport(experiment_name="test", num_cases=10)
        paths = ReportGenerator.save(report, tmp_path, fmt="both")
        assert len(paths) == 2
        assert (tmp_path / "report.md").exists()
        assert (tmp_path / "report.json").exists()

    def test_save_markdown_only(self, tmp_path):
        report = EvalReport(experiment_name="test")
        paths = ReportGenerator.save(report, tmp_path, fmt="markdown")
        assert len(paths) == 1
        assert paths[0].name == "report.md"

    def test_empty_sweep(self, tmp_path):
        sweep_data = {"sweep_name": "empty", "conditions": []}
        report_file = tmp_path / "empty.json"
        report_file.write_text(json.dumps(sweep_data), encoding="utf-8")

        report = ReportGenerator.from_sweep_report(report_file)
        assert report.experiment_name == "empty"
        assert len(report.comparisons) == 0
