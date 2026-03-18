"""Integration tests for the full diagnostic pipeline."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from culturedx.core.models import ClinicalCase, Turn
from culturedx.modes.mas import MASMode
from culturedx.pipeline.runner import ExperimentRunner


@dataclass
class MockLLM:
    """Mock LLM that returns disorder-specific responses."""
    model: str = "test-model"
    responses: dict = field(default_factory=dict)
    default_response: str = '{"criteria": []}'
    call_count: int = 0

    @staticmethod
    def compute_prompt_hash(text: str) -> str:
        return "testhash"

    def generate(self, prompt: str, prompt_hash: str = "", language: str = "zh") -> str:
        self.call_count += 1
        for key, response in self.responses.items():
            if key in prompt:
                return response
        return self.default_response


@pytest.fixture
def prompts_dir(tmp_path):
    """Create minimal Jinja templates for MAS agents."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "criterion_checker_en.jinja").write_text(
        "Evaluate {{ disorder_code }} {{ disorder_name }}\n"
        "{% for k, v in criteria.items() %}{{ k }}{% endfor %}\n"
        "{{ transcript_text }}\n"
        "{% if evidence_summary %}{{ evidence_summary }}{% endif %}\n"
    )
    (agents_dir / "criterion_checker_zh.jinja").write_text(
        "评估 {{ disorder_code }} {{ disorder_name }}\n"
        "{% for k, v in criteria.items() %}{{ k }}{% endfor %}\n"
        "{{ transcript_text }}\n"
        "{% if evidence_summary %}{{ evidence_summary }}{% endif %}\n"
    )
    (agents_dir / "differential_en.jinja").write_text(
        "Differential: {% for r in checker_results %}{{ r.disorder }}{% endfor %}\n"
        "{{ transcript_summary }}\n"
    )
    (agents_dir / "differential_zh.jinja").write_text(
        "鉴别: {% for r in checker_results %}{{ r.disorder }}{% endfor %}\n"
        "{{ transcript_summary }}\n"
    )
    return agents_dir


def _make_cases() -> list[ClinicalCase]:
    """Create test cases with ground truth diagnoses."""
    return [
        ClinicalCase(
            case_id="int-001",
            transcript=[
                Turn(speaker="doctor", text="What brings you here?", turn_id=0),
                Turn(speaker="patient", text="I feel very sad and have no energy.", turn_id=1),
                Turn(speaker="doctor", text="How long?", turn_id=2),
                Turn(speaker="patient", text="About a month now.", turn_id=3),
            ],
            language="en",
            dataset="test",
            diagnoses=["F32"],
        ),
        ClinicalCase(
            case_id="int-002",
            transcript=[
                Turn(speaker="doctor", text="Tell me about your symptoms.", turn_id=0),
                Turn(speaker="patient", text="I worry constantly and can't sleep.", turn_id=1),
            ],
            language="en",
            dataset="test",
            diagnoses=["F41.1"],
        ),
        ClinicalCase(
            case_id="int-003",
            transcript=[
                Turn(speaker="doctor", text="How are you?", turn_id=0),
                Turn(speaker="patient", text="I'm sad and anxious all the time.", turn_id=1),
            ],
            language="en",
            dataset="test",
            diagnoses=["F32", "F41.1"],
        ),
    ]


