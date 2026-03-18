"""Evaluation report generator.

Generates structured reports from experiment runs and sweep results.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MetricComparison:
    """Comparison of a metric across conditions."""
    metric_name: str
    values: dict[str, float] = field(default_factory=dict)  # condition_name -> value
    best_condition: str = ""
    best_value: float = 0.0


@dataclass
class AblationTable:
    """Ablation table comparing conditions."""
    name: str
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvalReport:
    """Complete evaluation report."""
    experiment_name: str
    dataset: str = ""
    num_cases: int = 0
    comparisons: list[MetricComparison] = field(default_factory=list)
    ablation_tables: list[AblationTable] = field(default_factory=list)
    summary: str = ""


class ReportGenerator:
    """Generates evaluation reports from experiment results."""

    @staticmethod
    def from_sweep_report(sweep_path: str | Path) -> EvalReport:
        """Load a sweep report and generate an evaluation report."""
        path = Path(sweep_path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        conditions = data.get("conditions", [])
        if not conditions:
            return EvalReport(experiment_name=data.get("sweep_name", "unknown"))

        # Extract all metric names
        all_metrics: set[str] = set()
        for cond in conditions:
            all_metrics.update(cond.get("metrics", {}).keys())

        # Build metric comparisons
        comparisons = []
        for metric in sorted(all_metrics):
            values = {}
            for cond in conditions:
                val = cond.get("metrics", {}).get(metric)
                if val is not None:
                    values[cond["name"]] = float(val)

            best_cond = max(values, key=values.get) if values else ""
            best_val = values.get(best_cond, 0.0) if best_cond else 0.0

            comparisons.append(MetricComparison(
                metric_name=metric,
                values=values,
                best_condition=best_cond,
                best_value=best_val,
            ))

        # Build ablation tables
        ablation_tables = []

        # Mode comparison table
        mode_table = AblationTable(
            name="Mode Comparison",
            columns=["condition", "mode", "evidence", "somatization"]
            + sorted(all_metrics)
            + ["duration_sec"],
        )
        for cond in conditions:
            row = {
                "condition": cond["name"],
                "mode": cond["mode_type"],
                "evidence": "yes" if cond.get("with_evidence") else "no",
                "somatization": "yes" if cond.get("with_somatization") else "no",
                "duration_sec": f"{cond.get('duration_sec', 0):.1f}",
            }
            for metric in sorted(all_metrics):
                val = cond.get("metrics", {}).get(metric)
                row[metric] = f"{val:.4f}" if val is not None else "—"
            mode_table.rows.append(row)
        ablation_tables.append(mode_table)

        report = EvalReport(
            experiment_name=data.get("sweep_name", "unknown"),
            num_cases=conditions[0].get("num_cases", 0) if conditions else 0,
            comparisons=comparisons,
            ablation_tables=ablation_tables,
        )

        return report

    @staticmethod
    def format_markdown(report: EvalReport) -> str:
        """Format report as Markdown."""
        lines = [
            f"# Evaluation Report: {report.experiment_name}",
            "",
            f"**Cases:** {report.num_cases}",
            "",
        ]

        # Metric comparisons
        if report.comparisons:
            lines.append("## Metric Comparisons")
            lines.append("")
            lines.append("| Metric | Best Condition | Best Value |")
            lines.append("|--------|---------------|------------|")
            for comp in report.comparisons:
                lines.append(f"| {comp.metric_name} | {comp.best_condition} | {comp.best_value:.4f} |")
            lines.append("")

        # Ablation tables
        for table in report.ablation_tables:
            lines.append(f"## {table.name}")
            lines.append("")
            if table.columns and table.rows:
                lines.append("| " + " | ".join(table.columns) + " |")
                lines.append("|" + "|".join(["---"] * len(table.columns)) + "|")
                for row in table.rows:
                    cells = [str(row.get(col, "—")) for col in table.columns]
                    lines.append("| " + " | ".join(cells) + " |")
                lines.append("")

        if report.summary:
            lines.append("## Summary")
            lines.append("")
            lines.append(report.summary)

        return "\n".join(lines)

    @staticmethod
    def format_json(report: EvalReport) -> str:
        """Format report as JSON."""
        data = {
            "experiment_name": report.experiment_name,
            "dataset": report.dataset,
            "num_cases": report.num_cases,
            "comparisons": [
                {
                    "metric": c.metric_name,
                    "values": c.values,
                    "best_condition": c.best_condition,
                    "best_value": c.best_value,
                }
                for c in report.comparisons
            ],
            "ablation_tables": [
                {
                    "name": t.name,
                    "columns": t.columns,
                    "rows": t.rows,
                }
                for t in report.ablation_tables
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    @staticmethod
    def save(report: EvalReport, output_dir: str | Path, fmt: str = "both") -> list[Path]:
        """Save report to files.

        Args:
            report: The evaluation report.
            output_dir: Directory to save to.
            fmt: "markdown", "json", or "both".

        Returns:
            List of saved file paths.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        saved = []

        if fmt in ("markdown", "both"):
            md_path = out / "report.md"
            md_path.write_text(ReportGenerator.format_markdown(report), encoding="utf-8")
            saved.append(md_path)

        if fmt in ("json", "both"):
            json_path = out / "report.json"
            json_path.write_text(ReportGenerator.format_json(report), encoding="utf-8")
            saved.append(json_path)

        return saved
