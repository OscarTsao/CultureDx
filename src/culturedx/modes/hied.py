"""HiED-MAS: Hierarchical Evidence-grounded Diagnostic pipeline.

5-stage pipeline:
  Stage 1: Triage → broad ICD-10 categories
  Stage 2: Criterion Checkers → per-disorder criteria evaluation
  Stage 2.5: Contrastive Disambiguation → shared criteria attribution (optional)
  Stage 3: Logic Engine → deterministic ICD-10 threshold checking
  Stage 4: Calibrator → statistical confidence scoring + abstention
"""
from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from culturedx.agents.base import AgentInput
from culturedx.agents.criterion_checker import CriterionCheckerAgent
from culturedx.agents.differential import DifferentialDiagnosisAgent
from culturedx.agents.triage import TriageAgent
from culturedx.core.models import (
    CheckerOutput,
    ClinicalCase,
    DiagnosisResult,
    EvidenceBrief,
)
from culturedx.diagnosis.calibrator import ConfidenceCalibrator
from culturedx.diagnosis.pairwise_ranker import PairwiseRanker
from culturedx.diagnosis.comorbidity import ComorbidityResolver
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine
from culturedx.modes.base import BaseModeOrchestrator
from culturedx.ontology.icd10 import get_disorder_name

logger = logging.getLogger(__name__)


