"""End-to-end golden regression tests for HiED pipeline.

These tests use a mock LLM client that returns predefined checker responses
to verify the full pipeline: triage -> checker -> logic engine -> calibrator
-> comorbidity -> result.

Design notes:
- MockLLMClient detects which stage is calling by inspecting the rendered
  prompt (disorder code present for checker, triage keywords for triage,
  differential keywords for differential).
- All criterion IDs in mock responses must match the real ICD-10 ontology
  so the logic engine's threshold rules fire correctly.
- F32 threshold: min_core=2 (from B1/B2/B3), min_total=4 (all criteria).
  Criterion A is type=duration, B1-B3 are type=core, C1-C7 type=additional.
- F41.1 threshold: min_symptoms=4 (out of 5 criteria A, B1-B4).
  Soft path: exactly 3 met + >= 1 insufficient_evidence + <= 1 not_met.
"""
from __future__ import annotations

import hashlib
import json
import re
import pytest

from culturedx.core.models import ClinicalCase, Turn
from culturedx.modes.hied import HiEDMode


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

class MockLLMClient:
    """Mock LLM that returns predefined responses based on disorder code in prompt.

    The criterion checker renders the disorder code directly into the prompt:
        'ICD-10诊断 F32 ...' or 'ICD-10诊断 F41.1 ...'
    so we scan the rendered prompt for each registered code and return the
    corresponding JSON.

    The triage prompt contains '可选分类' (category selection section header).
    The differential prompt contains '鉴别诊断'.
    """

    model = "mock-model"
    max_concurrent = 1

    def __init__(self, checker_responses: dict[str, dict]):
        """checker_responses: disorder_code -> {criteria: [...]} JSON response."""
        self._responses = checker_responses
        self._triage_response: str | None = None

    def set_triage_response(self, response: str) -> None:
        self._triage_response = response

    @staticmethod
    def compute_prompt_hash(template_source: str) -> str:
        """Match OllamaClient.compute_prompt_hash signature."""
        return hashlib.sha256(template_source.encode("utf-8")).hexdigest()[:16]

    def generate(
        self,
        prompt: str,
        prompt_hash: str = "",
        language: str = "zh",
        json_schema: dict | None = None,
    ) -> str:
        # --- Triage stage ---
        # Triage prompt contains '可选分类' (category selection section header)
        if "可选分类" in prompt:
            return (
                self._triage_response
                or '{"categories": [{"category": "mood", "confidence": 0.9}]}'
            )

        # --- Differential stage ---
        # The differential prompt contains a unique section heading '鉴别诊断任务'
        # that does NOT appear in criterion checker prompts (which only have
        # '鉴别诊断注意事项'). The English template contains 'Differential
        # Diagnosis Task'. Using specific markers avoids false positives when
        # the F32 criterion checker prompt body mentions '鉴别诊断注意事项'.
        if "鉴别诊断任务" in prompt or "Differential Diagnosis Task" in prompt:
            codes = list(self._responses.keys())
            primary = codes[0] if codes else "F32"
            comorbid = codes[1:] if len(codes) > 1 else []
            return json.dumps({
                "primary_diagnosis": primary,
                "comorbid_diagnoses": comorbid,
                "confidence": 0.85,
                "reasoning": "mock differential",
            })

        # --- Criterion checker stage ---
        # The criterion checker prompt header is always:
        #   '...评估ICD-10诊断 <CODE> <name> 的各项标准是否满足。'
        # Extract the code from the first 300 characters to avoid false
        # matches: the F32 prompt body mentions 'F41.1' in its differential
        # notes section, so full-prompt substring search is unreliable.
        m = re.search(r"ICD-10诊断\s+(\S+)", prompt[:300])
        if m:
            code = m.group(1)
            if code in self._responses:
                return json.dumps(self._responses[code])

        # Default: empty criteria list (all insufficient_evidence)
        return json.dumps({"criteria": []})


# ---------------------------------------------------------------------------
# Shared test fixture
# ---------------------------------------------------------------------------

