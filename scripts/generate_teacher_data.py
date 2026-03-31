#!/usr/bin/env python3
"""Generate high-quality teacher data for criterion checker SFT.

Uses Qwen3-32B-AWQ via vLLM with guided JSON decoding to produce
100% valid JSON responses for criterion checker training.

Approach:
  1. Load all available cases from LingxiDiag-16K and MDD-5k datasets
  2. For each case × target disorder, render the criterion checker prompt
  3. Call the teacher model with guided_json for guaranteed JSON compliance
  4. Save as SFT JSONL dataset

Usage:
    python scripts/generate_teacher_data.py \
        --max-cases 500 \
        --output-dir data/sft/teacher_v1 \
        --concurrency 4
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys
import time
from pathlib import Path

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

# Target disorders (canonical 5-disorder set)
TARGET_DISORDERS = ["F32", "F33", "F41.1", "F42", "F43.1"]

# Dataset definitions
DATASETS = [
    ("lingxidiag16k", PROJECT_ROOT / "data" / "raw" / "lingxidiag16k"),
    ("mdd5k_raw", PROJECT_ROOT / "data" / "raw" / "mdd5k_repo"),
]

# JSON schema for guided decoding
CHECKER_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["met", "not_met", "insufficient_evidence"],
                    },
                    "evidence": {
                        "anyOf": [{"type": "string"}, {"type": "null"}]
                    },
                    "confidence": {"type": "number"},
                },
                "required": ["criterion_id", "status", "evidence", "confidence"],
            },
        }
    },
    "required": ["criteria"],
}


def load_all_cases(
    adapter_name: str, data_path: Path, max_cases: int | None = None, seed: int = 42
) -> list[dict]:
    """Load cases and return list of {case_id, transcript_text, diagnoses, dataset}."""
    adapter = get_adapter(adapter_name, data_path)
    cases = adapter.load()
    logger.info("Loaded %d cases from %s", len(cases), adapter_name)

    if max_cases and len(cases) > max_cases:
        rng = random.Random(seed)
        cases = rng.sample(cases, max_cases)
        logger.info("Sampled %d cases", len(cases))

    result = []
    for case in cases:
        lines = []
        for turn in case.transcript:
            speaker = turn.speaker.capitalize()
            lines.append(f"{speaker}: {turn.text}")
        full_text = "\n".join(lines)

        # Same truncation as prepare_sft_dataset.py
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
            marker = "\n[...对话中间部分省略 / middle turns omitted...]\n"
            full_text = "\n".join(head_lines) + marker + "\n".join(tail_lines)

        result.append({
            "case_id": case.case_id,
            "transcript_text": full_text,
            "diagnoses": case.diagnoses,
            "dataset": adapter_name,
        })

    return result


def render_checker_prompt(
    env: Environment,
    disorder_code: str,
    transcript_text: str,
    evidence_summary: str | None = None,
) -> str:
    """Render the criterion checker prompt."""
    criteria = get_disorder_criteria(disorder_code)
    if criteria is None:
        raise ValueError(f"Unknown disorder: {disorder_code}")
    disorder_name = get_disorder_name(disorder_code, "zh") or disorder_code
    template = env.get_template("criterion_checker_zh.jinja")
    return template.render(
        disorder_code=disorder_code,
        disorder_name=disorder_name,
        criteria=criteria,
        transcript_text=transcript_text,
        evidence_summary=evidence_summary,
    )


async def generate_one(
    session, base_url: str, model: str, prompt: str, schema: dict,
    semaphore: asyncio.Semaphore, idx: int, total: int,
) -> str | None:
    """Generate one teacher response with guided JSON."""
    async with semaphore:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 1024,
            "guided_json": schema,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            import httpx
            resp = await session.post(
                f"{base_url}/v1/chat/completions",
                json=body,
                timeout=300.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            if (idx + 1) % 50 == 0:
                logger.info("  Progress: %d/%d", idx + 1, total)
            return text
        except Exception as e:
            logger.warning("  Failed example %d: %s", idx, str(e)[:200])
            return None


async def run_teacher_generation(
    cases: list[dict],
    disorders: list[str],
    jinja_env: Environment,
    base_url: str,
    model: str,
    concurrency: int,
) -> list[dict]:
    """Run teacher generation for all case × disorder pairs."""
    import httpx

    # Build all prompts
    tasks = []
    for case in cases:
        for disorder in disorders:
            evidence_summary = scan_somatic_hints(case["transcript_text"], disorder)
            try:
                prompt = render_checker_prompt(
                    jinja_env, disorder, case["transcript_text"], evidence_summary
                )
            except ValueError:
                continue
            tasks.append({
                "case_id": case["case_id"],
                "disorder_code": disorder,
                "dataset": case["dataset"],
                "diagnoses": case["diagnoses"],
                "prompt": prompt,
            })

    logger.info("Total prompts to generate: %d", len(tasks))

    semaphore = asyncio.Semaphore(concurrency)
    examples = []

    async with httpx.AsyncClient() as client:
        # Process in batches of 200 to avoid overwhelming
        batch_size = 200
        for batch_start in range(0, len(tasks), batch_size):
            batch = tasks[batch_start:batch_start + batch_size]
            logger.info(
                "Batch %d-%d of %d",
                batch_start, batch_start + len(batch), len(tasks),
            )

            coros = [
                generate_one(
                    client, base_url, model, t["prompt"],
                    CHECKER_JSON_SCHEMA, semaphore, i, len(batch),
                )
                for i, t in enumerate(batch)
            ]
            responses = await asyncio.gather(*coros)

            for task_info, response in zip(batch, responses):
                if response is None:
                    continue

                # Validate JSON
                try:
                    parsed = json.loads(response)
                    if "criteria" not in parsed:
                        continue
                except json.JSONDecodeError:
                    continue

                examples.append({
                    "messages": [
                        {"role": "user", "content": task_info["prompt"]},
                        {"role": "assistant", "content": response},
                    ],
                    "metadata": {
                        "case_id": task_info["case_id"],
                        "disorder_code": task_info["disorder_code"],
                        "dataset": task_info["dataset"],
                        "gold_diagnoses": task_info["diagnoses"],
                        "teacher_model": model,
                        "n_criteria": len(parsed["criteria"]),
                        "n_met": sum(
                            1 for c in parsed["criteria"] if c["status"] == "met"
                        ),
                        "n_not_met": sum(
                            1 for c in parsed["criteria"] if c["status"] == "not_met"
                        ),
                        "n_insufficient": sum(
                            1 for c in parsed["criteria"]
                            if c["status"] == "insufficient_evidence"
                        ),
                    },
                })

    return examples


def report_stats(examples: list[dict]) -> None:
    """Print dataset statistics."""
    from collections import Counter

    total = len(examples)
    logger.info("=" * 60)
    logger.info("Teacher Dataset Statistics")
    logger.info("=" * 60)
    logger.info("Total examples: %d", total)

    disorder_counts: Counter = Counter()
    dataset_counts: Counter = Counter()
    status_counts: Counter = Counter()

    for ex in examples:
        meta = ex["metadata"]
        disorder_counts[meta["disorder_code"]] += 1
        dataset_counts[meta["dataset"]] += 1
        status_counts["met"] += meta["n_met"]
        status_counts["not_met"] += meta["n_not_met"]
        status_counts["insufficient_evidence"] += meta["n_insufficient"]

    logger.info("")
    logger.info("Per-disorder:")
    for code, cnt in sorted(disorder_counts.items()):
        logger.info("  %-8s %4d (%.1f%%)", code, cnt, 100 * cnt / total)

    logger.info("")
    logger.info("Per-dataset:")
    for ds, cnt in sorted(dataset_counts.items()):
        logger.info("  %-20s %4d", ds, cnt)

    logger.info("")
    total_decisions = sum(status_counts.values())
    if total_decisions:
        logger.info("Criterion status balance:")
        for status, cnt in status_counts.most_common():
            logger.info("  %-25s %5d (%.1f%%)", status, cnt, 100 * cnt / total_decisions)

    prompt_lens = [len(ex["messages"][0]["content"]) for ex in examples]
    resp_lens = [len(ex["messages"][1]["content"]) for ex in examples]
    logger.info("")
    logger.info(
        "Prompt: mean=%.0f, median=%.0f, max=%d chars",
        sum(prompt_lens) / len(prompt_lens),
        sorted(prompt_lens)[len(prompt_lens) // 2],
        max(prompt_lens),
    )
    logger.info(
        "Response: mean=%.0f, median=%.0f, max=%d chars",
        sum(resp_lens) / len(resp_lens),
        sorted(resp_lens)[len(resp_lens) // 2],
        max(resp_lens),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate teacher SFT data")
    parser.add_argument("--max-cases", type=int, default=500,
                        help="Max cases per dataset (default: 500)")
    parser.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "data" / "sft" / "teacher_v1")
    parser.add_argument("--split-ratio", type=float, default=0.9)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--model", default="Qwen/Qwen3-32B-AWQ")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()

    # Jinja2 env
    prompts_dir = PROJECT_ROOT / "prompts" / "agents"
    jinja_env = Environment(
        loader=FileSystemLoader(str(prompts_dir)),
        keep_trailing_newline=True,
    )

    # Load cases from all datasets
    all_cases = []
    for adapter_name, data_path in DATASETS:
        if not data_path.exists():
            logger.warning("Data path not found: %s — skipping", data_path)
            continue
        cases = load_all_cases(adapter_name, data_path, args.max_cases, args.seed)
        all_cases.extend(cases)

    logger.info("Total cases loaded: %d", len(all_cases))

    if not all_cases:
        logger.error("No cases loaded. Check data paths.")
        sys.exit(1)

    # Run teacher generation
    t0 = time.time()
    examples = asyncio.run(
        run_teacher_generation(
            all_cases, TARGET_DISORDERS, jinja_env,
            args.base_url, args.model, args.concurrency,
        )
    )
    elapsed = time.time() - t0
    logger.info("Generation completed in %.0fs (%.1f examples/min)",
                elapsed, len(examples) / (elapsed / 60))

    if not examples:
        logger.error("No examples generated!")
        sys.exit(1)

    # Stats
    report_stats(examples)

    # Shuffle and split
    random.seed(args.seed)
    random.shuffle(examples)

    split_idx = int(len(examples) * args.split_ratio)
    train = examples[:split_idx]
    val = examples[split_idx:]

    logger.info("Train: %d, Val: %d", len(train), len(val))

    # Write
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for name, data in [("train", train), ("val", val)]:
        path = args.output_dir / f"criterion_checker_{name}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for ex in data:
                f.write(json.dumps({"messages": ex["messages"]}, ensure_ascii=False) + "\n")
        logger.info("Written: %s (%d examples)", path, len(data))

    # Full with metadata
    full_path = args.output_dir / "criterion_checker_full.jsonl"
    with open(full_path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    logger.info("Written: %s (%d examples with metadata)", full_path, len(examples))

    # Config
    config = {
        "teacher_model": args.model,
        "n_cases": len(all_cases),
        "n_examples": len(examples),
        "n_train": len(train),
        "n_val": len(val),
        "disorders": TARGET_DISORDERS,
        "datasets": [d[0] for d in DATASETS],
        "max_cases_per_dataset": args.max_cases,
        "seed": args.seed,
        "guided_json": True,
        "concurrency": args.concurrency,
        "generation_time_sec": round(elapsed),
    }
    config_path = args.output_dir / "teacher_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    logger.info("Config: %s", config_path)


if __name__ == "__main__":
    main()