class HiEDMode(BaseModeOrchestrator):
    """Hierarchical Evidence-grounded Diagnostic MAS.

    Primary mode implementing the 5-stage pipeline:
    1. Triage: classify into broad ICD-10 categories
    2. Criterion Checkers: per-disorder ICD-10 criteria evaluation
    2.5. Contrastive Disambiguation: shared criteria attribution (optional)
    3. Logic Engine: deterministic threshold checking (no LLM)
    4. Calibrator: statistical confidence + abstention (no LLM)
    """

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
        target_disorders: list[str] | None = None,
        abstain_threshold: float = 0.3,
        comorbid_threshold: float = 0.5,
        differential_threshold: float = 0.10,
        contrastive_enabled: bool = False,
        ranker_weights_path: str | Path | None = None,
    ) -> None:
        self.mode_name = "hied"
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self.target_disorders = target_disorders

        # Stage 1: Triage
        self.triage = TriageAgent(llm_client, prompts_dir)

        # Stage 2: Criterion Checkers (one per disorder, reuse single agent)
        self.checker = CriterionCheckerAgent(llm_client, prompts_dir)

        # Stage 2.5: Contrastive disambiguation (optional)
        self.contrastive_enabled = contrastive_enabled
        self.contrastive = None
        if self.contrastive_enabled:
            from culturedx.agents.contrastive_checker import ContrastiveCheckerAgent
            self.contrastive = ContrastiveCheckerAgent(llm_client, prompts_dir)

        # Stage 3: Logic Engine (deterministic)
        self.logic_engine = DiagnosticLogicEngine()

        # Stage 4: Calibrator (statistical)
        self.calibrator = ConfidenceCalibrator(
            abstain_threshold=abstain_threshold,
            comorbid_threshold=comorbid_threshold,
        )

        # Stage 4.5: Differential disambiguation (for close calls)
        self.differential = DifferentialDiagnosisAgent(llm_client, prompts_dir)
        self.differential_threshold = differential_threshold

        # Stage 4b: Comorbidity resolver
        self.comorbidity_resolver = ComorbidityResolver()

        # Stage 4a: Pairwise re-ranking (optional, no LLM)
        self.pairwise_ranker: PairwiseRanker | None = None
        if ranker_weights_path is not None:
            self.pairwise_ranker = PairwiseRanker(ranker_weights_path)
            logger.info("Pairwise ranker loaded from %s", ranker_weights_path)

    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        lang = case.language
        if lang not in ("zh", "en"):
            return self._abstain(case, lang)

        # When evidence is provided, transcript is supplementary — reduce budget
        max_chars = 8000 if evidence else 20000
        transcript_text = self._build_transcript_text(case, max_chars=max_chars)
        evidence_map = self._build_evidence_map(evidence) if evidence else {}

        # === Stage 1: Triage ===
        if self.target_disorders is not None:
            # Skip triage when target disorders are explicitly set
            candidate_codes = list(self.target_disorders)
            logger.info("Skipping triage, using %d target disorders", len(candidate_codes))
        else:
            triage_input = AgentInput(
                transcript_text=transcript_text,
                evidence={"evidence_summary": self._build_global_evidence_summary(evidence)} if evidence else None,
                language=lang,
            )
            triage_output = self.triage.run(triage_input)
            if triage_output.parsed and "disorder_codes" in triage_output.parsed:
                candidate_codes = triage_output.parsed["disorder_codes"]
            else:
                logger.warning("Triage failed for case %s, using all disorders", case.case_id)
                from culturedx.ontology.icd10 import list_disorders
                candidate_codes = list_disorders()

        if not candidate_codes:
            return self._abstain(case, lang)

        logger.info("Case %s: %d candidate disorders from triage", case.case_id, len(candidate_codes))

        # === Stage 2: Criterion Checkers (parallel) ===
        checker_outputs = self._parallel_check_criteria(
            self.checker, candidate_codes, transcript_text, evidence_map, lang,
        )

        if not checker_outputs:
            return self._abstain(case, lang, criteria_results=[])

        # === Stage 2.5: Contrastive Disambiguation ===
        if self.contrastive_enabled and self.contrastive is not None:
            checker_outputs = self._run_contrastive(
                checker_outputs, transcript_text, lang,
            )

        # === Stage 3: Logic Engine (deterministic) ===
        logic_output = self.logic_engine.evaluate(checker_outputs)

        if not logic_output.confirmed:
            # No disorders meet thresholds
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                criteria_results=checker_outputs,
                mode=self.mode_name,
                model_name=self.llm.model,
                language_used=lang,
            )

        # === Stage 4: Calibrator (statistical) ===
        # Build confirmation type map from logic engine results
        confirmation_types = {
            r.disorder_code: r.confirmation_type
            for r in logic_output.confirmed
        }
        cal_output = self.calibrator.calibrate(
            confirmed_disorders=logic_output.confirmed_codes,
            checker_outputs=checker_outputs,
            evidence=evidence,
            confirmation_types=confirmation_types,
        )

        if cal_output.primary is None:
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                criteria_results=checker_outputs,
                mode=self.mode_name,
                model_name=self.llm.model,
                language_used=lang,
            )

        # === Stage 4a: Pairwise Re-ranking (optional, no LLM) ===
        if self.pairwise_ranker is not None:
            all_cal = [cal_output.primary] + cal_output.comorbid
            if len(all_cal) >= 2:
                codes = [c.disorder_code for c in all_cal]
                reranked_codes = self.pairwise_ranker.rerank(
                    codes, checker_outputs,
                )
                if reranked_codes[0] != codes[0]:
                    logger.info(
                        "Pairwise ranker reordered: %s -> %s",
                        codes, reranked_codes,
                    )
                    code_to_cal = {c.disorder_code: c for c in all_cal}
                    reranked_cal = [code_to_cal[c] for c in reranked_codes]
                    cal_output = replace(
                        cal_output,
                        primary=reranked_cal[0],
                        comorbid=reranked_cal[1:],
                    )

        # === Stage 4.5: Differential Disambiguation ===
        all_calibrated = [cal_output.primary] + cal_output.comorbid
        if len(all_calibrated) >= 2:
            gap = all_calibrated[0].confidence - all_calibrated[1].confidence
            if gap < self.differential_threshold:
                logger.info(
                    "Case %s: confidence gap %.4f < %.2f, running differential",
                    case.case_id, gap, self.differential_threshold,
                )
                diff_result = self._run_differential(
                    case, checker_outputs, logic_output, lang, transcript_text,
                )
                if diff_result is not None:
                    return diff_result
                logger.info("Differential inconclusive, falling back to calibrator")

        # === Stage 4b: Comorbidity Resolution ===
        # Build confidence map from calibrated scores
        confidences = {c.disorder_code: c.confidence for c in all_calibrated}
        confirmed_codes = [c.disorder_code for c in all_calibrated]

        comorbidity_result = self.comorbidity_resolver.resolve(
            confirmed=confirmed_codes,
            confidences=confidences,
        )

        # Find the calibrated diagnosis for the resolved primary
        primary_cal = next(
            (c for c in all_calibrated if c.disorder_code == comorbidity_result.primary),
            cal_output.primary,
        )

        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=comorbidity_result.primary,
            comorbid_diagnoses=comorbidity_result.comorbid,
            confidence=primary_cal.confidence,
            decision=primary_cal.decision,
            criteria_results=checker_outputs,
            mode=self.mode_name,
            model_name=self.llm.model,
            language_used=lang,
        )

    def _run_contrastive(
        self,
        checker_outputs: list[CheckerOutput],
        transcript_text: str,
        lang: str,
    ) -> list[CheckerOutput]:
        """Stage 2.5: Contrastive disambiguation of shared criteria."""
        from itertools import combinations

        from culturedx.ontology.shared_criteria import (
            apply_attributions_to_checker_output,
            get_shared_pairs,
        )

        # Build disorder -> CheckerOutput index
        co_index: dict[str, CheckerOutput] = {co.disorder: co for co in checker_outputs}

        # Find shared criteria that are both-met
        all_shared_pairs = []
        checker_evidence: dict[str, dict] = {}

        for d1, d2 in combinations(co_index.keys(), 2):
            pairs = get_shared_pairs(d1, d2)
            if not pairs:
                continue

            cr_a = {cr.criterion_id: cr for cr in co_index[d1].criteria}
            cr_b = {cr.criterion_id: cr for cr in co_index[d2].criteria}

            for pair in pairs:
                crit_a = cr_a.get(pair.criterion_a)
                crit_b = cr_b.get(pair.criterion_b)
                if (
                    crit_a
                    and crit_b
                    and crit_a.status == "met"
                    and crit_b.status == "met"
                ):
                    all_shared_pairs.append(pair)
                    key_a = f"{pair.disorder_a}_{pair.criterion_a}"
                    key_b = f"{pair.disorder_b}_{pair.criterion_b}"
                    checker_evidence[key_a] = {
                        "status": crit_a.status,
                        "evidence": crit_a.evidence,
                        "confidence": crit_a.confidence,
                    }
                    checker_evidence[key_b] = {
                        "status": crit_b.status,
                        "evidence": crit_b.evidence,
                        "confidence": crit_b.confidence,
                    }

        if not all_shared_pairs:
            return checker_outputs

        # Collect disorder names for prompt
        disorder_names = {}
        for pair in all_shared_pairs:
            for code in (pair.disorder_a, pair.disorder_b):
                if code not in disorder_names:
                    disorder_names[code] = get_disorder_name(code, lang) or code

        # Call contrastive agent
        agent_input = AgentInput(
            transcript_text=transcript_text,
            language=lang,
            extra={
                "shared_pairs": all_shared_pairs,
                "checker_evidence": checker_evidence,
                "disorder_names": disorder_names,
            },
        )

        output = self.contrastive.run(agent_input)

        # Graceful fallback on failure
        if not output.parsed or not output.parsed.get("attributions"):
            logger.info("Contrastive agent returned no attributions, skipping")
            return checker_outputs

        # Build deduped attribution map: (disorder, criterion_id) -> (confidence, target)
        attribution_map: dict[tuple[str, str], tuple[float, str]] = {}
        pair_by_domain = {p.symptom_domain: p for p in all_shared_pairs}

        for attr in output.parsed["attributions"]:
            domain = attr["symptom_domain"]
            pair = pair_by_domain.get(domain)
            if not pair:
                continue
            conf = attr["attribution_confidence"]
            target = attr["primary_attribution"]

            for disorder, criterion_id in [
                (pair.disorder_a, pair.criterion_a),
                (pair.disorder_b, pair.criterion_b),
            ]:
                key = (disorder, criterion_id)
                if key not in attribution_map or conf > attribution_map[key][0]:
                    attribution_map[key] = (conf, target)

        # Apply attributions to each affected CheckerOutput
        result = []
        for co in checker_outputs:
            if any(k[0] == co.disorder for k in attribution_map):
                result.append(apply_attributions_to_checker_output(co, attribution_map))
            else:
                result.append(co)

        logger.info(
            "Contrastive: %d shared pairs evaluated, %d attributions applied",
            len(all_shared_pairs),
            len(attribution_map),
        )
        return result

    def _run_differential(
        self,
        case: ClinicalCase,
        checker_outputs: list[CheckerOutput],
        logic_output,
        lang: str,
        transcript_text: str,
    ) -> DiagnosisResult | None:
        """Run differential diagnosis to disambiguate close-confidence disorders."""
        confirmed_set = set(logic_output.confirmed_codes)
        confirmed_checker_outputs = [
            co for co in checker_outputs if co.disorder in confirmed_set
        ]
        disorder_names = {
            code: get_disorder_name(code, lang) or code
            for code in confirmed_set
        }
        diff_input = AgentInput(
            transcript_text=transcript_text,
            language=lang,
            extra={
                "checker_outputs": confirmed_checker_outputs,
                "case_id": case.case_id,
                "disorder_names": disorder_names,
            },
        )
        diff_output = self.differential.run(diff_input)

        if not diff_output.parsed or not diff_output.parsed.get("primary_diagnosis"):
            return None

        primary = diff_output.parsed["primary_diagnosis"]
        if primary not in confirmed_set:
            logger.warning(
                "Differential returned %s not in confirmed set %s",
                primary, confirmed_set,
            )
            return None

        comorbid = diff_output.parsed.get("comorbid_diagnoses", [])
        confidence = diff_output.parsed.get("confidence", 0.0)

        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=primary,
            comorbid_diagnoses=[c for c in comorbid if c in confirmed_set],
            confidence=confidence,
            decision="diagnosis",
            criteria_results=checker_outputs,
            mode=self.mode_name,
            model_name=self.llm.model,
            language_used=lang,
        )