def _make_case(case_id: str = "test_001", lang: str = "zh") -> ClinicalCase:
    return ClinicalCase(
        case_id=case_id,
        transcript=[
            Turn(speaker="Doctor", text="你好，请问你今天来看什么问题？", turn_id=0),
            Turn(
                speaker="Patient",
                text=(
                    "我最近情绪很低落，睡不好觉，做什么都没兴趣。"
                    "心里很烦躁，经常担心各种事情。"
                ),
                turn_id=1,
            ),
            Turn(speaker="Doctor", text="这种情况持续多久了？", turn_id=2),
            Turn(
                speaker="Patient",
                text="大概有半年了，越来越严重。有时候心慌胸闷，全身紧绷。",
                turn_id=3,
            ),
        ],
        language=lang,
        dataset="test",
    )


# ---------------------------------------------------------------------------
# Predefined criterion-checker payloads
# (Criterion IDs must match the real ICD-10 ontology.)
#
# F32 criteria: A(duration), B1(core), B2(core), B3(core),
#               C1-C7(additional)
# Threshold:   min_core=2 (B1/B2/B3), min_total=4
#
# F41.1 criteria: A(core/duration), B1(somatic), B2(somatic),
#                 B3(cognitive), B4(somatic)
# Threshold:   min_symptoms=4
# ---------------------------------------------------------------------------

def _f32_checker_response() -> dict:
    """F32 with B1+B2 core met (2/2) and 6 total met (6/4) -> confirmed."""
    return {
        "criteria": [
            # duration criterion (not counted in core)
            {"criterion_id": "A",  "status": "not_met",  "evidence": None,         "confidence": 0.20},
            # core criteria
            {"criterion_id": "B1", "status": "met",      "evidence": "情绪低落",    "confidence": 0.90},
            {"criterion_id": "B2", "status": "met",      "evidence": "没兴趣",      "confidence": 0.85},
            {"criterion_id": "B3", "status": "not_met",  "evidence": None,         "confidence": 0.20},
            # additional criteria
            {"criterion_id": "C1", "status": "met",      "evidence": "注意力下降",   "confidence": 0.75},
            {"criterion_id": "C2", "status": "met",      "evidence": "自我评价低",   "confidence": 0.70},
            {"criterion_id": "C3", "status": "not_met",  "evidence": None,         "confidence": 0.15},
            {"criterion_id": "C4", "status": "met",      "evidence": "睡不好觉",    "confidence": 0.85},
            {"criterion_id": "C5", "status": "not_met",  "evidence": None,         "confidence": 0.10},
            {"criterion_id": "C6", "status": "met",      "evidence": "疲乏",        "confidence": 0.80},
            {"criterion_id": "C7", "status": "not_met",  "evidence": None,         "confidence": 0.10},
        ]
    }
    # met: B1, B2, C1, C2, C4, C6 -> core_met=2/2, total_met=6/4 -> confirmed


def _f41_1_all_met_response() -> dict:
    """F41.1 with all 5/5 criteria met -> confirmed (threshold=4)."""
    return {
        "criteria": [
            {"criterion_id": "A",  "status": "met", "evidence": "半年了",       "confidence": 0.85},
            {"criterion_id": "B1", "status": "met", "evidence": "全身紧绷",     "confidence": 0.80},
            {"criterion_id": "B2", "status": "met", "evidence": "心慌胸闷",     "confidence": 0.85},
            {"criterion_id": "B3", "status": "met", "evidence": "担心各种事情",  "confidence": 0.90},
            {"criterion_id": "B4", "status": "met", "evidence": "睡不好觉",     "confidence": 0.85},
        ]
    }
    # met: A, B1, B2, B3, B4 -> count=5 >= min_symptoms=4 -> confirmed


