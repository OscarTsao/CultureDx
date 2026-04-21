"""Generate a deterministic DSM-5 clinical review sample from predictions.jsonl."""
from __future__ import annotations

import copy
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from culturedx.translators.dsm5_translator import translate_prediction_record

INPUT_PATH = Path("results/validation/r16_bypass_logic/predictions.jsonl")
OUTPUT_PATH = Path("results/dsm5_review/sample_for_review.jsonl")
PAPER_CLASSES = ["F20", "F31", "F32", "F33", "F39", "F41", "F42", "F43", "F45", "F51", "F98", "Z71"]
DESIRED_TOTAL = 30
MIN_PER_CLASS = 2
MAX_PER_CLASS = 3
LOSSY_PRIORITY_CODES = {
    "F41": {"F41.2"},
    "F43": {"F43.2"},
    "F98": {"F98"},
}
SOURCE_PRIORITY = {"primary": 0, "comorbid": 1, "gold": 2}


def _normalize_code(code: str | None) -> str | None:
    if code is None:
        return None
    normalized = str(code).strip().upper()
    return normalized or None


def _base_code(code: str | None) -> str | None:
    normalized = _normalize_code(code)
    if normalized is None:
        return None
    return normalized.split(".", 1)[0]


def _match_details(record: dict[str, Any], target_class: str) -> tuple[list[str], list[str], bool]:
    sources: list[str] = []
    matching_codes: list[str] = []
    lossy_priority_hit = False
    lossy_codes = LOSSY_PRIORITY_CODES.get(target_class, set())

    primary = _normalize_code(record.get("primary_diagnosis"))
    if primary is not None and _base_code(primary) == target_class:
        sources.append("primary")
        matching_codes.append(primary)
        if primary in lossy_codes:
            lossy_priority_hit = True

    for code in record.get("comorbid_diagnoses") or []:
        normalized = _normalize_code(code)
        if normalized is None or _base_code(normalized) != target_class:
            continue
        sources.append("comorbid")
        matching_codes.append(normalized)
        if normalized in lossy_codes:
            lossy_priority_hit = True

    for code in record.get("gold_diagnoses") or []:
        normalized = _normalize_code(code)
        if normalized is None or _base_code(normalized) != target_class:
            continue
        sources.append("gold")
        matching_codes.append(normalized)
        if normalized in lossy_codes:
            lossy_priority_hit = True

    deduped_sources = list(dict.fromkeys(sources))
    deduped_codes = list(dict.fromkeys(matching_codes))
    return deduped_sources, deduped_codes, lossy_priority_hit


def _candidate_rank(candidate: dict[str, Any]) -> tuple[int, int, int, str]:
    source_rank = min(SOURCE_PRIORITY[source] for source in candidate["match_sources"])
    lossy_rank = 0 if candidate["lossy_priority_hit"] else 1
    order_index = int(candidate["record"].get("order_index", 0))
    case_id = str(candidate["record"].get("case_id", ""))
    return (lossy_rank, source_rank, order_index, case_id)


def _build_candidate_pools(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    pools: dict[str, list[dict[str, Any]]] = {paper_class: [] for paper_class in PAPER_CLASSES}
    for record in records:
        for paper_class in PAPER_CLASSES:
            match_sources, matching_codes, lossy_priority_hit = _match_details(record, paper_class)
            if not matching_codes:
                continue
            pools[paper_class].append(
                {
                    "record": record,
                    "target_class": paper_class,
                    "match_sources": match_sources,
                    "matching_codes": matching_codes,
                    "lossy_priority_hit": lossy_priority_hit,
                }
            )

    for paper_class, candidates in pools.items():
        unique_by_case: dict[str, dict[str, Any]] = {}
        for candidate in sorted(candidates, key=_candidate_rank):
            case_id = str(candidate["record"]["case_id"])
            unique_by_case.setdefault(case_id, candidate)
        pools[paper_class] = list(unique_by_case.values())
    return pools


def _compute_targets(pools: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    targets = {paper_class: 0 for paper_class in PAPER_CLASSES}
    present_classes = [paper_class for paper_class in PAPER_CLASSES if pools[paper_class]]
    for paper_class in present_classes:
        targets[paper_class] = MIN_PER_CLASS

    remaining = DESIRED_TOTAL - sum(targets.values())
    if remaining < 0:
        raise RuntimeError("Requested total is smaller than the minimum per-class allocation.")

    extra_order = sorted(
        present_classes,
        key=lambda paper_class: (len(pools[paper_class]), PAPER_CLASSES.index(paper_class)),
    )
    for paper_class in extra_order:
        if remaining == 0:
            break
        if len(pools[paper_class]) >= MAX_PER_CLASS:
            targets[paper_class] += 1
            remaining -= 1

    if remaining != 0:
        raise RuntimeError("Unable to allocate a 30-case sample with the available class coverage.")
    return targets


def _select_records(pools: dict[str, list[dict[str, Any]]], targets: dict[str, int]) -> list[dict[str, Any]]:
    selected_case_ids: set[str] = set()
    selected: list[dict[str, Any]] = []
    selection_order = sorted(
        [paper_class for paper_class, target in targets.items() if target > 0],
        key=lambda paper_class: (len(pools[paper_class]), PAPER_CLASSES.index(paper_class)),
    )

    for paper_class in selection_order:
        needed = targets[paper_class]
        picked = 0
        for candidate in pools[paper_class]:
            case_id = str(candidate["record"]["case_id"])
            if case_id in selected_case_ids:
                continue
            enriched = copy.deepcopy(candidate["record"])
            enriched["review_sample_target_class"] = paper_class
            enriched["review_sample_matching_codes"] = list(candidate["matching_codes"])
            enriched["review_sample_selection_sources"] = list(candidate["match_sources"])
            enriched["review_sample_contains_priority_lossy_code"] = candidate["lossy_priority_hit"]
            selected.append(enriched)
            selected_case_ids.add(case_id)
            picked += 1
            if picked == needed:
                break
        if picked != needed:
            raise RuntimeError(
                f"Unable to satisfy target count for {paper_class}: needed {needed}, picked {picked}."
            )
    return selected


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing predictions file: {INPUT_PATH}")

    raw_records = [
        json.loads(line)
        for line in INPUT_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    translated = [translate_prediction_record(record) for record in raw_records]
    pools = _build_candidate_pools(translated)
    targets = _compute_targets(pools)
    selected = _select_records(pools, targets)
    selected.sort(key=lambda record: (PAPER_CLASSES.index(record["review_sample_target_class"]), record["order_index"]))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for record in selected:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    present_classes = [paper_class for paper_class in PAPER_CLASSES if pools[paper_class]]
    missing_classes = [paper_class for paper_class in PAPER_CLASSES if not pools[paper_class]]
    per_class_counts: dict[str, int] = defaultdict(int)
    lossy_f412_count = 0
    for record in selected:
        per_class_counts[record["review_sample_target_class"]] += 1
        if "F41.2" in record["review_sample_matching_codes"]:
            lossy_f412_count += 1

    print(f"Wrote {len(selected)} records to {OUTPUT_PATH}")
    print(f"Present classes: {', '.join(present_classes)}")
    print(f"Missing classes: {', '.join(missing_classes) if missing_classes else 'none'}")
    print("Per-class counts:")
    for paper_class in PAPER_CLASSES:
        if targets[paper_class] > 0:
            print(f"  {paper_class}: {per_class_counts[paper_class]}")
    print(f"Included F41.2 review cases: {lossy_f412_count}")


if __name__ == "__main__":
    main()
