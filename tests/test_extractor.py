"""Tests for symptom span extraction."""
import json
from unittest.mock import MagicMock

import pytest

from culturedx.core.models import ClinicalCase, Turn
from culturedx.evidence.extractor import SymptomExtractor


def _make_case(language: str = "zh") -> ClinicalCase:
    return ClinicalCase(
        case_id="test_ext_001",
        transcript=[
            Turn(speaker="doctor", text="你最近怎么样？", turn_id=0),
            Turn(speaker="patient", text="我头疼，晚上也睡不着", turn_id=1),
            Turn(speaker="doctor", text="还有其他不舒服吗？", turn_id=2),
            Turn(speaker="patient", text="情绪很低落，什么都不想做", turn_id=3),
        ],
        language=language,
        dataset="test",
    )


def _make_mock_llm(return_json: dict | str) -> MagicMock:
    mock = MagicMock()
    mock.compute_prompt_hash.return_value = "test_hash"
    if isinstance(return_json, dict):
        mock.generate.return_value = json.dumps(return_json, ensure_ascii=False)
    else:
        mock.generate.return_value = return_json
    return mock


class TestSymptomExtractor:
    def test_extract_symptoms_zh(self, tmp_path):
        # Write a minimal template
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "extract_symptoms_zh.jinja").write_text(
            "Extract symptoms from: {% for t in turns %}{{ t.text }} {% endfor %}",
            encoding="utf-8",
        )
        llm = _make_mock_llm({
            "symptoms": [
                {"text": "头疼", "turn_id": 1, "symptom_type": "somatic"},
                {"text": "睡不着", "turn_id": 1, "symptom_type": "somatic"},
            ]
        })
        extractor = SymptomExtractor(llm_client=llm, prompts_dir=str(prompts_dir))
        spans = extractor.extract(_make_case("zh"))
        assert len(spans) == 2
        assert spans[0].text == "头疼"
        assert spans[0].symptom_type == "somatic"
        assert spans[0].turn_id == 1

    def test_extract_symptoms_en(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "extract_symptoms_en.jinja").write_text(
            "Extract symptoms from: {% for t in turns %}{{ t.text }} {% endfor %}",
            encoding="utf-8",
        )
        case = ClinicalCase(
            case_id="test_en",
            transcript=[
                Turn(speaker="doctor", text="How are you?", turn_id=0),
                Turn(speaker="patient", text="I have headaches", turn_id=1),
            ],
            language="en",
            dataset="test",
        )
        llm = _make_mock_llm({
            "symptoms": [
                {"text": "headaches", "turn_id": 1, "symptom_type": "somatic"},
            ]
        })
        extractor = SymptomExtractor(llm_client=llm, prompts_dir=str(prompts_dir))
        spans = extractor.extract(case)
        assert len(spans) == 1
        assert spans[0].text == "headaches"

    def test_extract_handles_bad_json(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "extract_symptoms_zh.jinja").write_text(
            "Extract: {% for t in turns %}{{ t.text }}{% endfor %}",
            encoding="utf-8",
        )
        llm = _make_mock_llm("This is not JSON at all, sorry")
        extractor = SymptomExtractor(llm_client=llm, prompts_dir=str(prompts_dir))
        spans = extractor.extract(_make_case("zh"))
        assert spans == []

    def test_somatic_flag_set_for_somatic_type(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "extract_symptoms_zh.jinja").write_text(
            "Extract: {% for t in turns %}{{ t.text }}{% endfor %}",
            encoding="utf-8",
        )
        llm = _make_mock_llm({
            "symptoms": [
                {"text": "头疼", "turn_id": 1, "symptom_type": "somatic"},
                {"text": "情绪低落", "turn_id": 3, "symptom_type": "emotional"},
            ]
        })
        extractor = SymptomExtractor(llm_client=llm, prompts_dir=str(prompts_dir))
        spans = extractor.extract(_make_case("zh"))
        assert spans[0].is_somatic is True
        assert spans[1].is_somatic is False