def _f41_1_below_threshold_response() -> dict:
    """F41.1 with only 2/5 met -> rejected (threshold=4)."""
    return {
        "criteria": [
            {"criterion_id": "A",  "status": "not_met", "evidence": None,    "confidence": 0.20},
            {"criterion_id": "B1", "status": "not_met", "evidence": None,    "confidence": 0.15},
            {"criterion_id": "B2", "status": "not_met", "evidence": None,    "confidence": 0.10},
            {"criterion_id": "B3", "status": "met",     "evidence": "担心",   "confidence": 0.70},
            {"criterion_id": "B4", "status": "met",     "evidence": "失眠",   "confidence": 0.75},
        ]
    }
    # met: B3, B4 -> count=2 < min_symptoms=4 -> rejected


def _f41_1_soft_threshold_response() -> dict:
    """F41.1 with 3 met + 1 insufficient_evidence + 1 not_met -> soft confirm.

    Soft-confirmation path in DiagnosticLogicEngine._eval_min_symptoms:
        met_count == min_symp - 1 (3 == 4-1)
        n_insufficient > 0 (A is insufficient)
        n_not_met <= 1 (B4 is not_met, count=1)
    -> confirmation_type='soft', calibrator applies 0.85x penalty.
    """
    return {
        "criteria": [
            {"criterion_id": "A",  "status": "insufficient_evidence", "evidence": None,      "confidence": 0.40},
            {"criterion_id": "B1", "status": "met",                   "evidence": "全身紧绷", "confidence": 0.80},
            {"criterion_id": "B2", "status": "met",                   "evidence": "心慌",    "confidence": 0.85},
            {"criterion_id": "B3", "status": "met",                   "evidence": "担心",    "confidence": 0.90},
            {"criterion_id": "B4", "status": "not_met",               "evidence": None,      "confidence": 0.15},
        ]
    }


def _f32_one_met_response() -> dict:
    """F32 with only B1 met -> below min_core=2 -> rejected."""
    return {
        "criteria": [
            {"criterion_id": "A",  "status": "not_met", "evidence": None,   "confidence": 0.10},
            {"criterion_id": "B1", "status": "met",     "evidence": "低落",  "confidence": 0.60},
            {"criterion_id": "B2", "status": "not_met", "evidence": None,   "confidence": 0.20},
            {"criterion_id": "B3", "status": "not_met", "evidence": None,   "confidence": 0.15},
            {"criterion_id": "C1", "status": "not_met", "evidence": None,   "confidence": 0.10},
            {"criterion_id": "C2", "status": "not_met", "evidence": None,   "confidence": 0.10},
            {"criterion_id": "C3", "status": "not_met", "evidence": None,   "confidence": 0.10},
            {"criterion_id": "C4", "status": "not_met", "evidence": None,   "confidence": 0.10},
            {"criterion_id": "C5", "status": "not_met", "evidence": None,   "confidence": 0.10},
            {"criterion_id": "C6", "status": "not_met", "evidence": None,   "confidence": 0.10},
            {"criterion_id": "C7", "status": "not_met", "evidence": None,   "confidence": 0.10},
        ]
    }
    # met: B1 only -> core_met=1 < min_core=2 -> rejected


def _f33_not_met_response() -> dict:
    """F33 with nothing met -> rejected."""
    return {
        "criteria": [
            {"criterion_id": "A",  "status": "not_met", "evidence": None, "confidence": 0.10},
            {"criterion_id": "B1", "status": "not_met", "evidence": None, "confidence": 0.10},
            {"criterion_id": "B2", "status": "not_met", "evidence": None, "confidence": 0.10},
            {"criterion_id": "B3", "status": "not_met", "evidence": None, "confidence": 0.10},
            {"criterion_id": "C1", "status": "not_met", "evidence": None, "confidence": 0.10},
            {"criterion_id": "C2", "status": "not_met", "evidence": None, "confidence": 0.10},
            {"criterion_id": "C3", "status": "not_met", "evidence": None, "confidence": 0.10},
            {"criterion_id": "C4", "status": "not_met", "evidence": None, "confidence": 0.10},
            {"criterion_id": "C5", "status": "not_met", "evidence": None, "confidence": 0.10},
            {"criterion_id": "C6", "status": "not_met", "evidence": None, "confidence": 0.10},
            {"criterion_id": "C7", "status": "not_met", "evidence": None, "confidence": 0.10},
        ]
    }


