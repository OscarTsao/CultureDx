"""HiED-MAS: hierarchical evidence-grounded diagnosis orchestration.

This file owns the repo's main diagnosis path. It keeps two execution
semantics explicit:

- benchmark/manual scope: closed-set evaluation with explicit target disorders
- production/open-set: triage-driven or all-supported candidate resolution

The main ``diagnose()`` method is intentionally stage-shaped so contributors
can reason about failures, timings, and routing semantics at each boundary.
"""
from __future__ import annotations

import logging
import time
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
    FailureInfo,
)
from culturedx.diagnosis.calibrator import ConfidenceCalibrator
from culturedx.diagnosis.pairwise_ranker import PairwiseRanker
from culturedx.diagnosis.comorbidity import ComorbidityResolver
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine
from culturedx.modes.base import BaseModeOrchestrator
from culturedx.ontology.icd10 import get_disorder_name

logger = logging.getLogger(__name__)

SUPPORTED_SCOPE_POLICIES = frozenset({"auto", "manual", "triage", "all_supported"})
SUPPORTED_EXECUTION_MODES = frozenset({"auto", "benchmark_manual_scope", "production_open_set"})


class HiEDMode(BaseModeOrchestrator):
    """Primary evidence-grounded diagnosis orchestrator.

    ``HiEDMode`` is the main place where routing semantics, deterministic
    diagnosis logic, calibration, differential disambiguation, and comorbidity
    resolution are wired together for one case.
    """

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
        checker_llm_client=None,
        target_disorders: list[str] | None = None,
        scope_policy: str = "auto",
        execution_mode: str = "auto",
        diagnose_then_verify: bool = False,
        abstain_threshold: float = 0.3,
        comorbid_threshold: float = 0.5,
        differential_threshold: float = 0.10,
        contrastive_enabled: bool = False,
        ranker_weights_path: str | Path | None = None,
        comorbid_min_ratio: float = 0.9,
        prompt_variant: str = "",
        calibrator_mode: str = "heuristic-v2",
        calibrator_artifact_path: str | Path | None = None,
        force_prediction: bool = False,
        case_retriever=None,
    ) -> None:
        self.mode_name = "hied"
        self.llm = llm_client
        self.case_retriever = case_retriever
        self.checker_llm = checker_llm_client or llm_client
        self.checker_model_name = (
            getattr(checker_llm_client, "model", None)
            if checker_llm_client is not None
            else None
        )
        self.prompts_dir = Path(prompts_dir)
        self.target_disorders = target_disorders
        self.diagnose_then_verify = diagnose_then_verify
        self.prompt_variant = prompt_variant
        self.force_prediction = force_prediction
        if scope_policy not in SUPPORTED_SCOPE_POLICIES:
            raise ValueError(
                f"Unsupported HiED scope_policy {scope_policy!r}; "
                f"expected one of {sorted(SUPPORTED_SCOPE_POLICIES)}"
            )
        if execution_mode not in SUPPORTED_EXECUTION_MODES:
            raise ValueError(
                f"Unsupported HiED execution_mode {execution_mode!r}; "
                f"expected one of {sorted(SUPPORTED_EXECUTION_MODES)}"
            )
        self.scope_policy = scope_policy
        self.execution_mode = execution_mode

        # Stage 1: Triage
        self.triage = TriageAgent(llm_client, prompts_dir)

        # Stage 1.5: Diagnostician (DtV path)
        if self.diagnose_then_verify:
            from culturedx.agents.diagnostician import DiagnosticianAgent

            self.diagnostician = DiagnosticianAgent(llm_client, prompts_dir)
        else:
            self.diagnostician = None

        # Stage 2: Criterion Checkers (one per disorder, reuse single agent)
        self.checker = CriterionCheckerAgent(self.checker_llm, prompts_dir)

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
            mode=calibrator_mode,
            artifact_path=calibrator_artifact_path,
        )

        # Stage 4.5: Differential disambiguation (for close calls)
        self.differential = DifferentialDiagnosisAgent(llm_client, prompts_dir)
        self.differential_threshold = differential_threshold

        # Stage 4b: Comorbidity resolver
        self.comorbidity_resolver = ComorbidityResolver(
            comorbid_min_ratio=comorbid_min_ratio,
        )

        # Stage 4a: Pairwise re-ranking (optional, no LLM)
        self.pairwise_ranker: PairwiseRanker | None = None
        if ranker_weights_path is not None:
            self.pairwise_ranker = PairwiseRanker(ranker_weights_path)
            logger.info("Pairwise ranker loaded from %s", ranker_weights_path)

    @staticmethod
    def _build_evidence_map(evidence: EvidenceBrief) -> dict[str, str | dict[str, str]]:
        """Build checker payloads with per-disorder evidence and temporal wiring."""
        result: dict[str, str | dict[str, str]] = BaseModeOrchestrator._build_evidence_map(evidence)

        temporal_features = evidence.temporal_features
        if temporal_features is not None and hasattr(temporal_features, "summary_zh"):
            temporal_summary = temporal_features.summary_zh()
            if temporal_summary:
                existing = result.get("F41.1")
                if isinstance(existing, dict):
                    existing["temporal_summary"] = temporal_summary
                elif isinstance(existing, str):
                    result["F41.1"] = {
                        "evidence_summary": existing,
                        "temporal_summary": temporal_summary,
                    }
                else:
                    result["F41.1"] = {"temporal_summary": temporal_summary}
        return result

    @staticmethod
    def _build_raw_checker_outputs_trace(
        checker_outputs: list[CheckerOutput],
    ) -> list[dict[str, object]]:
        """Serialize checker outputs into audit-friendly trace records."""
        return [
            {
                "disorder_code": co.disorder,
                "criteria_met_count": co.criteria_met_count,
                "criteria_total_count": co.criteria_required,
                "met_ratio": (
                    co.criteria_met_count / co.criteria_required
                    if co.criteria_required > 0
                    else 0.0
                ),
                "per_criterion": [
                    {
                        "criterion_id": cr.criterion_id,
                        "status": cr.status,
                        "confidence": cr.confidence,
                        "evidence": cr.evidence or "",
                    }
                    for cr in co.criteria
                ],
            }
            for co in checker_outputs
        ]

    def _diagnose_then_verify(
        self,
        *,
        case: ClinicalCase,
        lang: str,
        transcript_text: str,
        evidence_map: dict[str, str | dict[str, str]],
        candidate_codes: list[str],
        routing_mode: str,
        scope_policy: str,
        decision_trace: dict[str, object],
        stage_timings: dict[str, float],
        failures: list[FailureInfo],
        case_start: float,
    ) -> DiagnosisResult:
        """Run the historical DtV flow: diagnostician rank then checker verify."""
        full_transcript = self._build_transcript_text(case, max_chars=20000)
        disorder_names = {
            code: get_disorder_name(code, lang) or code
            for code in candidate_codes
        }

        diag_start = time.monotonic()
        similar_cases = None
        if self.case_retriever is not None:
            try:
                if hasattr(self.case_retriever, "retrieve_balanced"):
                    similar_cases = self.case_retriever.retrieve_balanced(
                        full_transcript,
                        candidate_codes,
                        top_per_class=1,
                    )
                else:
                    similar_cases = self.case_retriever.retrieve(full_transcript, top_k=5)
                similar_cases = [
                    {
                        "similarity": sc["similarity"],
                        "diagnosis_code": (sc.get("diagnosis_codes") or ["?"])[0],
                        "diagnosis_name": (sc.get("diagnosis_names") or [""])[0],
                        "chief_complaint_summary": sc.get("transcript_preview", "")[:100],
                        "key_evidence": sc.get("key_evidence", []),
                    }
                    for sc in (similar_cases or [])
                ]
            except Exception as exc:
                logger.warning("CaseRetriever failed: %s", exc)
                similar_cases = None

        diag_input = AgentInput(
            transcript_text=full_transcript,
            language=lang,
            extra={
                "candidate_disorders": candidate_codes,
                "disorder_names": disorder_names,
                "similar_cases": similar_cases,
                "prompt_variant": self.prompt_variant,
            },
        )
        diag_output = self.diagnostician.run(diag_input)
        stage_timings["diagnostician"] = time.monotonic() - diag_start

        ranked_codes = []
        diag_reasoning = []
        if diag_output.parsed and diag_output.parsed.get("ranked_codes"):
            ranked_codes = list(diag_output.parsed["ranked_codes"])
            diag_reasoning = list(diag_output.parsed.get("reasoning", []))
        if not ranked_codes:
            logger.warning(
                "Diagnostician returned no ranking for case %s, using candidate order",
                case.case_id,
            )
            ranked_codes = list(candidate_codes)
        top1_code = ranked_codes[0] if ranked_codes else None

        decision_trace["diagnostician"] = {
            "ranked_codes": ranked_codes,
            "reasoning": diag_reasoning,
            "used": bool(diag_output.parsed and diag_output.parsed.get("ranked_codes")),
        }

        verify_codes = ranked_codes[:5]
        checker_start = time.monotonic()
        checker_outputs = self._parallel_check_criteria(
            self.checker,
            verify_codes,
            transcript_text,
            evidence_map,
            lang,
            prompt_variant=self.prompt_variant,
            checker_llm_client=self.checker_llm,
        )
        stage_timings["checker_verify"] = time.monotonic() - checker_start

        remaining_codes = [code for code in candidate_codes if code not in verify_codes]
        all_checker_outputs = list(checker_outputs)
        if remaining_codes:
            remaining_start = time.monotonic()
            remaining_outputs = self._parallel_check_criteria(
                self.checker,
                remaining_codes,
                transcript_text,
                evidence_map,
                lang,
                prompt_variant=self.prompt_variant,
                checker_llm_client=self.checker_llm,
            )
            stage_timings["checker_remaining"] = time.monotonic() - remaining_start
            all_checker_outputs.extend(remaining_outputs)

        if not all_checker_outputs:
            stage_timings["total"] = time.monotonic() - case_start
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=top1_code,
                confidence=0.0,
                decision="diagnosis",
                criteria_results=[],
                mode=self.mode_name,
                model_name=self.llm.model,
                checker_model_name=self.checker_model_name,
                language_used=lang,
                candidate_disorders=candidate_codes,
                routing_mode=routing_mode,
                scope_policy=scope_policy,
                decision_trace={
                    **decision_trace,
                    "dtv_mode": True,
                    "diagnostician_ranked": ranked_codes,
                    "diagnostician_reasoning": diag_reasoning,
                    "verify_codes": verify_codes,
                    "veto_applied": False,
                    "veto_from": None,
                    "veto_to": None,
                    "logic_engine_confirmed_codes": [],
                    "raw_checker_outputs": [],
                    "dtv_fallback": "no_checker_outputs",
                },
                stage_timings=stage_timings,
                failures=failures,
            )

        logic_start = time.monotonic()
        logic_output = self.logic_engine.evaluate(all_checker_outputs)
        stage_timings["logic_engine"] = time.monotonic() - logic_start
        confirmed_set = set(logic_output.confirmed_codes)
        met_ratios = {
            co.disorder: co.criteria_met_count / max(co.criteria_required, 1)
            for co in all_checker_outputs
        }

        primary = None
        comorbid: list[str] = []
        confidence = 0.8
        veto_applied = False
        primary_source = "top1"

        for idx, code in enumerate(ranked_codes[:5]):
            if code in confirmed_set:
                primary = code
                if idx == 0:
                    confidence = 0.9
                else:
                    confidence = max(0.65, 0.85 - 0.05 * idx)
                    veto_applied = True
                    primary_source = f"top{idx + 1}"
                break

        if primary is None and confirmed_set:
            confirmed_by_ratio = sorted(
                confirmed_set,
                key=lambda code: met_ratios.get(code, 0.0),
                reverse=True,
            )
            primary = confirmed_by_ratio[0]
            confidence = 0.65
            veto_applied = True
            primary_source = "remaining_confirmed"

        if primary is None:
            primary = top1_code
            confidence = 0.55
            primary_source = "no_confirmed_fallback"

        if primary_source != "top1":
            logger.info(
                "Case %s: DtV primary from %s (top-1 %s -> primary %s)",
                case.case_id,
                primary_source,
                top1_code,
                primary,
            )

        for code in ranked_codes[:5]:
            if code != primary and code in confirmed_set:
                comorbid.append(code)
                break

        if comorbid:
            confirmed_codes_list = [primary] + comorbid
            confidences = {primary: confidence}
            for idx, code in enumerate(comorbid, start=1):
                confidences[code] = confidence - 0.05 * idx
            comorbidity_result = self.comorbidity_resolver.resolve(
                confirmed=confirmed_codes_list,
                confidences=confidences,
            )
            primary = comorbidity_result.primary
            comorbid = comorbidity_result.comorbid

        stage_timings["total"] = time.monotonic() - case_start
        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=primary,
            comorbid_diagnoses=comorbid,
            confidence=confidence,
            decision="diagnosis",
            criteria_results=all_checker_outputs,
            mode=self.mode_name,
            model_name=self.llm.model,
            checker_model_name=self.checker_model_name,
            language_used=lang,
            candidate_disorders=candidate_codes,
            routing_mode=routing_mode,
            scope_policy=scope_policy,
            decision_trace={
                **decision_trace,
                "dtv_mode": True,
                "diagnostician_ranked": ranked_codes,
                "diagnostician_reasoning": diag_reasoning,
                "verify_codes": verify_codes,
                "veto_applied": veto_applied,
                "veto_from": top1_code if veto_applied else None,
                "veto_to": primary if veto_applied else None,
                "logic_engine_confirmed_codes": logic_output.confirmed_codes,
                "raw_checker_outputs": self._build_raw_checker_outputs_trace(
                    all_checker_outputs
                ),
            },
            stage_timings=stage_timings,
            failures=failures,
        )

    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        """Execute one case through the staged HiED pipeline.

        The method keeps stage timings, routing semantics, candidate disorder
        scope, and failure reasons visible in the returned ``DiagnosisResult``
        so downstream evaluation and review tooling can audit the path taken.
        """
        case_start = time.monotonic()
        stage_timings: dict[str, float] = {}
        try:
            routing_mode, scope_policy = self._resolve_mode_semantics()
        except ValueError as exc:
            failure = FailureInfo(
                code="scope_resolution_failed",
                stage="mode_semantics",
                message=str(exc),
            )
            return self._abstain(
                case,
                case.language,
                failure=failure,
                routing_mode=self.execution_mode,
                scope_policy=self.scope_policy,
                stage_timings={"total": time.monotonic() - case_start},
            )

        lang = case.language
        failures = list(evidence.failures) if evidence and evidence.failures else []
        if lang not in ("zh", "en"):
            failure = FailureInfo(
                code="unsupported_language",
                stage="mode_entry",
                message=f"Language {lang!r} is not supported.",
            )
            return self._abstain(
                case,
                lang,
                failure=failure,
                routing_mode=routing_mode,
                scope_policy=scope_policy,
                failures=failures,
                stage_timings={"total": time.monotonic() - case_start},
            )

        # When evidence is provided, transcript is supplementary — reduce budget
        max_chars = 8000 if evidence else 20000
        transcript_text = self._build_transcript_text(case, max_chars=max_chars)
        evidence_map = self._build_evidence_map(evidence) if evidence else {}
        decision_trace: dict[str, object] = {
            "routing_mode": routing_mode,
            "scope_policy": scope_policy,
            "evidence_failures": [f.code for f in failures],
        }

        # === Stage 1: Triage ===
        if scope_policy == "manual":
            candidate_codes = list(self.target_disorders or [])
            decision_trace["triage"] = {
                "used": False,
                "reason": "manual_scope",
            }
            logger.info(
                "HiED manual scope mode: using %d target disorders", len(candidate_codes)
            )
        elif scope_policy == "all_supported":
            from culturedx.ontology.icd10 import list_disorders

            candidate_codes = list_disorders()
            decision_trace["triage"] = {
                "used": False,
                "reason": "all_supported_scope",
            }
            logger.info(
                "HiED all-supported scope mode: using %d disorders", len(candidate_codes)
            )
        else:
            triage_start = time.monotonic()
            triage_input = AgentInput(
                transcript_text=transcript_text,
                evidence={"evidence_summary": self._build_global_evidence_summary(evidence)} if evidence else None,
                language=lang,
                extra={
                    "chief_complaint": (case.metadata or {}).get("chief_complaint"),
                    "age": (case.metadata or {}).get("age"),
                    "gender": (case.metadata or {}).get("gender"),
                    "prompt_variant": self.prompt_variant,
                },
            )
            triage_output = self.triage.run(triage_input)
            stage_timings["triage"] = time.monotonic() - triage_start
            if triage_output.parsed and "disorder_codes" in triage_output.parsed:
                candidate_codes = triage_output.parsed["disorder_codes"]
                decision_trace["triage"] = {
                    "used": True,
                    "categories": triage_output.parsed.get("categories", []),
                }
            else:
                logger.warning("Triage parse failure for case %s: no disorder_codes in response", case.case_id)
                triage_failure = FailureInfo(
                    code="triage_parse_failure",
                    stage="triage",
                    message="Triage response was missing disorder_codes; cannot determine candidate disorders.",
                    recoverable=False,
                )
                failures.append(triage_failure)
                decision_trace["triage"] = {
                    "used": True,
                    "parse_failure": True,
                    "failure_code": triage_failure.code,
                }
                # Do NOT silently expand to all disorders — return abstain
                return self._abstain(
                    case,
                    lang,
                    failure=triage_failure,
                    decision_trace=decision_trace,
                    stage_timings=stage_timings,
                    failures=failures,
                )

        if not candidate_codes:
            failure = FailureInfo(
                code="scope_resolution_failed",
                stage="triage",
                message="No candidate disorders resolved for HiED.",
                details={"scope_policy": scope_policy},
            )
            return self._abstain(
                case,
                lang,
                failure=failure,
                routing_mode=routing_mode,
                scope_policy=scope_policy,
                decision_trace=decision_trace,
                failures=failures,
                stage_timings={**stage_timings, "total": time.monotonic() - case_start},
            )

        logger.info("Case %s: %d candidate disorders from triage", case.case_id, len(candidate_codes))
        decision_trace["candidate_disorders"] = candidate_codes

        if self.diagnose_then_verify and self.diagnostician is not None:
            return self._diagnose_then_verify(
                case=case,
                lang=lang,
                transcript_text=transcript_text,
                evidence_map=evidence_map,
                candidate_codes=candidate_codes,
                routing_mode=routing_mode,
                scope_policy=scope_policy,
                decision_trace=decision_trace,
                stage_timings=stage_timings,
                failures=failures,
                case_start=case_start,
            )

        # === Stage 2: Criterion Checkers (parallel) ===
        checker_start = time.monotonic()
        checker_outputs = self._parallel_check_criteria(
            self.checker,
            candidate_codes,
            transcript_text,
            evidence_map,
            lang,
            prompt_variant=self.prompt_variant,
            checker_llm_client=self.checker_llm,
        )
        stage_timings["checker_fanout"] = time.monotonic() - checker_start

        if not checker_outputs:
            failure = FailureInfo(
                code="checker_failed",
                stage="criterion_checkers",
                message="No checker outputs were produced for the candidate disorders.",
            )
            return self._abstain(
                case,
                lang,
                criteria_results=[],
                failure=failure,
                candidate_disorders=candidate_codes,
                routing_mode=routing_mode,
                scope_policy=scope_policy,
                decision_trace=decision_trace,
                failures=failures,
                stage_timings={**stage_timings, "total": time.monotonic() - case_start},
            )

        # === Stage 2.5: Contrastive Disambiguation ===
        if self.contrastive_enabled and self.contrastive is not None:
            contrastive_start = time.monotonic()
            checker_outputs = self._run_contrastive(
                checker_outputs, transcript_text, lang,
            )
            stage_timings["contrastive"] = time.monotonic() - contrastive_start

        # === Stage 3: Logic Engine (deterministic) ===
        logic_start = time.monotonic()
        logic_output = self.logic_engine.evaluate(checker_outputs)
        stage_timings["logic_engine"] = time.monotonic() - logic_start

        if not logic_output.confirmed:
            # No disorders meet thresholds
            failure = FailureInfo(
                code="rule_abstain",
                stage="logic_engine",
                message="No disorders satisfied ICD-10 threshold rules.",
                details={"confirmed_codes": logic_output.confirmed_codes},
            )
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                criteria_results=checker_outputs,
                mode=self.mode_name,
                model_name=self.llm.model,
                checker_model_name=self.checker_model_name,
                language_used=lang,
                candidate_disorders=candidate_codes,
                routing_mode=routing_mode,
                scope_policy=scope_policy,
                decision_trace={
                    **decision_trace,
                    "logic_engine_confirmed_codes": logic_output.confirmed_codes,
                },
                stage_timings={**stage_timings, "total": time.monotonic() - case_start},
                failure=failure,
                failures=failures + [failure],
            )

        # === Stage 4: Calibrator (statistical) ===
        # Build confirmation type map from logic engine results
        confirmation_types = {
            r.disorder_code: r.confirmation_type
            for r in logic_output.confirmed
        }
        calibrator_start = time.monotonic()
        cal_output = self.calibrator.calibrate(
            confirmed_disorders=logic_output.confirmed_codes,
            checker_outputs=checker_outputs,
            evidence=evidence,
            confirmation_types=confirmation_types,
            scale_scores=case.scale_scores,
        )
        stage_timings["calibrator"] = time.monotonic() - calibrator_start

        if cal_output.primary is None:
            failure = FailureInfo(
                code="rule_abstain",
                stage="calibrator",
                message="Calibrator abstained from selecting a primary diagnosis.",
            )
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                criteria_results=checker_outputs,
                mode=self.mode_name,
                model_name=self.llm.model,
                checker_model_name=self.checker_model_name,
                language_used=lang,
                candidate_disorders=candidate_codes,
                routing_mode=routing_mode,
                scope_policy=scope_policy,
                decision_trace=decision_trace,
                stage_timings={**stage_timings, "total": time.monotonic() - case_start},
                failure=failure,
                failures=failures + [failure],
            )

        # === Stage 4a: Pairwise Re-ranking (optional, no LLM) ===
        if self.pairwise_ranker is not None:
            all_cal = [cal_output.primary] + cal_output.comorbid
            if len(all_cal) >= 2:
                ranker_start = time.monotonic()
                codes = [c.disorder_code for c in all_cal]
                reranked_codes = self.pairwise_ranker.rerank(
                    codes, checker_outputs,
                )
                stage_timings["pairwise_ranker"] = time.monotonic() - ranker_start
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
                differential_start = time.monotonic()
                logger.info(
                    "Case %s: confidence gap %.4f < %.2f, running differential",
                    case.case_id, gap, self.differential_threshold,
                )
                diff_result = self._run_differential(
                    case, checker_outputs, logic_output, lang, transcript_text,
                )
                stage_timings["differential"] = time.monotonic() - differential_start
                if diff_result is not None:
                    diff_result.candidate_disorders = candidate_codes
                    diff_result.routing_mode = routing_mode
                    diff_result.scope_policy = scope_policy
                    diff_result.decision_trace = {
                        **decision_trace,
                        **(diff_result.decision_trace or {}),
                    }
                    diff_result.stage_timings = {
                        **stage_timings,
                        **(diff_result.stage_timings or {}),
                        "total": time.monotonic() - case_start,
                    }
                    diff_result.failures = failures + list(diff_result.failures)
                    return diff_result
                logger.info("Differential inconclusive, falling back to calibrator")

        # === Stage 4b: Comorbidity Resolution ===
        # Build confidence map from calibrated scores
        confidences = {c.disorder_code: c.confidence for c in all_calibrated}
        confirmed_codes = [c.disorder_code for c in all_calibrated]

        comorbidity_start = time.monotonic()
        comorbidity_result = self.comorbidity_resolver.resolve(
            confirmed=confirmed_codes,
            confidences=confidences,
        )
        stage_timings["comorbidity"] = time.monotonic() - comorbidity_start

        # Find the calibrated diagnosis for the resolved primary
        primary_cal = next(
            (c for c in all_calibrated if c.disorder_code == comorbidity_result.primary),
            cal_output.primary,
        )

        stage_timings["total"] = time.monotonic() - case_start

        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=comorbidity_result.primary,
            comorbid_diagnoses=comorbidity_result.comorbid,
            confidence=primary_cal.confidence,
            decision="diagnosis",
            criteria_results=checker_outputs,
            mode=self.mode_name,
            model_name=self.llm.model,
            checker_model_name=self.checker_model_name,
            language_used=lang,
            candidate_disorders=candidate_codes,
            routing_mode=routing_mode,
            scope_policy=scope_policy,
            decision_trace={
                **decision_trace,
                "logic_engine_confirmed_codes": logic_output.confirmed_codes,
                "calibration": {
                    "primary": primary_cal.disorder_code,
                    "primary_reason": primary_cal.decision_reason,
                    "comorbid": [c.disorder_code for c in cal_output.comorbid],
                    "abstained": [c.disorder_code for c in cal_output.abstained],
                    "rejected": [c.disorder_code for c in cal_output.rejected],
                },
                "comorbidity": {
                    "excluded": comorbidity_result.excluded,
                    "rejected": comorbidity_result.rejected,
                },
            },
            stage_timings=stage_timings,
            failures=failures,
        )

    def _resolve_mode_semantics(self) -> tuple[str, str]:
        """Resolve explicit benchmark/manual vs production/open-set semantics.

        This helper is intentionally strict: if callers provide
        ``target_disorders`` while claiming open-set semantics, or request
        manual scope without an explicit disorder set, the mode fails fast
        instead of silently reinterpreting the request.
        """
        scope_policy = self.scope_policy
        if scope_policy == "auto":
            scope_policy = "manual" if self.target_disorders is not None else "triage"

        if scope_policy == "manual" and not self.target_disorders:
            raise ValueError("manual scope requires explicit target_disorders")
        if self.target_disorders is not None and scope_policy != "manual":
            raise ValueError(
                "target_disorders implies benchmark/manual scope; set scope_policy='manual' or omit target_disorders"
            )

        execution_mode = self.execution_mode
        if execution_mode == "auto":
            execution_mode = (
                "benchmark_manual_scope"
                if scope_policy == "manual"
                else "production_open_set"
            )

        if execution_mode == "production_open_set" and scope_policy == "manual":
            raise ValueError(
                "production_open_set mode cannot run with manual target_disorders"
            )

        return execution_mode, scope_policy

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
                "prompt_variant": self.prompt_variant,
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
                "prompt_variant": self.prompt_variant,
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
            checker_model_name=self.checker_model_name,
            language_used=lang,
        )
