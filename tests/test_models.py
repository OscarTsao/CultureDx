# tests/test_models.py
"""Tests for core data models."""
import pytest
from culturedx.core.models import (
    Turn,
    ClinicalCase,
    SymptomSpan,
    CriterionEvidence,
    EvidenceBrief,
    CriterionResult,
    CheckerOutput,
    DiagnosisResult,
)


class TestTurn:
    def test_create_turn(self):
        t = Turn(speaker="doctor", text="How are you feeling?", turn_id=0)
        assert t.speaker == "doctor"
        assert t.turn_id == 0

    def test_turn_is_patient(self):
        t = Turn(speaker="patient", text="I feel sad", turn_id=1)
        assert t.is_patient is True
        t2 = Turn(speaker="doctor", text="Tell me more", turn_id=2)
        assert t2.is_patient is False


class TestClinicalCase:
    def test_create_clinical_case(self):
        turns = [
            Turn(speaker="doctor", text="How are you?", turn_id=0),
            Turn(speaker="patient", text="Not good", turn_id=1),
        ]
        case = ClinicalCase(
            case_id="test_001",
            transcript=turns,
            language="zh",
            dataset="mdd5k",
            transcript_format="dialogue",
            coding_system="icd10",
            diagnoses=["F32"],
            severity=None,
            comorbid=False,
            suicide_risk=None,
            metadata=None,
        )
        assert case.case_id == "test_001"
        assert case.language == "zh"
        assert len(case.transcript) == 2

    def test_patient_turns_only(self):
        turns = [
            Turn(speaker="doctor", text="Q1", turn_id=0),
            Turn(speaker="patient", text="A1", turn_id=1),
            Turn(speaker="doctor", text="Q2", turn_id=2),
            Turn(speaker="patient", text="A2", turn_id=3),
        ]
        case = ClinicalCase(
            case_id="t",
            transcript=turns,
            language="zh",
            dataset="mdd5k",
            transcript_format="dialogue",
            coding_system="icd10",
            diagnoses=["F32"],
        )
        patient_turns = case.patient_turns()
        assert len(patient_turns) == 2
        assert all(t.is_patient for t in patient_turns)

    def test_is_comorbid(self):
        case = ClinicalCase(
            case_id="t",
            transcript=[],
            language="zh",
            dataset="mdd5k",
            transcript_format="dialogue",
            coding_system="icd10",
            diagnoses=["F32", "F41.1"],
            comorbid=True,
        )
        assert case.comorbid is True
        assert len(case.diagnoses) == 2


class TestEvidenceBrief:
    def test_create_evidence_brief(self):
        evidence = CriterionEvidence(
            criterion_id="F32.A1",
            spans=[
                SymptomSpan(text="I feel sad", turn_id=1, symptom_type="mood"),
            ],
            confidence=0.85,
        )
        brief = EvidenceBrief(
            case_id="test_001",
            language="zh",
            criteria_evidence=[evidence],
        )
        assert len(brief.criteria_evidence) == 1
        assert brief.criteria_evidence[0].confidence == 0.85

    def test_empty_brief(self):
        brief = EvidenceBrief(case_id="t", language="en", criteria_evidence=[])
        assert len(brief.criteria_evidence) == 0


class TestDiagnosisResult:
    def test_diagnosis_with_confidence(self):
        result = DiagnosisResult(
            case_id="test_001",
            primary_diagnosis="F32",
            comorbid_diagnoses=["F41.1"],
            confidence=0.82,
            decision="diagnosis",
            criteria_results=[],
            mode="hied",
            model_name="qwen3:14b",
            language_used="zh",
        )
        assert result.decision == "diagnosis"
        assert result.confidence == 0.82
        assert result.comorbid_diagnoses == ["F41.1"]
        assert result.language_used == "zh"

    def test_abstain_result(self):
        result = DiagnosisResult(
            case_id="t",
            primary_diagnosis=None,
            comorbid_diagnoses=[],
            confidence=0.15,
            decision="abstain",
            criteria_results=[],
            mode="single",
            model_name="qwen3:14b",
        )
        assert result.decision == "abstain"
        assert result.primary_diagnosis is None
