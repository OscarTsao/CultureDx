"""End-to-end evidence extraction pipeline."""
from __future__ import annotations

import logging
from pathlib import Path

from culturedx.core.models import ClinicalCase, EvidenceBrief
from culturedx.evidence.brief import EvidenceBriefAssembler
from culturedx.evidence.criteria_matcher import CriteriaMatcher
from culturedx.evidence.extractor import SymptomExtractor
from culturedx.evidence.retriever import BaseRetriever
from culturedx.evidence.somatization import SomatizationMapper

logger = logging.getLogger(__name__)


class EvidencePipeline:
    """Orchestrate evidence extraction: extract -> somatize -> match -> assemble."""

    def __init__(
        self,
        llm_client,
        retriever: BaseRetriever,
        target_disorders: list[str] | None = None,
        extractor_enabled: bool = True,
        somatization_enabled: bool = True,
        somatization_llm_fallback: bool = True,
        top_k: int = 10,
        min_confidence: float = 0.1,
        prompts_dir: str | Path = "prompts/evidence",
    ) -> None:
        self.llm = llm_client
        self.retriever = retriever
        self.target_disorders = target_disorders or ["F32", "F41.1"]
        self.extractor_enabled = extractor_enabled
        self.somatization_enabled = somatization_enabled
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
                llm_fallback=somatization_llm_fallback,
                prompts_dir=prompts_dir,
            )
        else:
            self._somatizer = None

        self._matcher = CriteriaMatcher(
            retriever=retriever, top_k=top_k, min_score=min_confidence
        )
        self._assembler = EvidenceBriefAssembler(
            min_confidence=min_confidence
        )

    def extract(self, case: ClinicalCase) -> EvidenceBrief:
        """Run the full evidence extraction pipeline for a case."""
        # 1. Get patient turn sentences
        patient_turns = case.patient_turns()
        sentences = [t.text for t in patient_turns]
        turn_ids = [t.turn_id for t in patient_turns]

        if not sentences:
            logger.warning("No patient turns for case %s", case.case_id)
            return EvidenceBrief(case_id=case.case_id, language=case.language)

        # 2. Symptom span extraction (if enabled)
        symptom_spans = []
        if self._extractor is not None:
            symptom_spans = self._extractor.extract(case)
            logger.info(
                "Extracted %d symptom spans for case %s",
                len(symptom_spans),
                case.case_id,
            )

        # 3. Somatization mapping (Chinese only, if enabled)
        somatization_map = {}
        if self._somatizer is not None and case.language == "zh":
            context = " ".join(sentences)
            symptom_spans = self._somatizer.map_all(symptom_spans, context)
            somatization_map = self._build_somatization_boost_map(
                symptom_spans, sentences
            )

        # 4. Batch criteria matching across all disorders (encode sentences once)
        criteria_results = self._matcher.match_all_disorders(
            disorder_codes=self.target_disorders,
            sentences=sentences,
            turn_ids=turn_ids,
            language=case.language,
            somatization_map=somatization_map,
        )

        # 4b. Contrastive scoring: mark shared vs unique evidence across disorders
        criteria_results = self._matcher.add_contrastive_scores(criteria_results)

        # 5. Assemble EvidenceBrief
        return self._assembler.assemble(
            case_id=case.case_id,
            language=case.language,
            symptom_spans=symptom_spans,
            criteria_results=criteria_results,
        )

    @staticmethod
    def _build_somatization_boost_map(
        spans: list, sentences: list[str]
    ) -> dict[str, list[str]]:
        """Build mapping: sentence_text -> list of criterion_ids from somatization.

        This allows CriteriaMatcher to boost sentences that have somatization
        mappings for a particular criterion.
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
