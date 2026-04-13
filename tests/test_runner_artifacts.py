"""Tests for canonical runner artifacts."""
from __future__ import annotations

import json

from culturedx.core.models import ClinicalCase, DiagnosisResult, EvidenceBrief, FailureInfo, Turn
from culturedx.pipeline.runner import ExperimentRunner


class _FakeLLM:
    model = "stub-model"


class _StubMode:
    mode_name = "stub"
    llm = _FakeLLM()

    def diagnose(self, case: ClinicalCase, evidence: EvidenceBrief | None = None) -> DiagnosisResult:
        failures = []
        if evidence and evidence.failures:
            failures.extend(evidence.failures)
        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis="F32",
            confidence=0.8,
            decision="diagnosis",
            mode="stub",
            model_name="stub-model",
            language_used=case.language,
            candidate_disorders=["F32", "F41.1"],
            routing_mode="benchmark_manual_scope",
            scope_policy="manual",
            stage_timings={"logic_engine": 0.01},
            failures=failures,
        )


class _StubEvidencePipeline:
    def extract(self, case: ClinicalCase) -> EvidenceBrief:
        return EvidenceBrief(
            case_id=case.case_id,
            language=case.language,
            scope_policy="manual",
            target_disorders=["F32", "F41.1"],
            failures=[
                FailureInfo(
                    code="evidence_extraction_failed",
                    stage="extractor",
                    message="synthetic failure",
                    recoverable=True,
                )
            ],
            stage_timings={"extract": 0.02, "total": 0.02},
        )


def _make_case(case_id: str = "runner-001", diagnoses: list[str] | None = None) -> ClinicalCase:
    return ClinicalCase(
        case_id=case_id,
        transcript=[Turn(speaker="patient", text="我很難過，也睡不好。", turn_id=1)],
        language="zh",
        dataset="test",
        diagnoses=diagnoses or ["F32"],
    )


class TestRunnerArtifacts:
    def test_runner_emits_canonical_artifacts(self, tmp_path):
        runner = ExperimentRunner(
            mode=_StubMode(),
            output_dir=tmp_path / "run",
            evidence_pipeline=_StubEvidencePipeline(),
        )
        cases = [_make_case()]

        runner.save_run_info(
            config_dict={"mode": {"type": "stub"}},
            dataset_name="test",
            num_cases=1,
            mode_type="stub",
            case_ids=[case.case_id for case in cases],
            runtime_context={
                "config_paths": ["configs/base.yaml", "configs/hied.yaml"],
                "data_path": "tests/fixtures/mdd5k_sample.json",
                "split": None,
                "limit": None,
                "with_evidence": True,
                "seed": 42,
            },
        )
        results = runner.run(cases)
        metrics = runner.evaluate(results, cases)

        assert metrics["diagnosis"]["top1_accuracy"] >= 0.0
        assert (tmp_path / "run" / "run_manifest.json").exists()
        assert (tmp_path / "run" / "run_info.json").exists()
        assert (tmp_path / "run" / "case_selection.json").exists()
        assert (tmp_path / "run" / "predictions.jsonl").exists()
        assert (tmp_path / "run" / "failures.jsonl").exists()
        assert (tmp_path / "run" / "stage_timings.jsonl").exists()
        assert (tmp_path / "run" / "metrics_summary.json").exists()
        assert (tmp_path / "run" / "summary.md").exists()

        prediction = json.loads((tmp_path / "run" / "predictions.jsonl").read_text(encoding="utf-8").splitlines()[0])
        assert prediction["schema_version"] == "v1"
        assert prediction["case_id"] == "runner-001"
        assert prediction["candidate_disorders"] == ["F32", "F41.1"]
        assert "diagnosis_total" in prediction["stage_timings"]

        failure = json.loads((tmp_path / "run" / "failures.jsonl").read_text(encoding="utf-8").splitlines()[0])
        assert failure["code"] == "evidence_extraction_failed"
        assert failure["source"] == "evidence"

        manifest = json.loads((tmp_path / "run" / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["config_fingerprint"]
        assert manifest["case_selection_fingerprint"]
        assert manifest["runtime_context"]["seed"] == 42

        case_selection = json.loads((tmp_path / "run" / "case_selection.json").read_text(encoding="utf-8"))
        assert case_selection["case_ids"] == ["runner-001"]
        assert case_selection["case_order_fingerprint"] == manifest["case_selection_fingerprint"]

        metrics_summary = json.loads((tmp_path / "run" / "metrics_summary.json").read_text(encoding="utf-8"))
        assert metrics_summary["schema_version"] == "v1"
        assert metrics_summary["slice_metrics"]
