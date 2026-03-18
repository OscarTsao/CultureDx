"""Tests for evidence-enhanced single model mode."""
import json
from unittest.mock import MagicMock
from pathlib import Path

import pytest
from jinja2 import DictLoader, Environment

from culturedx.core.models import (
    ClinicalCase,
    CriterionEvidence,
    DisorderEvidence,
    EvidenceBrief,
    SymptomSpan,
    Turn,
)
from culturedx.modes.single import SingleModelMode


_MOCK_TEMPLATES = {
    "zero_shot_zh.jinja": (
        "{% for turn in transcript %}{{ turn.speaker }}: {{ turn.text }}\n{% endfor %}"
    ),
    "zero_shot_en.jinja": (
        "{% for turn in transcript %}{{ turn.speaker }}: {{ turn.text }}\n{% endfor %}"
    ),
    "zero_shot_evidence_zh.jinja": (
        "EVIDENCE MODE\n"
        "{% for turn in transcript %}{{ turn.speaker }}: {{ turn.text }}\n{% endfor %}"
        "{% for de in evidence.disorder_evidence %}{{ de.disorder_code }}{% endfor %}"
    ),
    "zero_shot_evidence_en.jinja": (
        "EVIDENCE MODE\n"
        "{% for turn in transcript %}{{ turn.speaker }}: {{ turn.text }}\n{% endfor %}"
        "{% for de in evidence.disorder_evidence %}{{ de.disorder_code }}{% endfor %}"
    ),
}


@pytest.fixture
def mock_llm():
    client = MagicMock()
    client.model = "test-model"
    client.compute_prompt_hash.return_value = "abc123"
    client.generate.return_value = json.dumps({
        "primary_diagnosis": "F32",
        "confidence": 0.85,
    })
    return client


@pytest.fixture
def mock_mode(mock_llm):
    mode = SingleModelMode.__new__(SingleModelMode)
    mode.llm = mock_llm
    mode.prompts_dir = Path("prompts/single")
    mode._env = Environment(loader=DictLoader(_MOCK_TEMPLATES))
    return mode


def _make_case(lang: str = "zh") -> ClinicalCase:
    return ClinicalCase(
        case_id="ev_test_001",
        transcript=[
            Turn(speaker="doctor", text="你好", turn_id=0),
            Turn(speaker="patient", text="情绪低落", turn_id=1),
        ],
        language=lang,
        dataset="test",
    )


def _make_evidence() -> EvidenceBrief:
    return EvidenceBrief(
        case_id="ev_test_001",
        language="zh",
        disorder_evidence=[
            DisorderEvidence(
                disorder_code="F32",
                disorder_name="Depressive episode",
                criteria_evidence=[
                    CriterionEvidence(
                        criterion_id="F32.B1",
                        spans=[
                            SymptomSpan(
                                text="情绪低落",
                                turn_id=1,
                                symptom_type="emotional",
                            )
                        ],
                        confidence=0.9,
                    ),
                ],
            ),
        ],
    )


class TestSingleEvidenceMode:
    def test_with_evidence_uses_evidence_template(self, mock_mode, mock_llm):
        result = mock_mode.diagnose(_make_case(), evidence=_make_evidence())
        # The prompt should have been rendered with evidence template
        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0]
        assert "F32" in prompt
        assert result.primary_diagnosis == "F32"

    def test_without_evidence_uses_base_template(self, mock_mode, mock_llm):
        result = mock_mode.diagnose(_make_case(), evidence=None)
        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0]
        assert "EVIDENCE MODE" not in prompt

    def test_empty_evidence_uses_base_template(self, mock_mode, mock_llm):
        empty_evidence = EvidenceBrief(
            case_id="ev_test_001",
            language="zh",
            disorder_evidence=[],  # Empty
        )
        result = mock_mode.diagnose(_make_case(), evidence=empty_evidence)
        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0]
        assert "EVIDENCE MODE" not in prompt
