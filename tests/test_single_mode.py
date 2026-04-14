# tests/test_single_mode.py
"""Tests for single-model baseline mode."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from jinja2 import DictLoader, Environment
from culturedx.modes.single import SingleModelMode
from culturedx.core.models import ClinicalCase, Turn


_MOCK_TEMPLATES = {
    "zero_shot_zh.jinja": "{{ transcript_text }}",
    "zero_shot_en.jinja": "{{ transcript_text }}",
}


@pytest.fixture
def mock_llm():
    client = MagicMock()
    client.model = "test-model"
    client.max_tokens = 256
    client.context_window = 1024
    client.compute_prompt_hash.return_value = "abc123"
    return client


@pytest.fixture
def mock_mode(mock_llm):
    """SingleModelMode with in-memory templates (no filesystem dependency)."""
    mode = SingleModelMode.__new__(SingleModelMode)
    mode.llm = mock_llm
    mode.prompts_dir = Path("prompts/single")
    mode._env = Environment(loader=DictLoader(_MOCK_TEMPLATES))
    mode.mode_name = "single"
    return mode


class TestSingleModelMode:
    def test_diagnose_zh(self, mock_llm, sample_case_zh, mock_mode):
        mock_llm.generate.return_value = '{"primary_diagnosis": "F32", "confidence": 0.8}'
        result = mock_mode.diagnose(sample_case_zh)
        assert result.case_id == "test_zh_001"
        assert result.primary_diagnosis == "F32"
        assert result.mode == "single"
        assert result.language_used == "zh"
        mock_llm.generate.assert_called_once()

    def test_diagnose_en(self, mock_llm, sample_case_en, mock_mode):
        mock_llm.generate.return_value = '{"primary_diagnosis": "F32", "confidence": 0.7}'
        result = mock_mode.diagnose(sample_case_en)
        assert result.language_used == "en"

    def test_diagnose_parse_failure(self, mock_llm, sample_case_zh, mock_mode):
        mock_llm.generate.return_value = "I cannot diagnose this patient."
        result = mock_mode.diagnose(sample_case_zh)
        assert result.decision == "abstain"
        assert result.primary_diagnosis is None

    def test_diagnose_truncates_prompt_for_small_context(self, mock_llm, mock_mode):
        long_case = ClinicalCase(
            case_id="long-001",
            transcript=[
                Turn(speaker="doctor", text="start", turn_id=1),
                Turn(speaker="patient", text="症状描述" * 2000, turn_id=2),
                Turn(speaker="doctor", text="end", turn_id=3),
            ],
            language="zh",
            dataset="test",
        )
        mock_llm.generate.return_value = '{"primary_diagnosis": "F32", "confidence": 0.8}'

        mock_mode.diagnose(long_case)

        prompt = mock_llm.generate.call_args.kwargs.get("prompt") or mock_llm.generate.call_args.args[0]
        assert prompt
        assert len(prompt) < len("doctor: start\npatient: " + ("症状描述" * 2000) + "\ndoctor: end\n")
