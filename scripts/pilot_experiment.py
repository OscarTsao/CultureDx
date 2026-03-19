#!/usr/bin/env python3
"""Pilot experiment: HiED vs single-model on stratified MDD-5k sample.

Usage:
    uv run python scripts/pilot_experiment.py --n-cases 20 --model qwen3:32b
    uv run python scripts/pilot_experiment.py --n-cases 50 --model qwen3:32b
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("pilot")


def stratified_sample(cases, n: int, seed: int = 42) -> list:
    """Stratified sample by primary diagnosis parent code."""
    import random
    rng = random.Random(seed)

    by_code = defaultdict(list)
    for c in cases:
        code = c.diagnoses[0] if c.diagnoses else "UNKNOWN"
        by_code[code].append(c)

    # Sort by code frequency descending
    sorted_codes = sorted(by_code.keys(), key=lambda k: -len(by_code[k]))

    # Proportional allocation
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


def run_experiment(
    cases,
    mode,
    mode_name: str,
    output_path: Path,
):
    """Run a mode on cases and return results + timing."""
    results = []
    start = time.time()
    for i, case in enumerate(cases):
        t0 = time.time()
        result = mode.diagnose(case, evidence=None)
        elapsed = time.time() - t0
        results.append(result)
        logger.info(
            "[%s] %d/%d case=%s pred=%s gold=%s (%.1fs)",
            mode_name, i + 1, len(cases), case.case_id,
            result.primary_diagnosis, case.diagnoses, elapsed,
        )
    total_time = time.time() - start

    # Save predictions
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "mode": mode_name,
                "n_cases": len(cases),
                "total_seconds": round(total_time, 1),
                "avg_seconds_per_case": round(total_time / len(cases), 1),
                "predictions": [asdict(r) for r in results],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    return results, total_time


def evaluate(results, cases, mode_name: str) -> dict:
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

    # Per-case detail
    case_details = []
    for r, c in zip(results, cases):
        pred_primary = r.primary_diagnosis or "abstain"
        pred_parent = pred_primary.split(".")[0] if pred_primary != "abstain" else "abstain"
        gold_parent = c.diagnoses[0].split(".")[0] if c.diagnoses else "UNKNOWN"
        case_details.append({
            "case_id": c.case_id,
            "gold": c.diagnoses,
            "gold_parent": gold_parent,
            "pred_primary": pred_primary,
            "pred_parent": pred_parent,
            "pred_comorbid": r.comorbid_diagnoses or [],
            "confidence": r.confidence,
            "decision": r.decision,
            "match_parent": pred_parent == gold_parent,
        })

    return {
        "mode": mode_name,
        "n_cases": len(cases),
        "metrics_parent_normalized": metrics_normalized,
        "metrics_exact": metrics_exact,
        "case_details": case_details,
    }


def main():
    parser = argparse.ArgumentParser(description="Pilot experiment")
    parser.add_argument("--n-cases", type=int, default=20)
    parser.add_argument("--model", type=str, default="qwen3:32b")
    parser.add_argument("--base-url", type=str, default="http://localhost:11434")
    parser.add_argument("--output-dir", type=str, default="outputs/pilot_v5")
    parser.add_argument("--cache-dir", type=str, default="data/cache")
    parser.add_argument("--modes", type=str, default="hied,single",
                        help="Comma-separated modes to run")
    parser.add_argument("--target-disorders", type=str,
                        default="F32,F33,F41.1,F42,F43.1",
                        help="Target disorders for HiED/MAS modes")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load dataset
    from culturedx.data.adapters import get_adapter
    logger.info("Loading MDD-5k raw dataset...")
    adapter = get_adapter("mdd5k_raw", "data/raw/mdd5k_repo")
    all_cases = adapter.load()
    logger.info("Loaded %d cases total", len(all_cases))

    # Stratified sample
    cases = stratified_sample(all_cases, args.n_cases, seed=args.seed)

    # Create LLM client
    from culturedx.llm import create_llm_client
    llm = create_llm_client(
        provider="ollama",
        base_url=args.base_url,
        model=args.model,
        temperature=0.0,
        top_k=1,
        timeout=600,
        cache_path=Path(args.cache_dir) / "pilot_v5_cache.db",
        disable_thinking=True,
    )

    target_disorders = args.target_disorders.split(",")
    mode_names = args.modes.split(",")
    all_eval = {}

    for mode_name in mode_names:
        logger.info("=" * 60)
        logger.info("Running mode: %s", mode_name)
        logger.info("=" * 60)

        if mode_name == "hied":
            from culturedx.modes.hied import HiEDMode
            mode = HiEDMode(
                llm_client=llm,
                target_disorders=target_disorders,
            )
        elif mode_name == "psycot":
            from culturedx.modes.psycot import PsyCoTMode
            mode = PsyCoTMode(
                llm_client=llm,
                target_disorders=target_disorders,
            )
        elif mode_name == "single":
            from culturedx.modes.single import SingleModelMode
            mode = SingleModelMode(llm_client=llm)
        elif mode_name == "specialist":
            from culturedx.modes.specialist import SpecialistMode
            mode = SpecialistMode(
                llm_client=llm,
                target_disorders=target_disorders,
            )
        elif mode_name == "debate":
            from culturedx.modes.debate import DebateMode
            mode = DebateMode(llm_client=llm)
        else:
            logger.error("Unknown mode: %s", mode_name)
            continue

        pred_path = output_dir / f"{mode_name}_predictions.json"
        results, total_time = run_experiment(cases, mode, mode_name, pred_path)

        eval_result = evaluate(results, cases, mode_name)
        eval_result["total_seconds"] = round(total_time, 1)
        all_eval[mode_name] = eval_result

        logger.info(
            "[%s] Done in %.1fs — Parent-norm: top1=%.3f top3=%.3f f1=%.3f",
            mode_name, total_time,
            eval_result["metrics_parent_normalized"]["top1_accuracy"],
            eval_result["metrics_parent_normalized"]["top3_accuracy"],
            eval_result["metrics_parent_normalized"]["macro_f1"],
        )

    # Save combined report
    report_path = output_dir / "pilot_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(all_eval, f, indent=2, ensure_ascii=False)

    # Print summary table
    logger.info("\n" + "=" * 70)
    logger.info("PILOT EXPERIMENT RESULTS")
    logger.info("=" * 70)
    logger.info(
        "%-12s %8s %8s %8s %8s %8s",
        "Mode", "Top-1", "Top-3", "F1", "Time(s)", "s/case",
    )
    logger.info("-" * 70)
    for mode_name, ev in all_eval.items():
        m = ev["metrics_parent_normalized"]
        logger.info(
            "%-12s %8.3f %8.3f %8.3f %8.1f %8.1f",
            mode_name,
            m["top1_accuracy"],
            m["top3_accuracy"],
            m["macro_f1"],
            ev["total_seconds"],
            ev["total_seconds"] / ev["n_cases"],
        )

    logger.info("\nReport saved to: %s", report_path)


if __name__ == "__main__":
    main()
