"""Evidence orchestration from transcript turns to ``EvidenceBrief``.

The pipeline prefers explicit partial outputs over opaque failure: most stage
errors are captured as machine-readable ``FailureInfo`` records and returned in
the brief instead of raising past the caller.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from culturedx.core.models import ClinicalCase, EvidenceBrief, FailureInfo
from culturedx.evidence.brief import EvidenceBriefAssembler
from culturedx.evidence.criteria_matcher import ConceptOverlapReranker, CriteriaMatcher
from culturedx.evidence.extractor import SymptomExtractor
from culturedx.evidence.retriever import BaseRetriever
from culturedx.evidence.somatization import SomatizationMapper
from culturedx.evidence.temporal import TemporalFeatures, extract_temporal_features
from culturedx.ontology.standards import DiagnosticStandard, list_disorders, normalize_standard

logger = logging.getLogger(__name__)

SUPPORTED_SCOPE_POLICIES = frozenset({"auto", "manual", "triage", "all_supported"})


class EvidencePipeline:
    """Orchestrate evidence extraction: extract -> somatize -> match -> assemble.

    Scope resolution is explicit and never silently narrows to a hidden subset.
    The returned ``EvidenceBrief`` may therefore represent a complete success,
    a partial success with recoverable failures, or a scope/input failure that
    still preserves debugging context.
    """

    def __init__(
        self,
        llm_client,
        retriever: BaseRetriever,
        target_disorders: list[str] | None = None,
        reasoning_standard: DiagnosticStandard | str = DiagnosticStandard.ICD10,
        scope_policy: str = "auto",
        extractor_enabled: bool = True,
        somatization_enabled: bool = True,
        somatization_mode: str = "ontology-only",
        temporal_enabled: bool = True,
        rerank_enabled: bool = False,
        rerank_top_n: int = 5,
        top_k: int = 10,
        min_confidence: float = 0.1,
        negation_mode: str = "clause-rule",
        prompts_dir: str | Path = "prompts/evidence",
        brief_cache: "EvidenceBriefCache | None" = None,
    ) -> None:
        self.llm = llm_client
        self.retriever = retriever
        self.target_disorders = list(target_disorders) if target_disorders is not None else None
        self.standard = normalize_standard(reasoning_standard)
        if scope_policy not in SUPPORTED_SCOPE_POLICIES:
            raise ValueError(
                f"Unsupported evidence scope policy {scope_policy!r}; "
                f"expected one of {sorted(SUPPORTED_SCOPE_POLICIES)}"
            )
        self.scope_policy = scope_policy
        self.extractor_enabled = extractor_enabled
        self.somatization_enabled = somatization_enabled
        self.temporal_enabled = temporal_enabled
        self.rerank_enabled = rerank_enabled
        self.rerank_top_n = rerank_top_n
        self.top_k = top_k
        self.min_confidence = min_confidence

        if extractor_enabled:
            self._extractor = SymptomExtractor(
                llm_client=llm_client, prompts_dir=prompts_dir
            )
        else:
            self._extractor = None

        if somatization_enabled:
            self._somatizer = SomatizationMapper(
                llm_client=llm_client,
                mode=somatization_mode,
                prompts_dir=prompts_dir,
            )
        else:
            self._somatizer = None

        self._matcher = CriteriaMatcher(
            retriever=retriever,
            standard=self.standard,
            top_k=top_k,
            min_score=min_confidence,
            reranker=ConceptOverlapReranker() if rerank_enabled else None,
            rerank_top_n=rerank_top_n,
            negation_mode=negation_mode,
        )
        self._assembler = EvidenceBriefAssembler(
            min_confidence=min_confidence,
            standard=self.standard,
        )
        self._brief_cache = brief_cache
        self._brief_cache_cfg_hash = ""
        if brief_cache is not None:
            from culturedx.evidence.brief_cache import EvidenceBriefCache
            self._brief_cache_cfg_hash = EvidenceBriefCache.config_hash(
                target_disorders=self.target_disorders,
                somatization_enabled=somatization_enabled,
                scope_policy=scope_policy,
                retriever_type=type(retriever).__name__,
                reasoning_standard=self.standard.value,
            )

    def extract(
        self,
        case: ClinicalCase,
        target_disorders: list[str] | None = None,
    ) -> EvidenceBrief:
        """Run the full evidence extraction pipeline for a case.

        The method preserves stage timings and recoverable failures in the
        returned brief so callers can continue diagnosis or abstain explicitly
        without losing evidence-generation context.
        """
        # Check brief cache first (sweep acceleration)
        if self._brief_cache is not None and target_disorders is None:
            cached = self._brief_cache.get(case.case_id, self._brief_cache_cfg_hash)
            if cached is not None:
                logger.debug("Brief cache hit for case %s", case.case_id)
                return cached

        t0 = time.monotonic()
        failures: list[FailureInfo] = []
        stage_timings: dict[str, float] = {}

        try:
            scope_policy, disorder_codes = self._resolve_target_disorders(target_disorders)
        except ValueError as exc:
            logger.warning("Evidence scope resolution failed for case %s: %s", case.case_id, exc)
            stage_timings["total"] = time.monotonic() - t0
            return EvidenceBrief(
                case_id=case.case_id,
                language=case.language,
                scope_policy=self.scope_policy,
                failures=[
                    FailureInfo(
                        code="scope_resolution_failed",
                        stage="evidence_scope",
                        message=str(exc),
                        details={"configured_scope_policy": self.scope_policy},
                    )
                ],
                stage_timings=stage_timings,
            )

        # 1. Get patient turn sentences
        patient_turns = case.patient_turns()
        sentences = [t.text for t in patient_turns]
        turn_ids = [t.turn_id for t in patient_turns]

        if not sentences:
            logger.warning("No patient turns for case %s", case.case_id)
            stage_timings["total"] = time.monotonic() - t0
            return EvidenceBrief(
                case_id=case.case_id,
                language=case.language,
                scope_policy=scope_policy,
                target_disorders=disorder_codes,
                failures=[
                    FailureInfo(
                        code="evidence_unavailable",
                        stage="evidence_input",
                        message="No patient turns available for evidence extraction.",
                    )
                ],
                stage_timings=stage_timings,
            )

        # 2. Symptom span extraction (if enabled)
        symptom_spans = []
        if self._extractor is not None:
            try:
                symptom_spans = self._extractor.extract(case)
                logger.info(
                    "Extracted %d symptom spans for case %s",
                    len(symptom_spans),
                    case.case_id,
                )
            except Exception as exc:
                logger.warning(
                    "Evidence extraction failed for case %s", case.case_id, exc_info=True
                )
                failures.append(
                    FailureInfo(
                        code="evidence_extraction_failed",
                        stage="extractor",
                        message=str(exc),
                        recoverable=True,
                    )
                )
        stage_timings["extract"] = time.monotonic() - t0

        # 3. Somatization mapping (Chinese only, if enabled)
        t1 = time.monotonic()
        somatization_map = {}
        if self._somatizer is not None and case.language == "zh":
            try:
                context = " ".join(sentences)
                symptom_spans = self._somatizer.map_all(symptom_spans, context)
                somatization_map = self._build_somatization_boost_map(
                    symptom_spans, sentences
                )
            except Exception as exc:
                logger.warning(
                    "Somatization mapping failed for case %s", case.case_id, exc_info=True
                )
                failures.append(
                    FailureInfo(
                        code="evidence_extraction_failed",
                        stage="somatization",
                        message=str(exc),
                        recoverable=True,
                    )
                )
        stage_timings["somatization"] = time.monotonic() - t1

        # 3b. Temporal feature extraction (Chinese only, for F41.1 Criterion A)
        t_temporal_start = time.monotonic()
        temporal_features: TemporalFeatures | None = None
        if self.temporal_enabled and case.language == "zh":
            if any(d.startswith("F41") for d in disorder_codes):
                try:
                    temporal_features = extract_temporal_features(case.transcript)
                    logger.info(
                        "Temporal extraction for %s: confidence=%.2f, months=%s",
                        case.case_id,
                        temporal_features.duration_confidence,
                        temporal_features.estimated_months,
                    )
                except Exception as exc:
                    logger.warning(
                        "Temporal extraction failed for case %s", case.case_id, exc_info=True
                    )
                    failures.append(
                        FailureInfo(
                            code="evidence_extraction_failed",
                            stage="temporal",
                            message=str(exc),
                            recoverable=True,
                        )
                    )
        stage_timings["temporal"] = time.monotonic() - t_temporal_start

        # 4. Batch criteria matching across all disorders (encode sentences once)
        t2 = time.monotonic()
        try:
            criteria_results = self._matcher.match_all_disorders(
                disorder_codes=disorder_codes,
                sentences=sentences,
                turn_ids=turn_ids,
                language=case.language,
                somatization_map=somatization_map,
            )
        except Exception as exc:
            logger.warning(
                "Criteria matching failed for case %s", case.case_id, exc_info=True
            )
            failures.append(
                FailureInfo(
                    code="evidence_extraction_failed",
                    stage="criteria_matcher",
                    message=str(exc),
                )
            )
            stage_timings["match"] = time.monotonic() - t2
            stage_timings["total"] = time.monotonic() - t0
            return EvidenceBrief(
                case_id=case.case_id,
                language=case.language,
                symptom_spans=symptom_spans,
                temporal_features=temporal_features,
                scope_policy=scope_policy,
                target_disorders=disorder_codes,
                failures=failures,
                stage_timings=stage_timings,
            )
        stage_timings["match"] = time.monotonic() - t2

        # 4b. Contrastive scoring: mark shared vs unique evidence across disorders
        t3 = time.monotonic()
        criteria_results = self._matcher.add_contrastive_scores(criteria_results)
        stage_timings["contrastive"] = time.monotonic() - t3

        # 5. Assemble EvidenceBrief
        t4 = time.monotonic()
        result = self._assembler.assemble(
            case_id=case.case_id,
            language=case.language,
            symptom_spans=symptom_spans,
            criteria_results=criteria_results,
        )
        stage_timings["assemble"] = time.monotonic() - t4
        stage_timings["total"] = time.monotonic() - t0

        logger.info(
            "Evidence timing for %s: extract=%.1fs somat=%.1fs"
            " temporal=%.1fs match=%.1fs assemble=%.1fs total=%.1fs",
            case.case_id,
            stage_timings["extract"],
            stage_timings["somatization"],
            stage_timings["temporal"],
            stage_timings["match"],
            stage_timings["assemble"],
            stage_timings["total"],
        )
        result.temporal_features = temporal_features
        result.scope_policy = scope_policy
        result.target_disorders = disorder_codes
        result.failures = failures
        result.stage_timings = stage_timings

        # Populate brief cache for sweep reuse
        if self._brief_cache is not None:
            self._brief_cache.put(case.case_id, self._brief_cache_cfg_hash, result)

        return result

    def _resolve_target_disorders(
        self,
        target_disorders: list[str] | None,
    ) -> tuple[str, list[str]]:
        """Resolve the effective disorder scope without hidden defaults.

        ``manual`` and ``triage`` both require an explicit disorder set.
        ``all_supported`` expands to the ontology-backed supported codes.
        ``auto`` is only a convenience alias for ``manual`` when targets are
        configured, otherwise ``all_supported``.
        """
        configured = (
            list(target_disorders)
            if target_disorders is not None
            else list(self.target_disorders)
            if self.target_disorders is not None
            else None
        )
        scope_policy = self.scope_policy
        if scope_policy == "auto":
            scope_policy = "manual" if configured is not None else "all_supported"

        if scope_policy == "manual":
            if not configured:
                raise ValueError("manual evidence scope requires explicit target_disorders")
            return scope_policy, self._dedupe_codes(configured)

        if scope_policy == "triage":
            if not configured:
                raise ValueError(
                    "triage evidence scope requires triage-provided target_disorders"
                )
            return scope_policy, self._dedupe_codes(configured)

        if scope_policy == "all_supported":
            return scope_policy, self._dedupe_codes(list_disorders(self.standard))

        raise ValueError(f"unsupported evidence scope policy {scope_policy!r}")

    @staticmethod
    def _dedupe_codes(codes: list[str]) -> list[str]:
        seen = set()
        result = []
        for code in codes:
            if code not in seen:
                seen.add(code)
                result.append(code)
        return result

    @staticmethod
    def _build_somatization_boost_map(
        spans: list, sentences: list[str]
    ) -> dict[str, list[str]]:
        """Build mapping: sentence_text -> list of criterion_ids from somatization.

        This allows CriteriaMatcher to boost sentences that have somatization
        mappings for a particular criterion.

        The matcher still performs normal retrieval/scoring; this map is only a
        lightweight hint layer that preserves the original sentence text.
        """
        boost_map: dict[str, list[str]] = {}
        for span in spans:
            if span.mapped_criterion:
                criteria = span.mapped_criterion.split(",")
                # Find which sentences contain this span's text
                for sent in sentences:
                    if span.text in sent:
                        if sent not in boost_map:
                            boost_map[sent] = []
                        boost_map[sent].extend(criteria)
        # Deduplicate
        for key in boost_map:
            boost_map[key] = list(set(boost_map[key]))
        return boost_map