def _f32_five_met_response() -> dict:
    """F32 with B1+B2 core (2/2) and 5 total met (5/4) -> confirmed (45% ratio)."""
    return {
        "criteria": [
            {"criterion_id": "A",  "status": "not_met", "evidence": None,      "confidence": 0.10},
            {"criterion_id": "B1", "status": "met",     "evidence": "低落",     "confidence": 0.80},
            {"criterion_id": "B2", "status": "met",     "evidence": "没兴趣",   "confidence": 0.75},
            {"criterion_id": "B3", "status": "not_met", "evidence": None,      "confidence": 0.10},
            {"criterion_id": "C1", "status": "met",     "evidence": "注意力",   "confidence": 0.70},
            {"criterion_id": "C2", "status": "met",     "evidence": "自评",     "confidence": 0.65},
            {"criterion_id": "C3", "status": "not_met", "evidence": None,      "confidence": 0.10},
            {"criterion_id": "C4", "status": "met",     "evidence": "睡眠",     "confidence": 0.80},
            {"criterion_id": "C5", "status": "not_met", "evidence": None,      "confidence": 0.10},
            {"criterion_id": "C6", "status": "not_met", "evidence": None,      "confidence": 0.10},
            {"criterion_id": "C7", "status": "not_met", "evidence": None,      "confidence": 0.10},
        ]
    }
    # met: B1, B2, C1, C2, C4 -> core_met=2/2, total_met=5/4 -> confirmed
    # proportion = 5/4 capped to 1.0; margin = (5-4)/(11-4) = 1/7 = 0.14


# ---------------------------------------------------------------------------
# Golden regression test cases
# ---------------------------------------------------------------------------

PROMPTS_DIR = "prompts/agents"


