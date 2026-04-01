#!/usr/bin/env python3
"""Run evidence pipeline sweep on E-DAIC (English) for cross-lingual gap experiment.

Runs HiED with and without evidence on E-DAIC English transcripts.
Somatization is disabled (Chinese-specific feature).
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
logger = logging.getLogger("edaic_evidence")

N_CASES = 217  # Use all E-DAIC cases (217 total)
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

    # Load configs
    cfg = load_config("configs/base.yaml", overrides=["configs/vllm_32b.yaml", "configs/evidence.yaml"])

    # Load E-DAIC dataset
    logger.info("Loading dataset 'edaic' from %s ...", DATA_PATH)
    adapter = get_adapter("edaic", DATA_PATH)
    all_cases = adapter.load()
    logger.info("Loaded %d cases total", len(all_cases))

    # Shuffle deterministically
    rng = random.Random(SEED)
    cases = list(all_cases)
    rng.shuffle(cases)

    depressed = sum(1 for c in cases if c.diagnoses)
    healthy = len(cases) - depressed
    logger.info("Using %d cases: %d depressed (F32), %d healthy", len(cases), depressed, healthy)

    # Create LLM client (force AWQ model name to match vLLM server)
    llm = create_llm_client(
        provider=cfg.llm.provider,
        base_url=cfg.llm.base_url,
        model="Qwen/Qwen3-32B-AWQ",
        temperature=cfg.llm.temperature,
        top_k=cfg.llm.top_k,
        timeout=cfg.request_timeout_sec,
        cache_path=Path(cfg.cache_dir) / "llm_cache.db",
        disable_thinking=getattr(cfg.llm, "disable_thinking", True),
        max_concurrent=getattr(cfg.llm, "max_concurrent", 4),
    )

    # Create evidence pipeline (somatization OFF for English)
    # Force retriever to CPU — vLLM uses 92% GPU memory
    cfg.evidence.retriever.device = "cpu"
    retriever = create_retriever(cfg.evidence.retriever)
    evidence_pipeline = EvidencePipeline(
        llm_client=llm,
        retriever=retriever,
        target_disorders=TARGET_DISORDERS,
        somatization_enabled=False,
        somatization_mode="ontology-only",
        top_k=cfg.evidence.top_k_final,
        min_confidence=cfg.evidence.min_confidence,
    )

    # Timestamp for output dir
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    sweep_dir = OUTPUT_BASE / f"evidence_edaic_{ts}"
    sweep_dir.mkdir(parents=True, exist_ok=True)

    # Save case list
    case_ids = [c.case_id for c in cases]
    with open(sweep_dir / "case_list.json", "w", encoding="utf-8") as f:
        json.dump(case_ids, f)

    conditions = [
        ("hied_no_evidence", False),
        ("hied_bge-m3_evidence", True),
    ]

    report = {
        "sweep_name": "evidence_edaic",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": cfg.llm.provider,
        "model": cfg.llm.model_id,
        "n_cases": len(cases),
        "seed": SEED,
        "n_conditions": len(conditions),
        "conditions": {},
    }

    for i, (cond_name, use_evidence) in enumerate(conditions):
        logger.info("Condition %d/%d: %s", i + 1, len(conditions), cond_name)
        logger.info("=" * 60)

        cond_dir = sweep_dir / cond_name
        cond_dir.mkdir(parents=True, exist_ok=True)

        mode = HiEDMode(
            llm_client=llm,
            target_disorders=TARGET_DISORDERS,
            contrastive_enabled=False,
        )

        runner = ExperimentRunner(
            mode=mode,
            output_dir=cond_dir,
            evidence_pipeline=evidence_pipeline if use_evidence else None,
        )

        t0 = time.time()
        results = runner.run(cases)
        elapsed = time.time() - t0

        # Evaluate
        metrics = runner.evaluate(results, cases)

        report["conditions"][cond_name] = {
            "condition": cond_name,
            "n_cases": len(cases),
            "metrics_parent_normalized": metrics.get("diagnosis", {}),
            "metrics_comorbidity": metrics.get("comorbidity", {}),
            "total_seconds": round(elapsed, 1),
            "avg_seconds_per_case": round(elapsed / len(cases), 1),
        }

        logger.info("Done: %s in %.1fs", cond_name, elapsed)
        dx = metrics.get("diagnosis", {})
        logger.info("  top1=%.3f  top3=%.3f  f1=%.3f",
                     dx.get("top1_accuracy", 0), dx.get("top3_accuracy", 0), dx.get("macro_f1", 0))

    # Save sweep report
    with open(sweep_dir / "sweep_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info("Sweep complete. Report saved to %s", sweep_dir / "sweep_report.json")


if __name__ == "__main__":
    main()
