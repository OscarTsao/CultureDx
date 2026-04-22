"""Tests for HiED dual-standard reasoning configuration."""
from __future__ import annotations

import logging

import pytest

from culturedx.modes.hied import HiEDMode
from culturedx.ontology.standards import DiagnosticStandard


class _FakeLLM:
    def __init__(self) -> None:
        self.model = "test-model"

    def generate(self, prompt: str, **kwargs) -> str:
        return "{}"

    def compute_prompt_hash(self, template_source: str) -> str:
        return "test-hash"


def test_default_reasoning_standard_is_icd10() -> None:
    mode = HiEDMode(llm_client=_FakeLLM(), prompt_variant="v2")

    assert mode.reasoning_standard == "icd10"
    assert mode._standards == [DiagnosticStandard.ICD10]


def test_dsm5_mode_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        mode = HiEDMode(
            llm_client=_FakeLLM(),
            prompt_variant="v2",
            reasoning_standard="dsm5",
        )

    assert mode._standards == [DiagnosticStandard.DSM5]
    assert "DSM-5 reasoning is enabled" in caplog.text


def test_invalid_reasoning_standard_raises() -> None:
    with pytest.raises(ValueError, match="reasoning_standard"):
        HiEDMode(
            llm_client=_FakeLLM(),
            prompt_variant="v2",
            reasoning_standard="bad-standard",
        )


def test_both_mode_has_two_standards() -> None:
    mode = HiEDMode(
        llm_client=_FakeLLM(),
        prompt_variant="v2",
        reasoning_standard="both",
    )

    assert mode.reasoning_standard == "both"
    assert mode._standards == [
        DiagnosticStandard.ICD10,
        DiagnosticStandard.DSM5,
    ]
