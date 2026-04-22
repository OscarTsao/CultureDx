"""Clinical diagnostic report generator for doctor review.

Renders a DiagnosisResult into a structured, explainable report with:
- Primary and comorbid diagnoses with ICD-10 codes
- Per-disorder criterion breakdown (met/not_met/insufficient_evidence)
- Evidence sentences quoted from the clinical transcript
- Confidence scores and diagnostic thresholds
- Decision trace for full traceability

Supports Markdown, JSON, and structured dict output formats.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from culturedx.core.models import CheckerOutput, DiagnosisResult
from culturedx.ontology.standards import (
    DiagnosticStandard,
    get_disorder_criteria,
    get_disorder_name,
    get_disorder_threshold,
    normalize_standard,
)

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "zh": {"met": "符合", "not_met": "不符合", "insufficient_evidence": "证据不足"},
    "en": {"met": "Met", "not_met": "Not Met", "insufficient_evidence": "Insufficient Evidence"},
}

STATUS_ICONS = {"met": "+", "not_met": "-", "insufficient_evidence": "?"}

DECISION_LABELS = {
    "zh": {"diagnosis": "诊断成立", "abstain": "证据不足，无法诊断"},
    "en": {"diagnosis": "Diagnosis confirmed", "abstain": "Insufficient evidence"},
}

CONFIDENCE_LABELS = {
    "zh": {"high": "高", "medium": "中", "low": "低"},
    "en": {"high": "High", "medium": "Medium", "low": "Low"},
}


def _confidence_level(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


@dataclass
class CriterionDetail:
    """Rendered detail for a single criterion."""

    criterion_id: str
    criterion_text: str
    criterion_text_zh: str
    criterion_type: str
    status: str
    status_label: str
    evidence: str | None
    confidence: float
    confidence_level: str


@dataclass
class DisorderSection:
    """Rendered section for a single disorder."""

    disorder_code: str
    disorder_name: str
    disorder_name_zh: str
    meets_threshold: bool
    met_count: int
    total_criteria: int
    threshold_info: str
    criteria: list[CriterionDetail] = field(default_factory=list)


@dataclass
class ClinicalReport:
    """Structured clinical diagnostic report."""

    case_id: str
    language: str
    generated_at: str
    model_name: str
    mode: str
    decision: str
    decision_label: str
    overall_confidence: float
    primary_diagnosis: DisorderSection | None
    comorbid_diagnoses: list[DisorderSection] = field(default_factory=list)
    ruled_out: list[DisorderSection] = field(default_factory=list)
    stage_timings: dict[str, float] = field(default_factory=dict)


class ClinicalReportGenerator:
    """Generates clinical diagnostic reports from DiagnosisResult."""

    @staticmethod
    def _resolve_standard(result: DiagnosisResult) -> DiagnosticStandard:
        reasoning_standard = (result.reasoning_standard or "icd10").strip().lower()
        if reasoning_standard == "both":
            return DiagnosticStandard.ICD10
        return normalize_standard(reasoning_standard)

    @staticmethod
    def generate(result: DiagnosisResult, language: str = "zh") -> ClinicalReport:
        """Build a ClinicalReport from a DiagnosisResult."""
        lang = language if language in ("zh", "en") else "en"
        status_labels = STATUS_LABELS[lang]
        decision_labels = DECISION_LABELS[lang]
        standard = ClinicalReportGenerator._resolve_standard(result)

        # Build disorder sections from criteria_results
        disorder_sections: dict[str, DisorderSection] = {}
        for checker_out in result.criteria_results:
            section = ClinicalReportGenerator._build_disorder_section(
                checker_out, lang, status_labels, standard
            )
            disorder_sections[checker_out.disorder] = section

        # Classify into primary, comorbid, ruled_out
        primary = None
        comorbid: list[DisorderSection] = []
        ruled_out: list[DisorderSection] = []

        if result.primary_diagnosis and result.primary_diagnosis in disorder_sections:
            primary = disorder_sections[result.primary_diagnosis]
        elif result.primary_diagnosis:
            primary = ClinicalReportGenerator._make_minimal_section(
                result.primary_diagnosis,
                lang,
                meets=True,
                standard=standard,
            )

        for code in result.comorbid_diagnoses:
            if code in disorder_sections:
                comorbid.append(disorder_sections[code])
            else:
                comorbid.append(
                    ClinicalReportGenerator._make_minimal_section(
                        code,
                        lang,
                        meets=True,
                        standard=standard,
                    )
                )

        diagnosed_codes = set()
        if result.primary_diagnosis:
            diagnosed_codes.add(result.primary_diagnosis)
        diagnosed_codes.update(result.comorbid_diagnoses)

        for code, section in disorder_sections.items():
            if code not in diagnosed_codes:
                ruled_out.append(section)

        return ClinicalReport(
            case_id=result.case_id,
            language=lang,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            model_name=result.model_name,
            mode=result.mode,
            decision=result.decision,
            decision_label=decision_labels.get(result.decision, result.decision),
            overall_confidence=result.confidence,
            primary_diagnosis=primary,
            comorbid_diagnoses=comorbid,
            ruled_out=ruled_out,
            stage_timings=result.stage_timings,
        )

    @staticmethod
    def _build_disorder_section(
        checker_out: CheckerOutput,
        lang: str,
        status_labels: dict[str, str],
        standard: DiagnosticStandard = DiagnosticStandard.ICD10,
    ) -> DisorderSection:
        code = checker_out.disorder
        name = get_disorder_name(code, standard, lang="en") or code
        name_zh = get_disorder_name(code, standard, lang="zh") or code
        threshold = get_disorder_threshold(code, standard)
        disorder = get_disorder_criteria(code, standard)
        ontology_criteria = disorder.get("criteria", {}) if disorder else {}

        criteria_details = []
        for cr in checker_out.criteria:
            crit_info = ontology_criteria.get(cr.criterion_id, {})
            criteria_details.append(CriterionDetail(
                criterion_id=cr.criterion_id,
                criterion_text=crit_info.get("text", ""),
                criterion_text_zh=crit_info.get("text_zh", ""),
                criterion_type=crit_info.get("type", ""),
                status=cr.status,
                status_label=status_labels.get(cr.status, cr.status),
                evidence=cr.evidence,
                confidence=cr.confidence,
                confidence_level=_confidence_level(cr.confidence),
            ))

        met_count = checker_out.criteria_met_count
        total = len(checker_out.criteria)
        required = checker_out.criteria_required or threshold.get("min_total", 0)

        threshold_parts = []
        if "min_core" in threshold:
            threshold_parts.append(f"core>={threshold['min_core']}")
        if "min_total" in threshold:
            threshold_parts.append(f"total>={threshold['min_total']}")
        if "duration_weeks" in threshold:
            threshold_parts.append(f"duration>={threshold['duration_weeks']}w")
        if "duration_months" in threshold:
            threshold_parts.append(f"duration>={threshold['duration_months']}mo")
        threshold_info = ", ".join(threshold_parts) if threshold_parts else ""

        return DisorderSection(
            disorder_code=code,
            disorder_name=name,
            disorder_name_zh=name_zh,
            meets_threshold=met_count >= required if required else met_count > 0,
            met_count=met_count,
            total_criteria=total,
            threshold_info=threshold_info,
            criteria=criteria_details,
        )

    @staticmethod
    def _make_minimal_section(
        code: str,
        lang: str,
        meets: bool,
        standard: DiagnosticStandard = DiagnosticStandard.ICD10,
    ) -> DisorderSection:
        return DisorderSection(
            disorder_code=code,
            disorder_name=get_disorder_name(code, standard, lang="en") or code,
            disorder_name_zh=get_disorder_name(code, standard, lang="zh") or code,
            meets_threshold=meets,
            met_count=0,
            total_criteria=0,
            threshold_info="",
        )

    @staticmethod
    def format_markdown(report: ClinicalReport) -> str:
        """Render report as Markdown for doctor review."""
        zh = report.language == "zh"
        lines: list[str] = []

        # Header
        if zh:
            lines.append("# 临床诊断报告")
            lines.append("")
            lines.append(f"**病例编号:** {report.case_id}")
            lines.append(f"**生成时间:** {report.generated_at}")
            lines.append(f"**诊断模型:** {report.model_name}")
            lines.append(f"**诊断模式:** {report.mode}")
            lines.append(f"**诊断决策:** {report.decision_label}")
            lines.append(f"**总体置信度:** {report.overall_confidence:.0%}")
        else:
            lines.append("# Clinical Diagnostic Report")
            lines.append("")
            lines.append(f"**Case ID:** {report.case_id}")
            lines.append(f"**Generated:** {report.generated_at}")
            lines.append(f"**Model:** {report.model_name}")
            lines.append(f"**Mode:** {report.mode}")
            lines.append(f"**Decision:** {report.decision_label}")
            lines.append(f"**Overall Confidence:** {report.overall_confidence:.0%}")

        lines.extend(["", "---", ""])

        # Primary diagnosis
        if report.primary_diagnosis:
            lines.append("## 主要诊断" if zh else "## Primary Diagnosis")
            lines.append("")
            ClinicalReportGenerator._render_disorder_section(
                lines, report.primary_diagnosis, zh
            )

        # Comorbid diagnoses
        if report.comorbid_diagnoses:
            lines.extend(["", "## 共病诊断" if zh else "## Comorbid Diagnoses", ""])
            for section in report.comorbid_diagnoses:
                ClinicalReportGenerator._render_disorder_section(lines, section, zh)

        # Ruled out
        if report.ruled_out:
            lines.extend(["", "## 已排除诊断" if zh else "## Ruled Out", ""])
            for section in report.ruled_out:
                ClinicalReportGenerator._render_disorder_section(lines, section, zh)

        # Timings
        if report.stage_timings:
            lines.extend(["", "## 处理耗时" if zh else "## Processing Time", ""])
            for stage, secs in report.stage_timings.items():
                lines.append(f"- {stage}: {secs:.1f}s")

        lines.extend(["", "---"])
        if zh:
            lines.append(
                "*本报告由 CultureDx 系统自动生成，仅供临床参考，"
                "不构成最终诊断意见。*"
            )
        else:
            lines.append(
                "*This report was generated by CultureDx and is intended "
                "for clinical reference only, not as a final diagnosis.*"
            )

        return "\n".join(lines)

    @staticmethod
    def _render_disorder_section(
        lines: list[str], section: DisorderSection, zh: bool
    ) -> None:
        name = section.disorder_name_zh if zh else section.disorder_name
        status_tag = ("确诊" if zh else "CONFIRMED") if section.meets_threshold \
            else ("未达标" if zh else "NOT MET")

        lines.append(
            f"### {section.disorder_code} {name} — {status_tag} "
            f"({section.met_count}/{section.total_criteria})"
        )
        if section.threshold_info:
            label = "诊断阈值" if zh else "Threshold"
            lines.append(f"**{label}:** {section.threshold_info}")
        lines.append("")

        if not section.criteria:
            return

        conf_labels = CONFIDENCE_LABELS.get("zh" if zh else "en", {})

        for crit in section.criteria:
            icon = STATUS_ICONS.get(crit.status, " ")
            crit_text = crit.criterion_text_zh if zh else crit.criterion_text
            conf_label = conf_labels.get(crit.confidence_level, "")

            lines.append(
                f"- [{icon}] **{crit.criterion_id}** ({crit.criterion_type}) "
                f"{crit_text}"
            )
            lines.append(
                f"  - {crit.status_label} "
                f"(confidence: {crit.confidence:.0%} {conf_label})"
            )
            if crit.evidence:
                ev_label = "证据" if zh else "Evidence"
                lines.append(f'  - {ev_label}: "{crit.evidence}"')
            lines.append("")

    @staticmethod
    def format_json(report: ClinicalReport) -> str:
        """Render report as JSON."""
        return json.dumps(asdict(report), indent=2, ensure_ascii=False)

    @staticmethod
    def save(
        report: ClinicalReport,
        output_dir: str | Path,
        fmt: str = "both",
    ) -> list[Path]:
        """Save report to files."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        saved = []
        filename = f"clinical_report_{report.case_id}"

        if fmt in ("markdown", "both"):
            md_path = out / f"{filename}.md"
            md_path.write_text(
                ClinicalReportGenerator.format_markdown(report), encoding="utf-8"
            )
            saved.append(md_path)

        if fmt in ("json", "both"):
            json_path = out / f"{filename}.json"
            json_path.write_text(
                ClinicalReportGenerator.format_json(report), encoding="utf-8"
            )
            saved.append(json_path)

        return saved