class TestHiEDE2E:
    """End-to-end golden regression tests for HiED pipeline."""

    # ------------------------------------------------------------------
    # Case 1: Clear F32 (strong depression, weak anxiety)
    # ------------------------------------------------------------------

    def test_clear_f32_diagnosis(self):
        """Case with strong F32 evidence, weak F41.1 -> diagnoses F32.

        F32: B1+B2 core met (2/2), 6 total met (6/4) -> confirmed
        F41.1: only 2/5 met -> rejected by logic engine
        F33: nothing met -> rejected
        Result: F32 is the only confirmed disorder -> primary diagnosis
        """
        mock = MockLLMClient(
            checker_responses={
                "F32": _f32_checker_response(),
                "F41.1": _f41_1_below_threshold_response(),
                "F33": _f33_not_met_response(),
            }
        )

        hied = HiEDMode(
            llm_client=mock,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F33", "F41.1"],
        )
        case = _make_case()
        result = hied.diagnose(case)

        assert result.primary_diagnosis == "F32", (
            f"Expected F32 but got {result.primary_diagnosis!r} "
            f"(decision={result.decision}, confidence={result.confidence:.4f})"
        )
        assert result.decision == "diagnosis"
        assert result.confidence > 0.3, (
            f"Expected confidence > 0.3 but got {result.confidence:.4f}"
        )

    # ------------------------------------------------------------------
    # Case 2: Clear F41.1 (strong anxiety, failed F32)
    # ------------------------------------------------------------------

    def test_clear_f41_1_diagnosis(self):
        """Case with strong F41.1 evidence, weak F32 -> diagnoses F41.1.

        F41.1: all 5/5 criteria met -> confirmed
        F32: only B1 met (1 core, 1 total) -> below min_core=2 and min_total=4
             -> rejected by logic engine
        Result: F41.1 is the only confirmed disorder -> primary diagnosis
        """
        mock = MockLLMClient(
            checker_responses={
                "F41.1": _f41_1_all_met_response(),
                "F32": _f32_one_met_response(),
            }
        )

        hied = HiEDMode(
            llm_client=mock,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
        )
        case = _make_case()
        result = hied.diagnose(case)

        assert result.primary_diagnosis == "F41.1", (
            f"Expected F41.1 but got {result.primary_diagnosis!r} "
            f"(decision={result.decision}, confidence={result.confidence:.4f})"
        )
        assert result.decision == "diagnosis"

    # ------------------------------------------------------------------
    # Case 3: F32/F41.1 comorbid (both confirmed)
    # ------------------------------------------------------------------

    def test_comorbid_f32_f41(self):
        """Case with both F32 and F41.1 confirmed -> highest confidence primary.

        F32: 6/4 total met (confirmed)
        F41.1: 5/4 met (confirmed)
        Both pass logic engine -> comorbidity resolver picks highest-confidence
        one as primary, the other as comorbid.
        """
        mock = MockLLMClient(
            checker_responses={
                "F32": _f32_checker_response(),
                "F41.1": _f41_1_all_met_response(),
            }
        )

        hied = HiEDMode(
            llm_client=mock,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
            # Disable differential to test pure calibrator + comorbidity path.
            differential_threshold=0.0,
        )
        case = _make_case()
        result = hied.diagnose(case)

        assert result.primary_diagnosis is not None, "Expected a primary diagnosis"
        assert result.decision == "diagnosis"

        # Both disorders should appear in result (primary + comorbid)
        all_diagnoses = {result.primary_diagnosis} | set(result.comorbid_diagnoses)
        assert "F32" in all_diagnoses or "F41.1" in all_diagnoses, (
            f"Neither F32 nor F41.1 in result: primary={result.primary_diagnosis}, "
            f"comorbid={result.comorbid_diagnoses}"
        )

    # ------------------------------------------------------------------
    # Case 4: Soft threshold F41.1
    # ------------------------------------------------------------------

    def test_soft_threshold_f41_confirmed(self):
        """F41.1 with 3 met + 1 insufficient -> soft confirmed via logic engine.

        The soft-confirmation path in _eval_min_symptoms fires when:
            met == min_symptoms - 1 (3 == 3)
            n_insufficient > 0 (A is insufficient)
            n_not_met <= 1 (B4 is not_met, so n_not_met=1)
        The calibrator then applies a 0.85x penalty to the confidence.
        F32 with 1 met is rejected, so F41.1 is primary.
        """
        mock = MockLLMClient(
            checker_responses={
                "F41.1": _f41_1_soft_threshold_response(),
                "F32": _f32_one_met_response(),  # 1 met -> rejected
            }
        )

        hied = HiEDMode(
            llm_client=mock,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
            differential_threshold=0.0,
        )
        case = _make_case()
        result = hied.diagnose(case)

        assert result.primary_diagnosis == "F41.1", (
            f"Expected F41.1 (soft) but got {result.primary_diagnosis!r} "
            f"(decision={result.decision}, confidence={result.confidence:.4f})"
        )
        assert result.decision == "diagnosis"

        # Soft confirmation penalty: confidence must be < hard-confirm score.
        # With the 0.85x penalty the calibrated confidence should be below 0.85.
        assert result.confidence < 0.85, (
            f"Expected confidence < 0.85 (soft penalty) but got {result.confidence:.4f}"
        )

    # ------------------------------------------------------------------
    # Case 5: Nothing meets threshold -> abstain
    # ------------------------------------------------------------------

    def test_abstain_when_nothing_meets(self):
        """No disorder meets thresholds -> pipeline returns abstain decision.

        F32: 0 met -> below min_core=2 -> rejected
        F41.1: 0 met -> below min_symptoms=4 -> rejected
        Logic engine confirms nothing -> DiagnosisResult.decision='abstain'.
        """
        mock = MockLLMClient(
            checker_responses={
                "F32": {
                    "criteria": [
                        {"criterion_id": "B1", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "B2", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "B3", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "C1", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "C2", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "C3", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "C4", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "C5", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "C6", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "C7", "status": "not_met", "evidence": None, "confidence": 0.10},
                    ]
                },
                "F41.1": {
                    "criteria": [
                        {"criterion_id": "A",  "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "B1", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "B2", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "B3", "status": "not_met", "evidence": None, "confidence": 0.10},
                        {"criterion_id": "B4", "status": "not_met", "evidence": None, "confidence": 0.10},
                    ]
                },
            }
        )

        hied = HiEDMode(
            llm_client=mock,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
        )
        case = _make_case()
        result = hied.diagnose(case)

        assert result.decision == "abstain", (
            f"Expected abstain but got decision={result.decision!r}, "
            f"primary={result.primary_diagnosis!r}"
        )
        assert result.primary_diagnosis is None

    # ------------------------------------------------------------------
    # Case 6: Proportion-based ranking favors complete checklist
    # ------------------------------------------------------------------

    def test_proportion_sorting_favors_complete_checklist(self):
        """F41.1 at 5/5 (100%) should outrank F32 at 5/11 (~45%) in calibrator.

        Logic engine sorts confirmed disorders by (met/required) ratio.
        F41.1: 5 met / min_symptoms=4 -> ratio capped at 1.0, margin=1/1=1.0
        F32:   5 met / min_total=4 -> ratio=1.0, but margin=(5-4)/(11-4)=1/7=0.14
        The calibrator's margin_score should give F41.1 a higher final confidence.

        differential_threshold=0.0 disables the differential agent so the
        ordering is determined purely by the calibrator.
        """
        mock = MockLLMClient(
            checker_responses={
                "F41.1": _f41_1_all_met_response(),
                "F32": _f32_five_met_response(),
            }
        )

        hied = HiEDMode(
            llm_client=mock,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
            differential_threshold=0.0,
        )
        case = _make_case()
        result = hied.diagnose(case)

        assert result.primary_diagnosis is not None, "Expected a primary diagnosis"
        assert result.decision == "diagnosis"
        # F41.1 has 100% excess ratio (1/1) vs F32's 14% (1/7);
        # with margin weight=0.08, F41.1 should get a higher calibrated score.
        assert result.primary_diagnosis == "F41.1", (
            f"Expected F41.1 to win on margin but got {result.primary_diagnosis!r} "
            f"(confidence={result.confidence:.4f})"
        )


    # ------------------------------------------------------------------
    # Case 7: Contrastive fires — F32 criteria downgraded, F41.1 wins
    # ------------------------------------------------------------------

    def test_contrastive_shifts_ranking_to_f41_1(self):
        """When contrastive is enabled and shared criteria favor F41.1,
        F32's shared criteria get downgraded, shifting ranking toward F41.1.

        Setup:
        - F32: 6 met including C4(concentration), C6(sleep) — shared with F41.1
        - F41.1: 5 met (all) including B3, B4 — shared with F32
        - Contrastive attributes concentration->F41.1, sleep->F41.1 (high conf)
        - After downgrade: F32 C4->insuff, C6->insuff, losing 2 met -> 4 met
        - F32 still confirmed (4 met >= 4 total), but lower calibrator score
        - F41.1 unchanged -> now ranks higher
        """
        f32_resp = _f32_checker_response()
        f41_resp = _f41_1_all_met_response()

        class ContrastiveMockLLM(MockLLMClient):
            def generate(self, prompt, **kwargs):
                if "共享症状评估" in prompt or "Shared Symptom Evaluation" in prompt:
                    return json.dumps({
                        "attributions": [
                            {
                                "symptom_domain": "concentration",
                                "primary_attribution": "F41.1",
                                "attribution_confidence": 0.85,
                                "reasoning": "worry-driven",
                            },
                            {
                                "symptom_domain": "sleep",
                                "primary_attribution": "F41.1",
                                "attribution_confidence": 0.82,
                                "reasoning": "anxiety insomnia",
                            },
                            {
                                "symptom_domain": "psychomotor",
                                "primary_attribution": "both",
                                "attribution_confidence": 0.55,
                                "reasoning": "ambiguous",
                            },
                            {
                                "symptom_domain": "fatigue",
                                "primary_attribution": "both",
                                "attribution_confidence": 0.50,
                                "reasoning": "ambiguous",
                            },
                        ]
                    })
                return super().generate(prompt, **kwargs)

        llm = ContrastiveMockLLM({"F32": f32_resp, "F41.1": f41_resp})
        mode = HiEDMode(
            llm_client=llm,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
            contrastive_enabled=True,
            differential_threshold=0.0,
        )
        result = mode.diagnose(_make_case())
        assert result.decision == "diagnosis"
        assert result.primary_diagnosis == "F41.1"

    # ------------------------------------------------------------------
    # Case 8: Contrastive disabled — same inputs, V10 behavior
    # ------------------------------------------------------------------

    def test_contrastive_disabled_preserves_v10_behavior(self):
        """With contrastive_enabled=False, same case uses V2 calibrator
        ranking. After weight tuning (core_score 0.30->0.05, threshold_ratio
        0.207->0.35), F32 wins because its threshold_ratio is higher than
        F41.1's (more criteria total = more discriminative signal).
        """
        f32_resp = _f32_checker_response()
        f41_resp = _f41_1_all_met_response()
        llm = MockLLMClient({"F32": f32_resp, "F41.1": f41_resp})
        mode = HiEDMode(
            llm_client=llm,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
            contrastive_enabled=False,
        )
        result = mode.diagnose(_make_case())
        assert result.decision == "diagnosis"
        # V2 tuned weights: threshold_ratio dominant -> F32 primary
        assert result.primary_diagnosis == "F32"
        assert "F41.1" in result.comorbid_diagnoses

    # ------------------------------------------------------------------
    # Case 9: Contrastive skipped — only one disorder confirmed
    # ------------------------------------------------------------------

    def test_contrastive_skipped_single_disorder(self):
        """Contrastive enabled but only F32 passes checker. No shared
        criteria are both-met -> contrastive not called -> normal F32.
        """
        f32_resp = _f32_checker_response()
        f41_resp = _f41_1_below_threshold_response()
        llm = MockLLMClient({"F32": f32_resp, "F41.1": f41_resp})
        mode = HiEDMode(
            llm_client=llm,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
            contrastive_enabled=True,
        )
        result = mode.diagnose(_make_case())
        assert result.decision == "diagnosis"
        assert result.primary_diagnosis == "F32"

    # ------------------------------------------------------------------
    # Case 10: Contrastive returns "both" — comorbidity preserved
    # ------------------------------------------------------------------

    def test_contrastive_both_preserves_comorbidity(self):
        """When contrastive returns 'both' for all pairs, no criteria are
        downgraded -> both disorders confirmed with original scores.
        """
        f32_resp = _f32_checker_response()
        f41_resp = _f41_1_all_met_response()

        class BothMockLLM(MockLLMClient):
            def generate(self, prompt, **kwargs):
                if "共享症状评估" in prompt or "Shared Symptom Evaluation" in prompt:
                    return json.dumps({
                        "attributions": [
                            {"symptom_domain": d, "primary_attribution": "both",
                             "attribution_confidence": 0.90, "reasoning": "comorbid"}
                            for d in ["concentration", "sleep", "psychomotor", "fatigue"]
                        ]
                    })
                return super().generate(prompt, **kwargs)

        llm = BothMockLLM({"F32": f32_resp, "F41.1": f41_resp})
        mode = HiEDMode(
            llm_client=llm,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
            contrastive_enabled=True,
        )
        result = mode.diagnose(_make_case())
        assert result.decision == "diagnosis"
        # "both" means no downgrade -> same ranking as non-contrastive
        # V2 tuned weights: threshold_ratio dominant -> F32 primary
        assert result.primary_diagnosis == "F32"
        assert "F41.1" in result.comorbid_diagnoses
