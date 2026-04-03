"""Run dedicated 2-class and 4-class prompts for LingxiDiagBench Table 4.

Paper baselines use task-specific prompts (Appendix C.3), not 12-class predictions
folded down. This script runs dedicated binary/4-class prompts to match that protocol.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.data.adapters.lingxidiag16k import LingxiDiag16kAdapter
from culturedx.eval.lingxidiag_paper import (
    PAPER_2_CLASSES,
    PAPER_4_CLASSES,
    classify_2class_from_raw,
    classify_4class_from_raw,
    compute_singlelabel_metrics,
)
from culturedx.llm.vllm_client import VLLMClient
from culturedx.llm.json_utils import extract_json_from_response
from culturedx.modes.base import BaseModeOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("paper_static_2c4c")


def build_transcript(case, max_chars=20000) -> str:
    """Build formatted transcript text (same as BaseModeOrchestrator)."""
    return BaseModeOrchestrator._build_transcript_text(case, max_chars=max_chars)


def parse_diagnosis(raw: str, valid_labels: set[str], default: str) -> str:
    """Extract diagnosis from LLM response."""
    parsed = extract_json_from_response(raw)
    if parsed and isinstance(parsed, dict):
        diag = parsed.get("diagnosis", "")
        if diag in valid_labels:
            return diag
    # Regex fallback
    for label in valid_labels:
        if label in raw:
            return label
    return default


def run_task(
    llm: VLLMClient,
    cases: list,
    template_path: str,
    task_name: str,
    valid_labels: set[str],
    default_label: str,
    output_path: Path,
) -> list[dict]:
    """Run a static prompt task on all cases."""
    env = Environment(
        loader=FileSystemLoader(str(Path(template_path).parent)),
        keep_trailing_newline=True,
    )
    template = env.get_template(Path(template_path).name)
    source, _, _ = env.loader.get_source(env, Path(template_path).name)
    prompt_hash = llm.compute_prompt_hash(source)

    results = []
    total = len(cases)
    start = time.monotonic()

    for i, case in enumerate(cases):
        transcript = build_transcript(case)
        prompt = template.render(transcript_text=transcript)

        raw = llm.generate(prompt, prompt_hash=prompt_hash, language="zh")
        pred = parse_diagnosis(raw, valid_labels, default_label)

        results.append({
            "case_id": case.case_id,
            "task": task_name,
            "prediction": pred,
            "raw_response": raw[:500],
            "DiagnosisCode": case.metadata.get("diagnosis_code_full", ""),
        })

        if (i + 1) % 50 == 0:
            elapsed = time.monotonic() - start
            rate = (i + 1) / elapsed
            eta = (total - i - 1) / rate if rate > 0 else 0
            logger.info(
                "Task %s: %d/%d (%.1f%%) | elapsed: %.0fs | ETA: %.0fs",
                task_name, i + 1, total, (i + 1) / total * 100, elapsed, eta,
            )

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    logger.info("Task %s: saved %d results to %s", task_name, len(results), output_path)
    return results


def evaluate_2class(results: list[dict]) -> dict:
    """Evaluate 2-class predictions."""
    gold_list, pred_list = [], []
    for r in results:
        raw_code = r["DiagnosisCode"]
        gold = classify_2class_from_raw(raw_code)
        if gold is None:
            continue  # skip non-binary cases (shouldn't happen if filtered)
        gold_list.append(gold)
        pred_list.append(r["prediction"])
    if not gold_list:
        return {}
    return compute_singlelabel_metrics(gold_list, pred_list, PAPER_2_CLASSES)


def evaluate_4class(results: list[dict]) -> dict:
    """Evaluate 4-class predictions."""
    gold_list, pred_list = [], []
    for r in results:
        raw_code = r["DiagnosisCode"]
        gold = classify_4class_from_raw(raw_code)
        gold_list.append(gold)
        pred_list.append(r["prediction"])
    return compute_singlelabel_metrics(gold_list, pred_list, PAPER_4_CLASSES)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", default="data/raw/lingxidiag16k")
    parser.add_argument("--split", default="validation")
    parser.add_argument("--output-dir", default="outputs/paper_static_2c4c")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--model", default="Qwen/Qwen3-32B-AWQ")
    parser.add_argument("--max-concurrent", type=int, default=4)
    parser.add_argument("--max-cases", type=int, default=0, help="0=all")
    parser.add_argument("--skip-2c", action="store_true")
    parser.add_argument("--skip-4c", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    adapter = LingxiDiag16kAdapter(data_path=args.data_path)
    all_cases = adapter.load(split=args.split)
    if args.max_cases > 0:
        all_cases = all_cases[:args.max_cases]
    logger.info("Loaded %d cases from %s split", len(all_cases), args.split)

    # LLM client
    cache_path = Path("outputs/cache/paper_static_2c4c.db")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    llm = VLLMClient(
        base_url=args.base_url,
        model=args.model,
        temperature=0.0,
        top_k=1,
        disable_thinking=True,
        max_concurrent=args.max_concurrent,
        cache_path=cache_path,
    )

    prompts_dir = Path(__file__).resolve().parent.parent / "prompts" / "paper_static"

    # --- 2-class task ---
    if not args.skip_2c:
        # Filter to pure F32/F41 cases
        cases_2c = []
        for case in all_cases:
            raw_code = case.metadata.get("diagnosis_code_full", "")
            if classify_2class_from_raw(raw_code) is not None:
                cases_2c.append(case)
        logger.info("2-class task: %d eligible cases (pure F32/F41)", len(cases_2c))

        results_2c = run_task(
            llm=llm,
            cases=cases_2c,
            template_path=str(prompts_dir / "binary_zh.jinja"),
            task_name="2class",
            valid_labels={"Depression", "Anxiety"},
            default_label="Depression",
            output_path=output_dir / "results_2class.jsonl",
        )
        m2 = evaluate_2class(results_2c)
        logger.info("2-class: Acc=%.3f F1m=%.3f F1w=%.3f (n=%d)",
                     m2.get("accuracy", 0), m2.get("macro_f1", 0),
                     m2.get("weighted_f1", 0), m2.get("n", 0))
    else:
        logger.info("Skipping 2-class task")

    # --- 4-class task ---
    if not args.skip_4c:
        logger.info("4-class task: %d cases", len(all_cases))

        results_4c = run_task(
            llm=llm,
            cases=all_cases,
            template_path=str(prompts_dir / "fourclass_zh.jinja"),
            task_name="4class",
            valid_labels={"Depression", "Anxiety", "Mixed", "Others"},
            default_label="Others",
            output_path=output_dir / "results_4class.jsonl",
        )
        m4 = evaluate_4class(results_4c)
        logger.info("4-class: Acc=%.3f F1m=%.3f F1w=%.3f (n=%d)",
                     m4.get("accuracy", 0), m4.get("macro_f1", 0),
                     m4.get("weighted_f1", 0), m4.get("n", 0))
    else:
        logger.info("Skipping 4-class task")

    # --- Combined Table 4 ---
    logger.info("Loading existing DtV 12-class results...")
    dtv_path = Path("outputs/eval/hied_dtv_validation/results_lingxidiag.jsonl")
    if dtv_path.exists():
        from culturedx.eval.lingxidiag_paper import (
            compute_multilabel_metrics, PAPER_12_CLASSES,
            gold_to_parent_list, pred_to_parent_list, to_paper_parent,
        )
        import numpy as np

        dtv_cases = []
        with open(dtv_path) as f:
            for line in f:
                dtv_cases.append(json.loads(line))

        # 12-class from DtV diagnostician ranking
        gold_12, pred_12 = [], []
        for case in dtv_cases:
            raw_code = str(case.get("DiagnosisCode", "") or "")
            gold_12.append(gold_to_parent_list(raw_code))
            ranked = case.get("decision_trace", {}).get("diagnostician_ranked", [])
            if ranked:
                parents, seen = [], set()
                for code in ranked:
                    p = to_paper_parent(code)
                    if p not in seen:
                        seen.add(p)
                        parents.append(p)
                pred_12.append(parents or ["Others"])
            else:
                primary = case.get("primary_diagnosis", "")
                comorbid = case.get("comorbid_diagnoses", [])
                pred_12.append(pred_to_parent_list([primary] + comorbid))

        m12 = compute_multilabel_metrics(gold_12, pred_12, PAPER_12_CLASSES)

        # Combine
        table4 = {}
        if not args.skip_2c:
            table4["2class_Acc"] = m2.get("accuracy")
            table4["2class_F1_macro"] = m2.get("macro_f1")
            table4["2class_F1_weighted"] = m2.get("weighted_f1")
        if not args.skip_4c:
            table4["4class_Acc"] = m4.get("accuracy")
            table4["4class_F1_macro"] = m4.get("macro_f1")
            table4["4class_F1_weighted"] = m4.get("weighted_f1")
        table4["12class_Acc"] = m12.get("accuracy")
        table4["12class_Top1"] = m12.get("top1_accuracy")
        table4["12class_Top3"] = m12.get("top3_accuracy")
        table4["12class_F1_macro"] = m12.get("macro_f1")
        table4["12class_F1_weighted"] = m12.get("weighted_f1")

        vals = [float(v) for v in table4.values() if v is not None]
        table4["Overall"] = float(np.mean(vals)) if vals else None

        logger.info("\n=== Combined Table 4 (dedicated 2c/4c + DtV 12c) ===")
        for k, v in table4.items():
            logger.info("  %s = %.3f", k, v if v else 0)

        with open(output_dir / "table4_combined.json", "w") as f:
            json.dump(table4, f, indent=2)
    else:
        logger.warning("No DtV results at %s — skipping combined table", dtv_path)

    llm.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()
