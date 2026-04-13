"""Tests for HiED Diagnose-then-Verify mode."""
from __future__ import annotations

import json

from culturedx.core.models import ClinicalCase, EvidenceBrief, Turn
from culturedx.modes.hied import HiEDMode


class DiagnosticianLLM:
    """Fake LLM for diagnostician prompts."""

    def __init__(self, response: str) -> None:
        self.model = "diagnostician-model"
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        return self.response

    @staticmethod
    def compute_prompt_hash(template_source: str) -> str:
        return "diag-hash"


class CheckerLLM:
    """Thread-safe fake checker LLM keyed by disorder code in the prompt."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.model = "checker-model"
        self.responses = responses
        self.prompts: list[str] = []

    def generate(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        for disorder_code, response in self.responses.items():
            if disorder_code in prompt:
                return response
        return "{}"

    @staticmethod
    def compute_prompt_hash(template_source: str) -> str:
        return "checker-hash"


def make_case(case_id: str = "dtv-001", *, long_text: bool = False) -> ClinicalCase:
    transcript = [
        Turn(speaker="doctor", text="你好，今天来看什么问题？", turn_id=1),
        Turn(speaker="patient", text="我一直很担心，坐立不安，影响工作。", turn_id=2),
    ]
    if long_text:
        for idx in range(3, 403):
            speaker = "patient" if idx % 2 == 1 else "doctor"
            text = (
                "我每天都很担心未来，注意力也很差，还会反复想工作的事情。"
                if speaker == "patient"
                else "这些担心和紧张的情况对你的生活、睡眠和工作影响如何？"
            )
            transcript.append(Turn(speaker=speaker, text=text, turn_id=idx))
    transcript.extend(
        [
            Turn(
                speaker="doctor",
                text="这些症状持续多久了？",
                turn_id=len(transcript) + 1,
            ),
            Turn(
                speaker="patient",
                text="已经很久了，也有些情绪低落。",
                turn_id=len(transcript) + 2,
            ),
        ]
    )
    return ClinicalCase(
        case_id=case_id,
        transcript=transcript,
        language="zh",
        dataset="test",
    )


def make_checker_response(disorder: str, criteria_met: int, total: int) -> str:
    from culturedx.ontology.icd10 import get_disorder_criteria

    real_criteria = get_disorder_criteria(disorder)
    real_ids = list(real_criteria.keys()) if real_criteria else []
    while len(real_ids) < total:
        real_ids.append(f"X{len(real_ids)}")
    real_ids = real_ids[:total]

    criteria = []
    for idx, criterion_id in enumerate(real_ids):
        status = "met" if idx < criteria_met else "not_met"
        criteria.append(
            {
                "criterion_id": criterion_id,
                "status": status,
                "evidence": criterion_id if status == "met" else None,
                "confidence": 0.9 if status == "met" else 0.2,
            }
        )
    return json.dumps({"criteria": criteria})


def test_dtv_promotes_confirmed_second_choice():
    diagnostician_llm = DiagnosticianLLM(
        json.dumps(
            {
                "ranked_diagnoses": [
                    {"code": "F32", "reasoning": "mood symptoms appear possible"},
                    {"code": "F41.1", "reasoning": "anxiety is more coherent overall"},
                    {"code": "F42", "reasoning": "less likely"},
                ]
            }
        )
    )
    checker_llm = CheckerLLM(
        {
            "F32": make_checker_response("F32", 1, 9),
            "F41.1": make_checker_response("F41.1", 4, 6),
            "F42": make_checker_response("F42", 2, 5),
        }
    )
    mode = HiEDMode(
        llm_client=diagnostician_llm,
        checker_llm_client=checker_llm,
        target_disorders=["F32", "F41.1", "F42"],
        diagnose_then_verify=True,
    )

    result = mode.diagnose(make_case())

    assert result.decision == "diagnosis"
    assert result.primary_diagnosis == "F41.1"
    assert result.candidate_disorders == ["F32", "F41.1", "F42"]
    assert result.decision_trace["dtv_mode"] is True
    assert result.decision_trace["diagnostician_ranked"] == ["F32", "F41.1", "F42"]
    assert result.decision_trace["verify_codes"] == ["F32", "F41.1"]
    assert result.decision_trace["veto_applied"] is True
    assert result.decision_trace["veto_from"] == "F32"
    assert result.decision_trace["veto_to"] == "F41.1"
    assert set(result.decision_trace["logic_engine_confirmed_codes"]) == {"F41.1"}
    assert {co.disorder for co in result.criteria_results} == {"F32", "F41.1", "F42"}


def test_dtv_uses_full_transcript_for_diagnostician_with_evidence():
    diagnostician_llm = DiagnosticianLLM(
        json.dumps(
            {
                "ranked_diagnoses": [
                    {"code": "F41.1", "reasoning": "best fit"},
                    {"code": "F32", "reasoning": "second"},
                ]
            }
        )
    )
    checker_llm = CheckerLLM(
        {
            "F32": make_checker_response("F32", 1, 9),
            "F41.1": make_checker_response("F41.1", 4, 6),
        }
    )
    mode = HiEDMode(
        llm_client=diagnostician_llm,
        checker_llm_client=checker_llm,
        target_disorders=["F32", "F41.1"],
        diagnose_then_verify=True,
    )
    case = make_case(long_text=True)
    evidence = EvidenceBrief(case_id=case.case_id, language=case.language)

    result = mode.diagnose(case, evidence=evidence)

    assert result.primary_diagnosis == "F41.1"
    assert diagnostician_llm.prompts
    assert checker_llm.prompts
    assert len(diagnostician_llm.prompts[0]) > len(checker_llm.prompts[0]) + 5000
