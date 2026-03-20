#!/usr/bin/env python3
"""Deep-dive one or more sweep cases with criterion-level detail.

Usage:
    uv run python scripts/case_deep_dive.py \
        --sweep-dir outputs/sweeps/vllm_validate3_* \
        --case-id patient_335,patient_524
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

CRITERIA_REQUIRED_CACHE: dict[tuple[str, int], int] = {}
SIMULATED_FEATURE_CACHE: dict[int, dict[str, dict]] = {}


def load_case_list(sweep_dir: Path) -> dict[str, dict]:
    """Load sweep_dir/case_list.json and return a case_id keyed mapping."""
    case_list_path = sweep_dir / "case_list.json"
    if not case_list_path.exists():
        return {}

    with open(case_list_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    cases = data.get("cases", [])
    return {
        case["case_id"]: case
        for case in cases
        if isinstance(case, dict) and case.get("case_id")
    }


def load_predictions(pred_path: Path) -> list[dict]:
    """Load predictions.json and return the prediction list."""
    with open(pred_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, dict):
        predictions = data.get("predictions", [])
        return predictions if isinstance(predictions, list) else []
    if isinstance(data, list):
        return data
    return []


def find_prediction(preds: list[dict], case_id: str) -> dict | None:
    """Find a prediction entry by case_id."""
    for pred in preds:
        if pred.get("case_id") == case_id:
            return pred
    return None


def status_icon(status: str) -> str:
    """Return a colored icon for a criterion status."""
    if status == "met":
        return f"{GREEN}✓{RESET}"
    if status == "not_met":
        return f"{RED}✗{RESET}"
    if status == "insufficient_evidence":
        return f"{YELLOW}?{RESET}"
    return f"{DIM}~{RESET}"


def conf_bar(conf: float, width: int = 12) -> str:
    """Render a fixed-width confidence bar."""
    value = safe_float(conf)
    if not math.isfinite(value):
        value = 0.0
    value = max(0.0, min(1.0, value))
    width = max(1, width)
    filled = min(width, max(0, int(math.floor(value * width))))
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {value:.2f}"


def parent_code(code: str) -> str:
    """Normalize a code to its parent code."""
    if not code:
        return ""
    return code.split(".")[0]


def safe_float(value: object, default: float = 0.0) -> float:
    """Best-effort float conversion."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def safe_int(value: object, default: int = 0) -> int:
    """Best-effort int conversion."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def truncate(text: str | None, limit: int) -> str:
    """Truncate a string for compact terminal display."""
    if not text:
        return "(no evidence)"
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return f"{text[:limit - 3].rstrip()}..."


def is_f3x(code: str) -> bool:
    """Return True when the parent code is in the F3x family."""
    return parent_code(code).startswith("F3")


def is_f4x(code: str) -> bool:
    """Return True when the parent code is in the F4x family."""
    return parent_code(code).startswith("F4")


def remember_required_count(disorder: str, criteria: list[dict], required: int) -> None:
    """Cache the required count for a criteria list without changing the printer signature."""
    CRITERIA_REQUIRED_CACHE[(disorder, id(criteria))] = required


def infer_required(disorder: str, criteria: list[dict]) -> int:
    """Infer the required criterion count for a disorder."""
    cached = CRITERIA_REQUIRED_CACHE.get((disorder, id(criteria)))
    if cached is not None:
        return cached

    try:
        from culturedx.ontology.icd10 import get_disorder_threshold

        threshold = get_disorder_threshold(disorder)
        if threshold.get("min_total") is not None:
            return safe_int(threshold.get("min_total"))
        if threshold.get("min_symptoms") is not None:
            return safe_int(threshold.get("min_symptoms"))
        if threshold.get("all_required"):
            return len(criteria)
        if threshold.get("core_required") and threshold.get("min_additional") is not None:
            return 1 + safe_int(threshold.get("min_additional"))
    except Exception:
        pass

    fallback_required = {
        "F32": 4,
        "F33": 4,
        "F41": 4,
        "F42": 4,
        "F43": 4,
    }
    return fallback_required.get(parent_code(disorder), min(4, len(criteria)))


def print_criteria_table(disorder: str, criteria: list[dict], indent: int = 2) -> None:
    """Print a criterion table for a single disorder."""
    pad = " " * indent
    counts = Counter(str(item.get("status", "")) for item in criteria)
    met_count = counts.get("met", 0)
    total_count = len(criteria)
    required = infer_required(disorder, criteria)
    confirmed = required > 0 and met_count >= required
    logic_label = f"{GREEN}CONFIRMED{RESET}" if confirmed else f"{RED}REJECTED{RESET}"

    print(
        f"{pad}Disorder: {CYAN}{disorder}{RESET}  "
        f"(met {met_count}/{total_count}, required {required})"
    )
    print(f"{pad}ID   Status  Conf               Evidence")
    print(f"{pad}{'-' * 74}")

    for item in criteria:
        criterion_id = str(item.get("criterion_id", "?"))
        status = str(item.get("status", "unknown"))
        evidence = truncate(item.get("evidence"), 80)
        confidence = safe_float(item.get("confidence"))
        status_text = f"{status_icon(status)} {status}"
        print(
            f"{pad}{criterion_id:<4} {status_text:<12} "
            f"{conf_bar(confidence):<20} {evidence}"
        )

    print(
        f"{pad}Logic: {met_count} met / {required} required -> {BOLD}{logic_label}{RESET}"
    )


def normalize_feature_dict(raw: dict) -> dict:
    """Normalize calibrator feature field names into a compact, script-friendly form."""
    normalized = {}
    mapping = {
        "confidence": "confidence",
        "core_score": "core_score",
        "threshold_ratio": "threshold_ratio",
        "avg_conf": "avg_conf",
        "avg_confidence": "avg_conf",
        "avg_criterion_confidence": "avg_conf",
        "evidence_cov": "evidence_cov",
        "evidence_coverage": "evidence_cov",
    }
    for source_key, target_key in mapping.items():
        if source_key in raw:
            normalized[target_key] = safe_float(raw.get(source_key))

    if "criteria_met_count" in raw:
        normalized["criteria_met_count"] = safe_int(raw.get("criteria_met_count"))
    if "criteria_total_count" in raw:
        normalized["criteria_total_count"] = safe_int(raw.get("criteria_total_count"))

    return normalized


def collect_present_calibrator_features(pred: dict) -> dict[str, dict]:
    """Collect calibrator features already present in the prediction payload."""
    feature_map: defaultdict[str, dict] = defaultdict(dict)
    explicit_feature_keys = {
        "confidence",
        "core_score",
        "threshold_ratio",
        "avg_conf",
        "avg_confidence",
        "avg_criterion_confidence",
        "evidence_cov",
        "evidence_coverage",
    }

    raw_features = pred.get("calibrator_features")
    if isinstance(raw_features, dict):
        for key, value in raw_features.items():
            if not isinstance(value, dict):
                continue
            disorder = str(value.get("disorder") or value.get("disorder_code") or key)
            feature_map[disorder].update(normalize_feature_dict(value))
    elif isinstance(raw_features, list):
        for entry in raw_features:
            if not isinstance(entry, dict):
                continue
            disorder = str(entry.get("disorder") or entry.get("disorder_code") or "")
            if disorder:
                feature_map[disorder].update(normalize_feature_dict(entry))

    for block in pred.get("criteria_results", []):
        if not isinstance(block, dict):
            continue
        disorder = str(block.get("disorder", ""))
        if not disorder:
            continue
        block_features = {
            key: block.get(key)
            for key in explicit_feature_keys
            if key in block
        }
        if block_features:
            feature_map[disorder].update(normalize_feature_dict(block_features))

    return dict(feature_map)


def simulate_calibrator_features(pred: dict) -> dict[str, dict]:
    """Optionally reconstruct calibrator features from criteria results."""
    cache_key = id(pred)
    if cache_key in SIMULATED_FEATURE_CACHE:
        return SIMULATED_FEATURE_CACHE[cache_key]

    try:
        from culturedx.core.models import CheckerOutput, CriterionResult
        from culturedx.diagnosis.calibrator import ConfidenceCalibrator

        checker_outputs = []
        for block in pred.get("criteria_results", []):
            if not isinstance(block, dict):
                continue
            criteria = []
            for item in block.get("criteria", []):
                if not isinstance(item, dict):
                    continue
                criteria.append(
                    CriterionResult(
                        criterion_id=str(item.get("criterion_id", "?")),
                        status=str(item.get("status", "insufficient_evidence")),
                        evidence=item.get("evidence"),
                        confidence=safe_float(item.get("confidence")),
                    )
                )
            checker_outputs.append(
                CheckerOutput(
                    disorder=str(block.get("disorder", "")),
                    criteria=criteria,
                    criteria_met_count=safe_int(block.get("criteria_met_count")),
                    criteria_required=safe_int(block.get("criteria_required")),
                )
            )

        calibrator = ConfidenceCalibrator(version=2)
        feature_map = {}
        for checker_output in checker_outputs:
            if not checker_output.disorder:
                continue
            cal = calibrator._compute_calibrated_v2(
                checker_output.disorder,
                checker_output,
                checker_outputs,
                evidence=None,
            )
            feature_map[checker_output.disorder] = {
                "confidence": cal.confidence,
                "core_score": cal.core_score,
                "threshold_ratio": cal.threshold_ratio,
                "avg_conf": cal.avg_criterion_confidence,
                "evidence_cov": cal.evidence_coverage,
                "criteria_met_count": cal.criteria_met_count,
                "criteria_total_count": cal.criteria_total_count,
            }
        SIMULATED_FEATURE_CACHE[cache_key] = feature_map
        return feature_map
    except Exception:
        SIMULATED_FEATURE_CACHE[cache_key] = {}
        return {}


def get_feature_map_for_comparison(pred: dict) -> tuple[dict[str, dict], str]:
    """Return the best available feature map and its source."""
    present = collect_present_calibrator_features(pred)
    if present:
        return present, "present"

    simulated = simulate_calibrator_features(pred)
    if simulated:
        return simulated, "simulated"

    return {}, "raw"


def get_feature_for_prefix(feature_map: dict[str, dict], prefix: str) -> dict | None:
    """Find a disorder feature entry by parent code prefix."""
    for disorder, feature_dict in feature_map.items():
        if parent_code(disorder) == prefix:
            return feature_dict
    return None


def find_disorder_block(pred: dict, prefix: str) -> dict | None:
    """Find a criteria_results block by parent disorder code."""
    for block in pred.get("criteria_results", []):
        disorder = str(block.get("disorder", ""))
        if parent_code(disorder) == prefix:
            return block
    return None


def format_compare_cell(item: dict | None) -> str:
    """Format one side of the F32/F41 side-by-side row."""
    if not item:
        return ""
    criterion_id = str(item.get("criterion_id", "?"))
    status = str(item.get("status", "unknown"))
    evidence = truncate(item.get("evidence"), 30)
    return f"{criterion_id:<3} {status_icon(status)} {evidence:<30}"


def criterion_map(block: dict) -> dict[str, dict]:
    """Return a criterion_id keyed mapping for a disorder block."""
    return {
        str(item.get("criterion_id", "?")): item
        for item in block.get("criteria", [])
        if isinstance(item, dict)
    }


def met_count(block: dict) -> int:
    """Count met criteria in a disorder block."""
    return sum(
        1
        for item in block.get("criteria", [])
        if isinstance(item, dict) and item.get("status") == "met"
    )


def pick_specific_met_criteria(block: dict, other_block: dict) -> list[str]:
    """Return met criteria that are unique or materially stronger than the comparison block."""
    block_map = criterion_map(block)
    other_map = criterion_map(other_block)
    selected = []

    for criterion_id, item in block_map.items():
        if item.get("status") != "met":
            continue

        other_item = other_map.get(criterion_id)
        other_status = str(other_item.get("status", "")) if other_item else ""
        other_conf = safe_float(other_item.get("confidence")) if other_item else 0.0
        this_conf = safe_float(item.get("confidence"))

        if other_item is None or other_status != "met" or this_conf >= other_conf + 0.15:
            evidence = truncate(item.get("evidence"), 45)
            selected.append(f"{criterion_id}({this_conf:.2f}): {evidence}")

    return selected


def print_f32_f41_comparison(pred: dict) -> None:
    """Print a side-by-side F32 vs F41 criterion comparison."""
    f32_block = find_disorder_block(pred, "F32")
    f41_block = find_disorder_block(pred, "F41")

    if f32_block is None or f41_block is None:
        print(f"  {YELLOW}Note:{RESET} F32/F41 comparison unavailable (missing criteria block).")
        return

    f32_criteria = list(f32_block.get("criteria", []))
    f41_criteria = list(f41_block.get("criteria", []))
    n_rows = max(len(f32_criteria), len(f41_criteria))

    print("\n  F32 CRITERIA                          | F41 CRITERIA")
    print("  ------------------------------------- | -------------------------------------")
    for index in range(n_rows):
        left_item = f32_criteria[index] if index < len(f32_criteria) else None
        right_item = f41_criteria[index] if index < len(f41_criteria) else None
        print(f"  {format_compare_cell(left_item):<37} | {format_compare_cell(right_item):<37}")

    f32_met = met_count(f32_block)
    f41_met = met_count(f41_block)
    feature_map, feature_source = get_feature_map_for_comparison(pred)
    f32_features = get_feature_for_prefix(feature_map, "F32")
    f41_features = get_feature_for_prefix(feature_map, "F41")

    if f32_features and f41_features:
        f32_conf = safe_float(f32_features.get("confidence"))
        f41_conf = safe_float(f41_features.get("confidence"))
        diff = f32_conf - f41_conf
        if diff > 0:
            leader = "F32"
        elif diff < 0:
            leader = "F41"
        else:
            leader = "neither"
        print(
            f"  Summary: met-count edge {f32_met - f41_met:+d}; "
            f"confidence diff {diff:+.3f} ({leader}, {feature_source} calibrator)."
        )
    else:
        print(f"  Summary: raw met-count diff {f32_met - f41_met:+d} (F32 - F41).")

    print(f"\n  {BOLD}KEY DISCRIMINATION ANALYSIS{RESET}")
    gold_primary = parent_code(str(pred.get("_gold_primary", "")))
    pred_primary = parent_code(str(pred.get("primary_diagnosis") or ""))
    if pred_primary == "F32" and gold_primary == "F41":
        print(f"  {RED}FALSE POSITIVE F32 (missed F41){RESET}")
    elif pred_primary == "F41" and gold_primary == "F32":
        print(f"  {RED}FALSE POSITIVE F41 (missed F32){RESET}")

    print(
        f"  F32 met {f32_met}/{len(f32_criteria)} criteria, "
        f"F41 met {f41_met}/{len(f41_criteria)} criteria"
    )

    f32_specific = pick_specific_met_criteria(f32_block, f41_block)
    f41_specific = pick_specific_met_criteria(f41_block, f32_block)

    if f32_specific:
        print("  F32-specific criteria met:")
        for item in f32_specific:
            print(f"    - {item}")
    else:
        print("  F32-specific criteria met: none")

    if f41_specific:
        print("  F41-specific criteria met:")
        for item in f41_specific:
            print(f"    - {item}")
    else:
        print("  F41-specific criteria met: none")


def print_calibrator_features(pred: dict) -> None:
    """Print any calibrator feature fields present in the prediction."""
    feature_map = collect_present_calibrator_features(pred)
    if not feature_map:
        return

    print(f"\n{BOLD}CALIBRATOR FEATURES:{RESET}")
    for block in pred.get("criteria_results", []):
        disorder = str(block.get("disorder", ""))
        if disorder not in feature_map:
            continue
        features = feature_map[disorder]
        print(
            f"  {disorder}: "
            f"core_score={safe_float(features.get('core_score')):.2f} "
            f"threshold_ratio={safe_float(features.get('threshold_ratio')):.2f} "
            f"avg_conf={safe_float(features.get('avg_conf')):.2f} "
            f"evidence_cov={safe_float(features.get('evidence_cov')):.2f}"
        )


def print_case_detail(
    case_id: str,
    gold_info: dict | None,
    pred: dict,
    condition_name: str,
    show_f41_compare: bool = False,
) -> None:
    """Print a complete deep-dive view for one case."""
    print("=" * 80)
    print(f"CASE: {case_id}   CONDITION: {condition_name}")

    gold_codes = gold_info.get("diagnoses", []) if gold_info else []
    gold_primary = parent_code(str(gold_codes[0])) if gold_codes else ""
    if gold_info is None:
        print("Gold:  (gold not found)")
    else:
        print(f"Gold:  {gold_codes}  (primary: {gold_primary or '?'})")

    pred_raw = str(pred.get("primary_diagnosis") or "")
    pred_primary = parent_code(pred_raw)
    pred_label = pred_primary or "abstain"
    raw_label = pred_raw or "abstain"
    confidence = safe_float(pred.get("confidence"))
    decision = str(pred.get("decision", "?"))
    mode = str(pred.get("mode", "?"))
    model = str(pred.get("model_name") or pred.get("model") or "?")
    language = str(pred.get("language_used") or pred.get("lang") or "?")

    if gold_primary:
        is_correct = pred_primary == gold_primary
        verdict = "CORRECT" if is_correct else "WRONG"
        verdict_color = GREEN if is_correct else RED
        verdict_text = f"{BOLD}{verdict_color}{verdict}{RESET}"
    else:
        verdict_text = f"{DIM}UNKNOWN{RESET}"

    print(
        f"Pred:  {pred_label}  (raw: {raw_label})  conf: {confidence:.3f}  "
        f"decision: {decision}  mode: {mode}  model: {model}  lang: {language}  "
        f"{verdict_text}"
    )

    comorbid = pred.get("comorbid_diagnoses", [])
    if comorbid:
        print(f"Comorbid: {comorbid}")

    print("-" * 80)
    criteria_results = pred.get("criteria_results", [])
    if not criteria_results:
        print(f"{DIM}No criteria results available.{RESET}")
    else:
        for block in criteria_results:
            disorder = str(block.get("disorder", "?"))
            criteria = list(block.get("criteria", []))
            required = safe_int(block.get("criteria_required"))
            remember_required_count(disorder, criteria, required)
            print_criteria_table(disorder, criteria)
            print()

    print_calibrator_features(pred)

    cross_family = (
        gold_primary
        and pred_primary
        and ((is_f4x(gold_primary) and is_f3x(pred_primary))
             or (is_f3x(gold_primary) and is_f4x(pred_primary)))
    )
    if show_f41_compare or cross_family:
        pred_for_compare = dict(pred)
        pred_for_compare["_gold_primary"] = gold_primary
        print_f32_f41_comparison(pred_for_compare)


def resolve_sweep_dir(raw_path: str) -> Path:
    """Resolve a sweep directory path, including glob expansion."""
    sweep_dir = Path(raw_path)
    if sweep_dir.exists():
        return sweep_dir

    matches = sorted(glob.glob(raw_path))
    if matches:
        return Path(matches[-1])

    print(f"No sweep directory found: {raw_path}", file=sys.stderr)
    sys.exit(1)


def find_condition_dirs(sweep_dir: Path) -> list[Path]:
    """Return all condition directories that contain predictions.json."""
    conditions = []
    for child in sorted(sweep_dir.iterdir()):
        if child.is_dir() and (child / "predictions.json").exists():
            conditions.append(child)
    return conditions


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Deep-dive one or more cases from a sweep")
    parser.add_argument("--sweep-dir", type=str, required=True, help="Sweep root directory")
    parser.add_argument(
        "--case-id",
        type=str,
        required=True,
        help="Comma-separated case IDs, e.g. patient_335,patient_524",
    )
    parser.add_argument(
        "--condition",
        type=str,
        default="",
        help="Condition subdirectory to inspect; default auto-detects the first match",
    )
    parser.add_argument(
        "--all-conditions",
        action="store_true",
        help="Show the listed cases across every condition with predictions.json",
    )
    parser.add_argument(
        "--f41-compare",
        action="store_true",
        help="Always show the F32 vs F41 side-by-side comparison table",
    )
    args = parser.parse_args()

    sweep_dir = resolve_sweep_dir(args.sweep_dir)
    gold_map = load_case_list(sweep_dir)
    case_ids = [item.strip() for item in args.case_id.split(",") if item.strip()]
    if not case_ids:
        print("No case IDs provided.", file=sys.stderr)
        sys.exit(1)

    if args.all_conditions:
        condition_dirs = find_condition_dirs(sweep_dir)
        if not condition_dirs:
            print("No condition directories with predictions.json found.", file=sys.stderr)
            sys.exit(1)
    elif args.condition:
        condition_dir = sweep_dir / args.condition
        pred_path = condition_dir / "predictions.json"
        if not pred_path.exists():
            print(
                f"Condition not found or missing predictions.json: {condition_dir}",
                file=sys.stderr,
            )
            sys.exit(1)
        condition_dirs = [condition_dir]
    else:
        condition_dirs = find_condition_dirs(sweep_dir)
        if not condition_dirs:
            print("No condition directories with predictions.json found.", file=sys.stderr)
            sys.exit(1)
        condition_dirs = [condition_dirs[0]]
        print(
            f"{YELLOW}Auto-detected condition:{RESET} {condition_dirs[0].name}",
            file=sys.stderr,
        )

    for condition_dir in condition_dirs:
        pred_path = condition_dir / "predictions.json"
        preds = load_predictions(pred_path)
        for case_id in case_ids:
            pred = find_prediction(preds, case_id)
            if pred is None:
                print("=" * 80)
                print(f"CASE: {case_id}   CONDITION: {condition_dir.name}")
                print(f"{RED}Prediction not found in {pred_path}{RESET}")
                continue

            gold_info = gold_map.get(case_id)
            print_case_detail(
                case_id=case_id,
                gold_info=gold_info,
                pred=pred,
                condition_name=condition_dir.name,
                show_f41_compare=args.f41_compare,
            )


if __name__ == "__main__":
    main()
