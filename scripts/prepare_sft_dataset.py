#!/usr/bin/env python3
"""Prepare criterion-level SFT dataset from CultureDx checker outputs.

Extracts (prompt, response) pairs from sweep predictions for fine-tuning
a smaller model to perform criterion checking.

For each criterion checker invocation:
  - Reconstructs the Jinja2 prompt (template + disorder criteria + transcript)
  - Extracts the JSON response (per-criterion met/not_met/insufficient_evidence)
  - Formats as chat-style JSONL for HuggingFace SFT

Usage:
    python scripts/prepare_sft_dataset.py [--output-dir data/sft] [--split-ratio 0.9]
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from collections import Counter
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jinja2 import Environment, FileSystemLoader

from culturedx.data.adapters import get_adapter
from culturedx.ontology.icd10 import get_disorder_criteria, get_disorder_name
from culturedx.ontology.symptom_map import scan_somatic_hints

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Sweep definitions: (sweep_dir_name, dataset_adapter_name, data_path)
# --------------------------------------------------------------------------- #
SWEEPS = [
    (
        "final_lingxidiag_20260323_131847",
        "lingxidiag16k",
        PROJECT_ROOT / "data" / "raw" / "lingxidiag16k",
    ),
    (
        "final_mdd5k_20260324_120113",
        "mdd5k_raw",
        PROJECT_ROOT / "data" / "raw" / "mdd5k_repo",
    ),
]

# Conditions containing criterion checker outputs (hied & psycot modes).
# no_evidence conditions: prompts are fully reconstructible (no evidence_summary).
CONDITIONS_PRIORITY = [
    "hied_no_evidence",
    "psycot_no_evidence",
]

# no_somatization conditions: evidence_summary=None always (somatic hints disabled)
CONDITIONS_WITH_SOMATIC_HINTS = [
    "hied_bge-m3_no_somatization",
    "psycot_bge-m3_no_somatization",
]


def load_transcript_map(
    adapter_name: str, data_path: Path
) -> dict[str, str]:
    """Load dataset and return {case_id: formatted_transcript_text}."""
    adapter = get_adapter(adapter_name, data_path)
    cases = adapter.load()
    logger.info(
        "Loaded %d cases from %s (%s)", len(cases), adapter_name, data_path
    )

    transcript_map: dict[str, str] = {}
    for case in cases:
        lines = []
        for turn in case.transcript:
            speaker = turn.speaker.capitalize()
            lines.append(f"{speaker}: {turn.text}")
        full_text = "\n".join(lines)
        # Apply same truncation as the pipeline (20000 chars for no-evidence)
        if len(full_text) > 20000:
            head_budget = int(20000 * 0.6)
            tail_budget = 20000 - head_budget
            head_lines, head_len = [], 0
            for line in lines:
                if head_len + len(line) + 1 > head_budget:
                    break
                head_lines.append(line)
                head_len += len(line) + 1
            tail_lines, tail_len = [], 0
            for line in reversed(lines):
                if tail_len + len(line) + 1 > tail_budget:
                    break
                tail_lines.insert(0, line)
                tail_len += len(line) + 1
            marker = "\n[..." + "对话中间部分省略 / middle turns omitted...]\n"
            full_text = "\n".join(head_lines) + marker + "\n".join(tail_lines)
        transcript_map[case.case_id] = full_text

    return transcript_map


def render_checker_prompt(
    env: Environment,
    language: str,
    disorder_code: str,
    transcript_text: str,
    evidence_summary: str | None = None,
) -> str:
    """Render the criterion checker prompt identically to CriterionCheckerAgent."""
    criteria = get_disorder_criteria(disorder_code)
    if criteria is None:
        raise ValueError(f"Unknown disorder: {disorder_code}")
    disorder_name = get_disorder_name(disorder_code, language) or disorder_code

    template_name = f"criterion_checker_{language}.jinja"
    template = env.get_template(template_name)
    return template.render(
        disorder_code=disorder_code,
        disorder_name=disorder_name,
        criteria=criteria,
        transcript_text=transcript_text,
        evidence_summary=evidence_summary,
    )


def checker_output_to_json(checker_result: dict) -> str:
    """Convert a checker_result dict to the JSON response the model produced."""
    criteria_list = []
    for crit in checker_result["criteria"]:
        entry = {
            "criterion_id": crit["criterion_id"],
            "status": crit["status"],
            "evidence": crit.get("evidence"),
            "confidence": crit["confidence"],
        }
        criteria_list.append(entry)
    return json.dumps({"criteria": criteria_list}, ensure_ascii=False, indent=2)


def extract_from_sweep(
    sweep_dir: Path,
    transcript_map: dict[str, str],
    jinja_env: Environment,
    language: str,
    dedupe_keys: set[str],
) -> list[dict]:
    """Extract SFT examples from a single sweep directory."""
    examples = []

    # Process no-evidence conditions first (fully reconstructible prompts)
    for condition in CONDITIONS_PRIORITY:
        pred_file = sweep_dir / condition / "predictions.json"
        if not pred_file.exists():
            logger.warning("Missing: %s", pred_file)
            continue

        with open(pred_file, encoding="utf-8") as f:
            data = json.load(f)

        mode = data.get("mode", "")
        with_evidence = data.get("with_evidence", False)

        for pred in data.get("predictions", []):
            case_id = pred["case_id"]
            if case_id not in transcript_map:
                continue

            transcript_text = transcript_map[case_id]

            for checker_result in pred.get("criteria_results", []):
                disorder_code = checker_result["disorder"]
                criteria = checker_result.get("criteria", [])
                if not criteria:
                    continue

                # Deduplicate: same case + disorder seen from another condition
                dedupe_key = f"{case_id}:{disorder_code}"
                if dedupe_key in dedupe_keys:
                    continue
                dedupe_keys.add(dedupe_key)

                # For no-evidence + zh language, the pipeline applies
                # scan_somatic_hints as a lightweight fallback
                evidence_summary = None
                if not with_evidence and language == "zh":
                    evidence_summary = scan_somatic_hints(
                        transcript_text, disorder_code
                    )

                try:
                    prompt = render_checker_prompt(
                        jinja_env,
                        language,
                        disorder_code,
                        transcript_text,
                        evidence_summary=evidence_summary,
                    )
                except ValueError:
                    continue

                response = checker_output_to_json(checker_result)

                examples.append({
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": response},
                    ],
                    "metadata": {
                        "case_id": case_id,
                        "disorder_code": disorder_code,
                        "condition": condition,
                        "mode": mode,
                        "dataset": sweep_dir.name,
                        "n_criteria": len(criteria),
                        "n_met": sum(
                            1 for c in criteria if c["status"] == "met"
                        ),
                        "n_not_met": sum(
                            1 for c in criteria if c["status"] == "not_met"
                        ),
                        "n_insufficient": sum(
                            1 for c in criteria
                            if c["status"] == "insufficient_evidence"
                        ),
                    },
                })

    # Also process no-somatization conditions (evidence_summary=None always)
    for condition in CONDITIONS_WITH_SOMATIC_HINTS:
        pred_file = sweep_dir / condition / "predictions.json"
        if not pred_file.exists():
            continue

        with open(pred_file, encoding="utf-8") as f:
            data = json.load(f)

        mode = data.get("mode", "")

        for pred in data.get("predictions", []):
            case_id = pred["case_id"]
            if case_id not in transcript_map:
                continue

            transcript_text = transcript_map[case_id]

            for checker_result in pred.get("criteria_results", []):
                disorder_code = checker_result["disorder"]
                criteria = checker_result.get("criteria", [])
                if not criteria:
                    continue

                dedupe_key = f"{case_id}:{disorder_code}"
                if dedupe_key in dedupe_keys:
                    continue
                dedupe_keys.add(dedupe_key)

                # no_somatization conditions explicitly disable somatic hints
                try:
                    prompt = render_checker_prompt(
                        jinja_env,
                        language,
                        disorder_code,
                        transcript_text,
                        evidence_summary=None,
                    )
                except ValueError:
                    continue

                response = checker_output_to_json(checker_result)

                examples.append({
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": response},
                    ],
                    "metadata": {
                        "case_id": case_id,
                        "disorder_code": disorder_code,
                        "condition": condition,
                        "mode": mode,
                        "dataset": sweep_dir.name,
                        "n_criteria": len(criteria),
                        "n_met": sum(
                            1 for c in criteria if c["status"] == "met"
                        ),
                        "n_not_met": sum(
                            1 for c in criteria if c["status"] == "not_met"
                        ),
                        "n_insufficient": sum(
                            1 for c in criteria
                            if c["status"] == "insufficient_evidence"
                        ),
                    },
                })

    return examples


def report_stats(examples: list[dict]) -> None:
    """Print dataset statistics."""
    total = len(examples)
    logger.info("=" * 60)
    logger.info("SFT Dataset Statistics")
    logger.info("=" * 60)
    logger.info("Total examples: %d", total)

    # Per-disorder distribution
    disorder_counts: Counter = Counter()
    dataset_counts: Counter = Counter()
    status_counts: Counter = Counter()
    condition_counts: Counter = Counter()

    for ex in examples:
        meta = ex["metadata"]
        disorder_counts[meta["disorder_code"]] += 1
        dataset_counts[meta["dataset"]] += 1
        condition_counts[meta["condition"]] += 1
        status_counts["met"] += meta["n_met"]
        status_counts["not_met"] += meta["n_not_met"]
        status_counts["insufficient_evidence"] += meta["n_insufficient"]

    logger.info("")
    logger.info("Per-disorder distribution:")
    for code, cnt in sorted(disorder_counts.items()):
        logger.info("  %-8s %4d examples (%.1f%%)", code, cnt, 100 * cnt / total)

    logger.info("")
    logger.info("Per-dataset distribution:")
    for ds, cnt in sorted(dataset_counts.items()):
        logger.info("  %-50s %4d", ds, cnt)

    logger.info("")
    logger.info("Per-condition distribution:")
    for cond, cnt in sorted(condition_counts.items()):
        logger.info("  %-40s %4d", cond, cnt)

    logger.info("")
    total_decisions = sum(status_counts.values())
    logger.info("Criterion-level status balance (across all criteria):")
    for status, cnt in status_counts.most_common():
        logger.info(
            "  %-25s %5d (%.1f%%)", status, cnt, 100 * cnt / total_decisions
        )

    # Average prompt/response lengths
    prompt_lens = [len(ex["messages"][0]["content"]) for ex in examples]
    resp_lens = [len(ex["messages"][1]["content"]) for ex in examples]
    logger.info("")
    logger.info(
        "Prompt length: mean=%.0f, median=%.0f, max=%d chars",
        sum(prompt_lens) / len(prompt_lens),
        sorted(prompt_lens)[len(prompt_lens) // 2],
        max(prompt_lens),
    )
    logger.info(
        "Response length: mean=%.0f, median=%.0f, max=%d chars",
        sum(resp_lens) / len(resp_lens),
        sorted(resp_lens)[len(resp_lens) // 2],
        max(resp_lens),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare SFT dataset from checker outputs"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "sft",
        help="Output directory for JSONL files",
    )
    parser.add_argument(
        "--split-ratio",
        type=float,
        default=0.9,
        help="Train/val split ratio (default: 0.9)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for train/val split",
    )
    parser.add_argument(
        "--sweeps-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "sweeps",
        help="Base directory for sweep outputs",
    )
    args = parser.parse_args()

    # Setup Jinja2 environment
    prompts_dir = PROJECT_ROOT / "prompts" / "agents"
    jinja_env = Environment(
        loader=FileSystemLoader(str(prompts_dir)),
        keep_trailing_newline=True,
    )

    all_examples: list[dict] = []
    dedupe_keys: set[str] = set()

    for sweep_name, adapter_name, data_path in SWEEPS:
        sweep_dir = args.sweeps_dir / sweep_name
        if not sweep_dir.exists():
            logger.warning("Sweep directory not found: %s", sweep_dir)
            continue

        logger.info("Processing sweep: %s", sweep_name)

        # Determine language from adapter
        language = "zh"  # Both lingxidiag and mdd5k are Chinese

        # Load transcripts
        transcript_map = load_transcript_map(adapter_name, data_path)

        # Filter to only cases used in the sweep
        case_list_file = sweep_dir / "case_list.json"
        if case_list_file.exists():
            with open(case_list_file, encoding="utf-8") as f:
                case_list = json.load(f)
            used_ids = {c["case_id"] for c in case_list["cases"]}
            transcript_map = {
                k: v for k, v in transcript_map.items() if k in used_ids
            }
            logger.info(
                "Filtered to %d cases from case_list.json", len(transcript_map)
            )

        examples = extract_from_sweep(
            sweep_dir, transcript_map, jinja_env, language, dedupe_keys
        )
        logger.info("Extracted %d examples from %s", len(examples), sweep_name)
        all_examples.extend(examples)

    if not all_examples:
        logger.error(
            "No examples extracted. Check sweep directories and data paths."
        )
        sys.exit(1)

    # Report stats
    report_stats(all_examples)

    # Shuffle and split
    random.seed(args.seed)
    random.shuffle(all_examples)

    split_idx = int(len(all_examples) * args.split_ratio)
    train_examples = all_examples[:split_idx]
    val_examples = all_examples[split_idx:]

    logger.info("")
    logger.info(
        "Train: %d examples, Val: %d examples",
        len(train_examples), len(val_examples),
    )

    # Write JSONL files
    args.output_dir.mkdir(parents=True, exist_ok=True)

    train_path = args.output_dir / "criterion_checker_train.jsonl"
    val_path = args.output_dir / "criterion_checker_val.jsonl"

    # Write train set (messages only, no metadata -- standard SFT format)
    with open(train_path, "w", encoding="utf-8") as f:
        for ex in train_examples:
            line = {"messages": ex["messages"]}
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    with open(val_path, "w", encoding="utf-8") as f:
        for ex in val_examples:
            line = {"messages": ex["messages"]}
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    # Also write a full version with metadata for analysis
    full_path = args.output_dir / "criterion_checker_full.jsonl"
    with open(full_path, "w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    logger.info("")
    logger.info("Written:")
    logger.info("  Train: %s (%d examples)", train_path, len(train_examples))
    logger.info("  Val:   %s (%d examples)", val_path, len(val_examples))
    logger.info(
        "  Full:  %s (%d examples with metadata)", full_path, len(all_examples)
    )


if __name__ == "__main__":
    main()