class TestPipelineIntegration:
    def test_mas_pipeline_end_to_end(self, prompts_dir, tmp_path):
        """Test full MAS pipeline: load -> diagnose -> evaluate -> save."""
        checker_resp = json.dumps({
            "criteria": [
                {"criterion_id": "B1", "status": "met", "evidence": "sad", "confidence": 0.9},
                {"criterion_id": "B3", "status": "met", "evidence": "no energy", "confidence": 0.8},
                {"criterion_id": "C1", "status": "met", "evidence": "worthless", "confidence": 0.7},
                {"criterion_id": "C6", "status": "met", "evidence": "insomnia", "confidence": 0.75},
            ]
        })
        diff_resp = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.85,
            "reasoning": "F32 meets threshold",
        })
        llm = MockLLM(responses={"Evaluate F32": checker_resp}, default_response=diff_resp)

        mode = MASMode(
            llm_client=llm,
            prompts_dir=prompts_dir,
            target_disorders=["F32"],
        )

        output_dir = tmp_path / "output"
        runner = ExperimentRunner(mode=mode, output_dir=output_dir)
        cases = _make_cases()

        # Run pipeline
        results = runner.run(cases)

        # Verify results
        assert len(results) == 3
        for r in results:
            assert r.mode == "mas"
            assert r.primary_diagnosis == "F32"

        # Verify predictions file
        pred_path = output_dir / "predictions.jsonl"
        assert pred_path.exists()
        lines = pred_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        first = json.loads(lines[0])
        assert first["case_id"] == "int-001"
        assert first["primary_diagnosis"] == "F32"

        # Evaluate
        metrics = runner.evaluate(results, cases)
        assert "diagnosis" in metrics
        assert metrics["diagnosis"]["top1_accuracy"] >= 0.0
        assert metrics["diagnosis"]["macro_f1"] >= 0.0

        # Verify metrics file
        metrics_path = output_dir / "metrics.json"
        assert metrics_path.exists()

    def test_pipeline_with_no_ground_truth(self, prompts_dir, tmp_path):
        """Test pipeline works when cases have no ground truth."""
        diff_resp = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.7,
            "reasoning": "test",
        })
        checker_resp = json.dumps({
            "criteria": [
                {"criterion_id": "B1", "status": "met", "evidence": "test", "confidence": 0.8},
            ]
        })
        llm = MockLLM(responses={"F32": checker_resp}, default_response=diff_resp)
        mode = MASMode(llm_client=llm, prompts_dir=prompts_dir, target_disorders=["F32"])

        cases = [
            ClinicalCase(
                case_id="nolabel-001",
                transcript=[Turn(speaker="patient", text="I feel down.", turn_id=0)],
                language="en",
                dataset="test",
                diagnoses=[],  # No ground truth
            )
        ]

        output_dir = tmp_path / "output_nolabel"
        runner = ExperimentRunner(mode=mode, output_dir=output_dir)
        results = runner.run(cases)

        assert len(results) == 1
        # Evaluate with no labels should give empty metrics
        metrics = runner.evaluate(results, cases)
        assert "diagnosis" not in metrics  # No labels, no diagnosis metrics

    def test_pipeline_abstain_cases(self, prompts_dir, tmp_path):
        """Test pipeline handles abstain decisions correctly."""
        diff_resp = json.dumps({
            "primary_diagnosis": None,
            "comorbid_diagnoses": [],
            "confidence": 0.2,
            "reasoning": "Insufficient evidence",
        })
        checker_resp = json.dumps({
            "criteria": [
                {"criterion_id": "B1", "status": "insufficient_evidence", "confidence": 0.1},
            ]
        })
        llm = MockLLM(responses={"F32": checker_resp}, default_response=diff_resp)
        mode = MASMode(llm_client=llm, prompts_dir=prompts_dir, target_disorders=["F32"])

        cases = [
            ClinicalCase(
                case_id="abstain-001",
                transcript=[Turn(speaker="patient", text="Hello.", turn_id=0)],
                language="en",
                dataset="test",
                diagnoses=["F32"],
            )
        ]

        output_dir = tmp_path / "output_abstain"
        runner = ExperimentRunner(mode=mode, output_dir=output_dir)
        results = runner.run(cases)

        assert results[0].decision == "abstain"
        assert results[0].primary_diagnosis is None

    def test_llm_called_expected_times(self, prompts_dir, tmp_path):
        """Test that LLM is called the expected number of times for MAS."""
        checker_resp = json.dumps({
            "criteria": [{"criterion_id": "A", "status": "met", "confidence": 0.8}]
        })
        diff_resp = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.8,
            "reasoning": "test",
        })
        llm = MockLLM(responses={"Evaluate F32": checker_resp, "Evaluate F41.1": checker_resp}, default_response=diff_resp)
        mode = MASMode(llm_client=llm, prompts_dir=prompts_dir, target_disorders=["F32", "F41.1"])

        cases = [_make_cases()[0]]  # 1 case
        output_dir = tmp_path / "output_calls"
        runner = ExperimentRunner(mode=mode, output_dir=output_dir)
        runner.run(cases)

        # 1 case × (2 checker calls + 1 differential call) = 3 LLM calls
        assert llm.call_count == 3
