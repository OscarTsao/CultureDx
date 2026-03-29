#!/usr/bin/env python3
"""Run scale score ablation on E-DAIC (English).

Runs HiED with 3 evidence conditions. The scale_scores field (PHQ-8)
is now active in the calibrator, so results should differ from the old sweep.
"""
import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from culturedx.core.target_disorders import load_final_target_disorders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("scale_score_edaic")

SEED = 42
OUTPUT_BASE = Path("outputs/sweeps")
DATA_PATH = "data/raw/daic_explain/edaic_processed.json"
TARGET_DISORDERS = load_final_target_disorders()


def main():
    from culturedx.core.config import load_config
    from culturedx.data.adapters import get_adapter
    from culturedx.llm import create_llm_client
    from culturedx.modes.hied import HiEDMode
    from culturedx.evidence.pipeline import EvidencePipeline
    from culturedx.evidence.retriever_factory import create_retriever
    from culturedx.pipeline.runner import ExperimentRunner

    cfg = load_config("configs/base.yaml", overrides=["configs/vllm_awq.yaml", "configs/evidence.yaml"])

    logger.info("Loading E-DAIC from %s", DATA_PATH)
    adapter = get_adapter("edaic", DATA_PATH)
    all_cases = adapter.load()
    logger.info("Loaded %d cases, %d with scale_scores",
                len(all_cases), sum(1 for c in all_cases if c.scale_scores))

    rng = random.Random(SEED)
    cases = list(all_cases)
    rng.shuffle(cases)

    depressed = sum(1 for c in cases if c.diagnoses)
    logger.info("Using %d cases: %d depressed (F32), %d healthy", len(cases), depressed, len(cases) - depressed)

    llm = create_llm_client(
        provider=cfg.llm.provider,
        base_url=cfg.llm.base_url,
        model=cfg.llm.model_id,
        temperature=cfg.llm.temperature,
        top_k=cfg.llm.top_k,
        timeout=cfg.request_timeout_sec,
        cache_path=Path(cfg.cache_dir) / "llm_cache.db",
        disable_thinking=getattr(cfg.llm, "disable_thinking", True),
        max_concurrent=getattr(cfg.llm, "max_concurrent", 4),
    )

    # Force retriever to CPU (vLLM uses 92% GPU memory)
    cfg.evidence.retriever.device = "cpu"
    retriever = create_retriever(cfg.evidence.retriever)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    sweep_dir = OUTPUT_BASE / f"scale_score_edaic_{ts}"
    sweep_dir.mkdir(parents=True, exist_ok=True)

    with open(sweep_dir / "case_list.json", "w", encoding="utf-8") as f:
        json.dump([c.case_id for c in cases], f)

    conditions = [
        ("hied_no_evidence", False, False),
        ("hied_bge-m3_evidence", True, False),
        ("hied_bge-m3_no_somatization", True, False),
    ]

    report = {
        "sweep_name": "scale_score_edaic",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": cfg.llm.provider,
        "model": cfg.llm.model_id,
        "n_cases": len(cases),
        "seed": SEED,
        "scale_scores_active": True,
        "conditions": {},
    }

    for i, (cond_name, use_evidence, use_somat) in enumerate(conditions):
        logger.info("Condition %d/%d: %s (evidence=%s, somat=%s)",
                     i + 1, len(conditions), cond_name, use_evidence, use_somat)

        cond_dir = sweep_dir / cond_name
        cond_dir.mkdir(parents=True, exist_ok=True)

        mode = HiEDMode(
            llm_client=llm,
            target_disorders=TARGET_DISORDERS,
            contrastive_enabled=False,
            comorbid_min_ratio=0.9,
        )

        evidence_pipeline = None
        if use_evidence:
            evidence_pipeline = EvidencePipeline(
                llm_client=llm,
                retriever=retriever,
                target_disorders=TARGET_DISORDERS,
                somatization_enabled=use_somat,
                somatization_llm_fallback=False,
                top_k=cfg.evidence.top_k_final,
                min_confidence=cfg.evidence.min_confidence,
            )

        runner = ExperimentRunner(
            mode=mode,
            output_dir=cond_dir,
            evidence_pipeline=evidence_pipeline,
        )

        t0 = time.time()
        results = runner.run(cases)
        elapsed = time.time() - t0

        metrics = runner.evaluate(results, cases)

        report["conditions"][cond_name] = {
            "n_cases": len(cases),
            "metrics": metrics.get("diagnosis", {}),
            "comorbidity": metrics.get("comorbidity", {}),
            "total_seconds": round(elapsed, 1),
            "avg_seconds_per_case": round(elapsed / len(cases), 1),
        }

        dx = metrics.get("diagnosis", {})
        logger.info("Done: %s in %.1fs — top1=%.3f top3=%.3f f1=%.3f",
                     cond_name, elapsed,
                     dx.get("top1_accuracy", 0), dx.get("top3_accuracy", 0), dx.get("macro_f1", 0))

    with open(sweep_dir / "sweep_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info("Sweep complete. Report: %s", sweep_dir / "sweep_report.json")

    # Print comparison with old results
    old_no_ev = 0.127
    old_ev = 0.206
    new_no_ev = report["conditions"].get("hied_no_evidence", {}).get("metrics", {}).get("top1_accuracy", 0)
    new_ev = report["conditions"].get("hied_bge-m3_evidence", {}).get("metrics", {}).get("top1_accuracy", 0)
    logger.info("=== Scale Score Impact ===")
    logger.info("No evidence: old=%.1f%% new=%.1f%% delta=%+.1fpp",
                old_no_ev * 100, new_no_ev * 100, (new_no_ev - old_no_ev) * 100)
    logger.info("With evidence: old=%.1f%% new=%.1f%% delta=%+.1fpp",
                old_ev * 100, new_ev * 100, (new_ev - old_ev) * 100)


if __name__ == "__main__":
    main()
