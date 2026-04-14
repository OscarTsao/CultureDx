"""Ablation sweep runner.

Runs combinations of mode × evidence × somatization × language
to produce structured results for cross-comparison.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from culturedx.core.config import CultureDxConfig, load_config
from culturedx.core.models import ClinicalCase, DiagnosisResult

logger = logging.getLogger(__name__)


@dataclass
class SweepCondition:
    """A single sweep condition (one run configuration)."""
    name: str
    mode_type: str
    with_evidence: bool = True
    with_somatization: bool = True
    target_disorders: list[str] | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class SweepResult:
    """Result from a single sweep condition."""
    condition: SweepCondition
    num_cases: int = 0
    num_diagnosed: int = 0
    num_abstained: int = 0
    metrics: dict = field(default_factory=dict)
    duration_sec: float = 0.0
    output_dir: str = ""


@dataclass
class SweepReport:
    """Complete sweep report."""
    sweep_name: str
    results: list[SweepResult] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "sweep_name": self.sweep_name,
            "timestamp": self.timestamp,
            "conditions": [
                {
                    "name": r.condition.name,
                    "mode_type": r.condition.mode_type,
                    "with_evidence": r.condition.with_evidence,
                    "with_somatization": r.condition.with_somatization,
                    "num_cases": r.num_cases,
                    "num_diagnosed": r.num_diagnosed,
                    "num_abstained": r.num_abstained,
                    "metrics": r.metrics,
                    "duration_sec": r.duration_sec,
                    "output_dir": r.output_dir,
                }
                for r in self.results
            ],
        }


def build_ablation_conditions(
    modes: list[str] | None = None,
    evidence_ablation: bool = True,
    somatization_ablation: bool = True,
    target_disorders: list[str] | None = None,
) -> list[SweepCondition]:
    """Build ablation sweep conditions from spec §6 ablation matrix.

    Default ablation matrix:
    - HiED vs single-model (does MAS help?)
    - With evidence vs without (does evidence help?)
    - With somatization mapper vs without (does culture-aware mapping help?)
    """
    if modes is None:
        modes = ["hied", "single"]

    conditions = []

    for mode in modes:
        # Base condition: full pipeline
        conditions.append(SweepCondition(
            name=f"{mode}_full",
            mode_type=mode,
            with_evidence=True,
            with_somatization=True,
            target_disorders=target_disorders,
        ))

        if evidence_ablation:
            # Without evidence
            conditions.append(SweepCondition(
                name=f"{mode}_no_evidence",
                mode_type=mode,
                with_evidence=False,
                with_somatization=False,
                target_disorders=target_disorders,
            ))

        if somatization_ablation and mode != "single":
            # With evidence but without somatization
            conditions.append(SweepCondition(
                name=f"{mode}_no_somatization",
                mode_type=mode,
                with_evidence=True,
                with_somatization=False,
                target_disorders=target_disorders,
            ))

    return conditions


def load_sweep_config(path: str | Path) -> dict:
    """Load a sweep configuration YAML file."""
    from omegaconf import OmegaConf
    cfg = OmegaConf.load(str(path))
    return OmegaConf.to_container(cfg, resolve=True)


class SweepRunner:
    """Runs ablation sweeps across multiple conditions."""

    def __init__(
        self,
        base_output_dir: str | Path = "outputs/sweeps",
    ) -> None:
        self.base_output_dir = Path(base_output_dir)

    def run_sweep(
        self,
        conditions: list[SweepCondition],
        cases: list[ClinicalCase],
        run_fn: Any = None,
        sweep_name: str = "ablation",
    ) -> SweepReport:
        """Run a sweep over multiple conditions.

        Args:
            conditions: List of sweep conditions to run.
            cases: Dataset cases.
            run_fn: Callable(condition, cases) -> (list[DiagnosisResult], dict[metrics]).
                     If None, only builds the plan without executing.
            sweep_name: Name for the sweep report.

        Returns:
            SweepReport with results for each condition.
        """
        from datetime import datetime

        report = SweepReport(
            sweep_name=sweep_name,
            timestamp=datetime.now().isoformat(),
        )

        sweep_dir = self.base_output_dir / f"{sweep_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        sweep_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting sweep '%s' with %d conditions", sweep_name, len(conditions))

        for i, condition in enumerate(conditions):
            logger.info("Condition %d/%d: %s", i + 1, len(conditions), condition.name)

            cond_dir = sweep_dir / condition.name
            cond_dir.mkdir(parents=True, exist_ok=True)

            start = time.time()

            if run_fn is not None:
                results, metrics = run_fn(condition, cases)
                duration = time.time() - start

                num_diagnosed = sum(1 for r in results if r.decision == "diagnosis")
                num_abstained = sum(1 for r in results if r.decision == "abstain")

                sweep_result = SweepResult(
                    condition=condition,
                    num_cases=len(cases),
                    num_diagnosed=num_diagnosed,
                    num_abstained=num_abstained,
                    metrics=metrics,
                    duration_sec=duration,
                    output_dir=str(cond_dir),
                )
            else:
                sweep_result = SweepResult(
                    condition=condition,
                    num_cases=len(cases),
                    output_dir=str(cond_dir),
                )

            report.results.append(sweep_result)

            # Save condition result
            with open(cond_dir / "result.json", "w", encoding="utf-8") as f:
                json.dump({
                    "condition": condition.name,
                    "mode_type": condition.mode_type,
                    "with_evidence": condition.with_evidence,
                    "with_somatization": condition.with_somatization,
                    "metrics": sweep_result.metrics,
                    "duration_sec": sweep_result.duration_sec,
                }, f, indent=2, ensure_ascii=False)

        # Save sweep report
        with open(sweep_dir / "sweep_report.json", "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info("Sweep complete. Report saved to %s", sweep_dir / "sweep_report.json")
        return report
