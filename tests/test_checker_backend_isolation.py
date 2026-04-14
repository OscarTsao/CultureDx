"""Tests for checker-specific backend isolation."""
from __future__ import annotations

from culturedx.core.models import ClinicalCase, Turn
from culturedx.modes.hied import HiEDMode


class FakeLLM:
    """Minimal fake LLM that records generate calls."""

    def __init__(self, model: str, responses: list[str] | None = None, max_concurrent: int = 1):
        self.model = model
        self.responses = list(responses or [])
        self.max_concurrent = max_concurrent
        self.call_count = 0

    def generate(self, prompt: str, **kwargs) -> str:
        self.call_count += 1
        if self.responses:
            return self.responses.pop(0)
        return "{}"

    def compute_prompt_hash(self, template_source: str) -> str:
        return f"{self.model}-hash"


def _make_case() -> ClinicalCase:
    return ClinicalCase(
        case_id="checker-backend-001",
        transcript=[
            Turn(speaker="doctor", text="哪里不舒服？", turn_id=1),
            Turn(speaker="patient", text="我最近总是心情低落，睡眠也很差。", turn_id=2),
            Turn(speaker="doctor", text="持续多久了？", turn_id=3),
            Turn(speaker="patient", text="有三个月了。", turn_id=4),
        ],
        language="zh",
        dataset="test",
    )


def _checker_response(criteria_met: int = 6) -> str:
    import json

    return json.dumps(
        {
            "criteria": [
                {
                    "criterion_id": f"A{i + 1}",
                    "status": "met" if i < criteria_met else "not_met",
                    "evidence": f"evidence-{i + 1}" if i < criteria_met else None,
                    "confidence": 0.9 if i < criteria_met else 0.2,
                }
                for i in range(9)
            ]
        }
    )


def test_hied_uses_checker_llm_for_checker_fanout():
    main_llm = FakeLLM("main-model")
    checker_llm = FakeLLM("checker-model", responses=[_checker_response()])
    mode = HiEDMode(
        llm_client=main_llm,
        checker_llm_client=checker_llm,
        target_disorders=["F32"],
        abstain_threshold=0.1,
    )

    result = mode.diagnose(_make_case())

    assert main_llm.call_count == 0
    assert checker_llm.call_count == 1
    assert result.model_name == "main-model"
    assert result.checker_model_name == "checker-model"


def test_hied_contrastive_and_differential_stay_on_main_llm():
    main_llm = FakeLLM("main-model")
    checker_llm = FakeLLM("checker-model")
    mode = HiEDMode(
        llm_client=main_llm,
        checker_llm_client=checker_llm,
        contrastive_enabled=True,
    )

    assert mode.triage.llm is main_llm
    assert mode.differential.llm is main_llm
    assert mode.contrastive is not None
    assert mode.contrastive.llm is main_llm
    assert mode.checker.llm is checker_llm
