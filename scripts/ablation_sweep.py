#!/usr/bin/env python3
"""Ablation sweep: full evaluation matrix for CultureDx.

Runs combinations of:
- 5 modes (hied, psycot, specialist, debate, single)
- Evidence: none / mock / bge-m3
- Somatization: on / off (Chinese only, with evidence)
- Model: configurable (default qwen3:32b)

Usage:
    # Dry run (show conditions)
    uv run python scripts/ablation_sweep.py --dry-run

    # Quick: HiED + single, no evidence (mode comparison baseline)
    uv run python scripts/ablation_sweep.py --modes hied,single --no-evidence -n 50

    # Evidence ablation: HiED ± evidence ± somatization
    uv run python scripts/ablation_sweep.py --modes hied --evidence-ablation -n 50

    # Full matrix (all modes × evidence × somatization)
    uv run python scripts/ablation_sweep.py --full -n 100

    # vLLM backend
    uv run python scripts/ablation_sweep.py --provider vllm --model Qwen/Qwen3-32B-AWQ -n 50

    # Resume from checkpoint
    uv run python scripts/ablation_sweep.py --resume outputs/sweeps/ablation_20260319_200000
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("ablation")


@dataclass
class AblationCondition:
    """A single ablation condition."""
    name: str
    mode_type: str
    with_evidence: bool = False
    retriever: str = "none"  # "none", "mock", "bge-m3"
    with_somatization: bool = False
    target_disorders: list[str] = field(default_factory=lambda: [
        "F32", "F33", "F41.1", "F42", "F43.1",
    ])


def build_conditions(
    modes: list[str],
    evidence_ablation: bool = False,
    somatization_ablation: bool = False,
    full: bool = False,
    retriever: str = "mock",
    target_disorders: list[str] | None = None,
) -> list[AblationCondition]:
    """Build ablation conditions.

    Default: one condition per mode (no evidence).
    --evidence-ablation: adds with/without evidence per mode.
    --somatization-ablation: adds with/without somatization per mode (requires evidence).
    --full: all combinations.
    """
    td = target_disorders or ["F32", "F33", "F41.1", "F42", "F43.1"]
    conditions = []

    for mode in modes:
        # Base: no evidence
        conditions.append(AblationCondition(
            name=f"{mode}_no_evidence",
            mode_type=mode,
            with_evidence=False,
            retriever="none",
            with_somatization=False,
            target_disorders=td,
        ))

        if evidence_ablation or full:
            # With evidence + somatization
            conditions.append(AblationCondition(
                name=f"{mode}_{retriever}_evidence",
                mode_type=mode,
                with_evidence=True,
                retriever=retriever,
                with_somatization=True,
                target_disorders=td,
            ))

        if somatization_ablation or full:
            # With evidence, no somatization
            conditions.append(AblationCondition(
                name=f"{mode}_{retriever}_no_somatization",
                mode_type=mode,
                with_evidence=True,
                retriever=retriever,
                with_somatization=False,
                target_disorders=td,
            ))

    return conditions


def stratified_sample(cases, n: int, seed: int = 42) -> list:
    """Stratified sample by primary diagnosis parent code."""
    import random
    rng = random.Random(seed)

    by_code = defaultdict(list)
    for c in cases:
        code = c.diagnoses[0] if c.diagnoses else "UNKNOWN"
        by_code[code].append(c)

    sorted_codes = sorted(by_code.keys(), key=lambda k: -len(by_code[k]))

    total = len(cases)
    selected = []
    remaining = n
    for i, code in enumerate(sorted_codes):
        pool = by_code[code]
        if i == len(sorted_codes) - 1:
            alloc = remaining
        else:
            alloc = max(1, round(len(pool) / total * n))
            alloc = min(alloc, remaining, len(pool))
        remaining -= alloc
        if alloc > 0:
            chosen = rng.sample(pool, min(alloc, len(pool)))
            selected.extend(chosen)
        if remaining <= 0:
            break

    rng.shuffle(selected)
    logger.info(
        "Sampled %d cases: %s",
        len(selected),
        dict(Counter(c.diagnoses[0] for c in selected if c.diagnoses)),
    )
    return selected


def create_mode(mode_name: str, llm_client, target_disorders: list[str]):
    """Create a mode orchestrator."""
    if mode_name == "hied":
        from culturedx.modes.hied import HiEDMode
        return HiEDMode(llm_client=llm_client, target_disorders=target_disorders, differential_threshold=0.10)
    elif mode_name == "psycot":
        from culturedx.modes.psycot import PsyCoTMode
        return PsyCoTMode(llm_client=llm_client, target_disorders=target_disorders)
    elif mode_name == "single":
        from culturedx.modes.single import SingleModelMode
        return SingleModelMode(llm_client=llm_client)
    elif mode_name == "specialist":
        from culturedx.modes.specialist import SpecialistMode
        return SpecialistMode(llm_client=llm_client, target_disorders=target_disorders)
    elif mode_name == "debate":
        from culturedx.modes.debate import DebateMode
        return DebateMode(llm_client=llm_client)
    else:
        raise ValueError(f"Unknown mode: {mode_name}")


def create_evidence_pipeline(llm_client, condition: AblationCondition):
    """Create evidence pipeline for a condition (or None if no evidence)."""
    if not condition.with_evidence:
        return None

    from culturedx.evidence.pipeline import EvidencePipeline
    from culturedx.evidence.retriever import MockRetriever

    if condition.retriever == "mock":
        retriever = MockRetriever()
    elif condition.retriever == "bge-m3":
        from culturedx.evidence.retriever import BGEM3Retriever
        retriever = BGEM3Retriever(model_id="BAAI/bge-m3", device="cpu")
    else:
        return None

    return EvidencePipeline(
        llm_client=llm_client,
        retriever=retriever,
        target_disorders=list(condition.target_disorders),
        extractor_enabled=True,
        somatization_enabled=condition.with_somatization,
        somatization_llm_fallback=condition.with_somatization,
    )


def run_condition(
    condition: AblationCondition,
    cases: list,
    llm_client,
    output_dir: Path,
) -> dict:
    """Run a single ablation condition on all cases."""
    logger.info("=" * 60)
    logger.info("Running condition: %s", condition.name)
    logger.info(
        "  mode=%s evidence=%s retriever=%s somatization=%s",
        condition.mode_type, condition.with_evidence,
        condition.retriever, condition.with_somatization,
    )
    logger.info("=" * 60)

    mode = create_mode(condition.mode_type, llm_client, condition.target_disorders)
    evidence_pipeline = create_evidence_pipeline(llm_client, condition)

    results = []
    start = time.time()

    for i, case in enumerate(cases):
        t0 = time.time()

        # Extract evidence if enabled
        evidence = None
        if evidence_pipeline is not None:
            try:
                evidence = evidence_pipeline.extract(case)
                logger.info(
                    "[%s] %d/%d evidence extracted for %s (%d spans)",
                    condition.name, i + 1, len(cases), case.case_id,
                    len(evidence.symptom_spans) if evidence.symptom_spans else 0,
                )
            except Exception as e:
                logger.warning(
                    "[%s] Evidence extraction failed for %s: %s",
                    condition.name, case.case_id, str(e),
                )

        # Run diagnosis
        result = mode.diagnose(case, evidence=evidence)
        elapsed = time.time() - t0
        results.append(result)

        logger.info(
            "[%s] %d/%d case=%s pred=%s gold=%s conf=%.3f (%.1fs)",
            condition.name, i + 1, len(cases), case.case_id,
            result.primary_diagnosis, case.diagnoses,
            result.confidence, elapsed,
        )

    total_time = time.time() - start

    # Save predictions
    cond_dir = output_dir / condition.name
    cond_dir.mkdir(parents=True, exist_ok=True)

    pred_path = cond_dir / "predictions.json"
    with open(pred_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "condition": condition.name,
                "mode": condition.mode_type,
                "with_evidence": condition.with_evidence,
                "retriever": condition.retriever,
                "with_somatization": condition.with_somatization,
                "n_cases": len(cases),
                "total_seconds": round(total_time, 1),
                "avg_seconds_per_case": round(total_time / len(cases), 1),
                "predictions": [asdict(r) for r in results],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    # Evaluate
    metrics = evaluate(results, cases, condition.name)
    metrics["total_seconds"] = round(total_time, 1)
    metrics["avg_seconds_per_case"] = round(total_time / len(cases), 1)

    # Save metrics
    with open(cond_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    return metrics


def evaluate(results, cases, condition_name: str) -> dict:
    """Compute metrics with parent-code normalization."""
    from culturedx.eval.metrics import compute_diagnosis_metrics

    preds = []
    golds = []
    for r, c in zip(results, cases):
        if c.diagnoses:
            pred_dx = [r.primary_diagnosis] if r.primary_diagnosis else ["unknown"]
            pred_dx += r.comorbid_diagnoses or []
            preds.append(pred_dx)
            golds.append(c.diagnoses)

    metrics_normalized = compute_diagnosis_metrics(preds, golds, normalize="parent")
    metrics_exact = compute_diagnosis_metrics(preds, golds, normalize=None)

    return {
        "condition": condition_name,
        "n_cases": len(cases),
        "metrics_parent_normalized": metrics_normalized,
        "metrics_exact": metrics_exact,
    }


def load_completed_conditions(resume_dir: Path) -> set[str]:
    """Load names of completed conditions from a prior sweep."""
    completed = set()
    if not resume_dir.exists():
        return completed
    for cond_dir in resume_dir.iterdir():
        if cond_dir.is_dir() and (cond_dir / "metrics.json").exists():
            completed.add(cond_dir.name)
    return completed


def main():
    parser = argparse.ArgumentParser(description="CultureDx Ablation Sweep")
    parser.add_argument("--n-cases", "-n", type=int, default=50)
    parser.add_argument("--modes", type=str, default="hied,single",
                        help="Comma-separated modes to sweep")
    parser.add_argument("--evidence-ablation", action="store_true",
                        help="Add evidence on/off conditions per mode")
    parser.add_argument("--somatization-ablation", action="store_true",
                        help="Add somatization on/off conditions (requires evidence)")
    parser.add_argument("--full", action="store_true",
                        help="Full ablation matrix (all combinations)")
    parser.add_argument("--no-evidence", action="store_true",
                        help="Only run without-evidence conditions")
    parser.add_argument("--retriever", type=str, default="mock",
                        choices=["mock", "bge-m3"],
                        help="Retriever for evidence matching")
    parser.add_argument("--provider", type=str, default="ollama",
                        choices=["ollama", "vllm"])
    parser.add_argument("--model", type=str, default="qwen3:32b")
    parser.add_argument("--base-url", type=str, default=None,
                        help="LLM API base URL (auto-detected from provider)")
    parser.add_argument("--target-disorders", type=str,
                        default="F32,F33,F41.1,F42,F43.1")
    parser.add_argument("--output-dir", type=str, default="outputs/sweeps")
    parser.add_argument("--cache-dir", type=str, default="data/cache")
    parser.add_argument("--sweep-name", type=str, default="ablation")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", type=str, default=None,
                        help="Resume from a prior sweep directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print conditions and exit")
    args = parser.parse_args()

    # Auto-detect base URL
    if args.base_url is None:
        if args.provider == "vllm":
            args.base_url = "http://localhost:8000"
        else:
            args.base_url = "http://localhost:11434"

    modes = args.modes.split(",")
    target_disorders = args.target_disorders.split(",")

    # Build conditions
    if args.no_evidence:
        conditions = [
            AblationCondition(
                name=f"{m}_no_evidence",
                mode_type=m,
                with_evidence=False,
                retriever="none",
                with_somatization=False,
                target_disorders=target_disorders,
            )
            for m in modes
        ]
    elif args.full:
        conditions = build_conditions(
            modes=modes,
            evidence_ablation=True,
            somatization_ablation=True,
            full=True,
            retriever=args.retriever,
            target_disorders=target_disorders,
        )
    else:
        conditions = build_conditions(
            modes=modes,
            evidence_ablation=args.evidence_ablation,
            somatization_ablation=args.somatization_ablation,
            retriever=args.retriever,
            target_disorders=target_disorders,
        )

    # Dry run
    if args.dry_run:
        logger.info("Ablation sweep conditions (%d total):", len(conditions))
        for i, c in enumerate(conditions):
            logger.info(
                "  %2d. %-35s mode=%-10s evidence=%-5s retriever=%-6s somat=%s",
                i + 1, c.name, c.mode_type,
                str(c.with_evidence), c.retriever, c.with_somatization,
            )
        est_per_case = 90 if args.provider == "ollama" else 30
        total_est = len(conditions) * args.n_cases * est_per_case
        logger.info(
            "\nEstimated time: %d conditions × %d cases × ~%ds = ~%.1f hours",
            len(conditions), args.n_cases, est_per_case, total_est / 3600,
        )
        return

    # Resume support
    from datetime import datetime
    if args.resume:
        sweep_dir = Path(args.resume)
        completed = load_completed_conditions(sweep_dir)
        logger.info("Resuming sweep from %s (%d conditions done)", sweep_dir, len(completed))
    else:
        sweep_dir = Path(args.output_dir) / f"{args.sweep_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        completed = set()

    sweep_dir.mkdir(parents=True, exist_ok=True)

    # Load dataset
    from culturedx.data.adapters import get_adapter
    logger.info("Loading MDD-5k raw dataset...")
    adapter = get_adapter("mdd5k_raw", "data/raw/mdd5k_repo")
    all_cases = adapter.load()
    logger.info("Loaded %d cases total", len(all_cases))

    cases = stratified_sample(all_cases, args.n_cases, seed=args.seed)

    # Save case list for reproducibility
    case_list_path = sweep_dir / "case_list.json"
    if not case_list_path.exists():
        with open(case_list_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "n_cases": len(cases),
                    "seed": args.seed,
                    "cases": [
                        {"case_id": c.case_id, "diagnoses": c.diagnoses}
                        for c in cases
                    ],
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

    # Create LLM client
    from culturedx.llm import create_llm_client
    llm = create_llm_client(
        provider=args.provider,
        base_url=args.base_url,
        model=args.model,
        temperature=0.0,
        top_k=1,
        timeout=600,
        cache_path=Path(args.cache_dir) / f"sweep_{args.sweep_name}_cache.db",
        disable_thinking=True,
        max_concurrent=4,
    )

    # Run sweep
    all_metrics = {}
    for i, condition in enumerate(conditions):
        if condition.name in completed:
            logger.info(
                "Skipping %d/%d: %s (already completed)",
                i + 1, len(conditions), condition.name,
            )
            # Load existing metrics
            existing = sweep_dir / condition.name / "metrics.json"
            if existing.exists():
                with open(existing, encoding="utf-8") as f:
                    all_metrics[condition.name] = json.load(f)
            continue

        logger.info("Condition %d/%d: %s", i + 1, len(conditions), condition.name)
        metrics = run_condition(condition, cases, llm, sweep_dir)
        all_metrics[condition.name] = metrics

        m = metrics["metrics_parent_normalized"]
        logger.info(
            "[%s] top1=%.3f top3=%.3f f1=%.3f time=%.0fs (%.1fs/case)",
            condition.name,
            m["top1_accuracy"],
            m["top3_accuracy"],
            m["macro_f1"],
            metrics["total_seconds"],
            metrics["avg_seconds_per_case"],
        )

    # Save sweep report
    report = {
        "sweep_name": args.sweep_name,
        "timestamp": datetime.now().isoformat(),
        "provider": args.provider,
        "model": args.model,
        "n_cases": len(cases),
        "seed": args.seed,
        "n_conditions": len(conditions),
        "conditions": all_metrics,
    }
    with open(sweep_dir / "sweep_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary table
    logger.info("\n" + "=" * 80)
    logger.info("ABLATION SWEEP RESULTS")
    logger.info("=" * 80)
    logger.info(
        "%-35s %8s %8s %8s %8s %8s",
        "Condition", "Top-1", "Top-3", "F1", "Time(s)", "s/case",
    )
    logger.info("-" * 80)
    for name, metrics in all_metrics.items():
        m = metrics["metrics_parent_normalized"]
        logger.info(
            "%-35s %8.3f %8.3f %8.3f %8.1f %8.1f",
            name,
            m["top1_accuracy"],
            m["top3_accuracy"],
            m["macro_f1"],
            metrics.get("total_seconds", 0),
            metrics.get("avg_seconds_per_case", 0),
        )

    logger.info("\nReport saved to: %s", sweep_dir / "sweep_report.json")


if __name__ == "__main__":
    main()
