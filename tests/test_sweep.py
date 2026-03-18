"""Tests for sweep runner."""
from __future__ import annotations

import json
import pytest

from culturedx.core.models import ClinicalCase, DiagnosisResult, Turn
from culturedx.pipeline.sweep import (
    SweepCondition,
    SweepRunner,
    build_ablation_conditions,
)


def make_case() -> ClinicalCase:
    return ClinicalCase(
        case_id="test-001",
        transcript=[Turn(speaker="doctor", text="hi", turn_id=1)],
        language="zh",
        dataset="test",
    )


class TestBuildAblationConditions:
    def test_default_modes(self):
        conditions = build_ablation_conditions()
        names = [c.name for c in conditions]
        assert "hied_full" in names
        assert "single_full" in names
        assert "psycot_full" in names

    def test_evidence_ablation(self):
        conditions = build_ablation_conditions(modes=["hied"])
        names = [c.name for c in conditions]
        assert "hied_full" in names
        assert "hied_no_evidence" in names

    def test_somatization_ablation(self):
        conditions = build_ablation_conditions(modes=["hied"])
        names = [c.name for c in conditions]
        assert "hied_no_somatization" in names

    def test_single_no_somatization_ablation(self):
        """Single mode should not have somatization ablation."""
        conditions = build_ablation_conditions(modes=["single"])
        names = [c.name for c in conditions]
        assert "single_no_somatization" not in names

    def test_custom_modes(self):
        conditions = build_ablation_conditions(modes=["hied", "psycot"])
        mode_types = {c.mode_type for c in conditions}
        assert mode_types == {"hied", "psycot"}

    def test_no_ablation(self):
        conditions = build_ablation_conditions(
            modes=["hied"],
            evidence_ablation=False,
            somatization_ablation=False,
        )
        assert len(conditions) == 1
        assert conditions[0].name == "hied_full"


class TestSweepRunner:
    def test_dry_run(self, tmp_path):
        """Sweep without run_fn just creates directories."""
        runner = SweepRunner(base_output_dir=tmp_path)
        conditions = [
            SweepCondition(name="test_cond", mode_type="single"),
        ]
        cases = [make_case()]
        report = runner.run_sweep(conditions, cases, sweep_name="test")

        assert report.sweep_name == "test"
        assert len(report.results) == 1
        assert report.results[0].condition.name == "test_cond"

    def test_with_run_fn(self, tmp_path):
        """Sweep with run_fn captures metrics."""
        def fake_run(condition, cases):
            results = [
                DiagnosisResult(
                    case_id="test-001",
                    primary_diagnosis="F32",
                    confidence=0.8,
                    decision="diagnosis",
                )
            ]
            metrics = {"accuracy": 0.85, "macro_f1": 0.75}
            return results, metrics

        runner = SweepRunner(base_output_dir=tmp_path)
        conditions = [SweepCondition(name="full", mode_type="hied")]
        report = runner.run_sweep(conditions, [make_case()], run_fn=fake_run)

        assert report.results[0].metrics["accuracy"] == 0.85
        assert report.results[0].num_diagnosed == 1

    def test_report_saved_to_disk(self, tmp_path):
        runner = SweepRunner(base_output_dir=tmp_path)
        conditions = [SweepCondition(name="a", mode_type="single")]
        report = runner.run_sweep(conditions, [make_case()], sweep_name="save_test")

        # Find the sweep dir
        sweep_dirs = list(tmp_path.glob("save_test_*"))
        assert len(sweep_dirs) == 1
        report_file = sweep_dirs[0] / "sweep_report.json"
        assert report_file.exists()

    def test_to_dict(self):
        from culturedx.pipeline.sweep import SweepReport, SweepResult
        report = SweepReport(
            sweep_name="test",
            results=[SweepResult(
                condition=SweepCondition(name="a", mode_type="single"),
                num_cases=10,
                metrics={"acc": 0.9},
            )],
        )
        d = report.to_dict()
        assert d["sweep_name"] == "test"
        assert len(d["conditions"]) == 1
