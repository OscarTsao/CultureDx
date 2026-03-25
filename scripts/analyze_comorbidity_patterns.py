#!/usr/bin/env python3
"""Analyze comorbidity patterns: gold vs predicted, criterion overlap, and
discriminative features for true vs false comorbidity.

Loads all hied predictions from multiple sweeps, computes:
1. True comorbidity rate in gold labels
2. Predicted comorbidity rate
3. Precision/recall by disorder pair
4. Most common comorbidity pairs (gold vs predicted)
5. Criterion overlap analysis for F32+F41 cases
6. Criterion-level features that distinguish true from false comorbidity

Usage:
    uv run python scripts/analyze_comorbidity_patterns.py
"""
from __future__ import annotations

import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.core.models import CheckerOutput, CriterionResult
from culturedx.diagnosis.calibrator import ConfidenceCalibrator
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine
from culturedx.eval.metrics import normalize_icd_code

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Sweeps with N=200 hied predictions
SWEEP_PATHS = [
    ("final_lingxidiag", "outputs/sweeps/final_lingxidiag_20260323_131847"),
    ("final_mdd5k", "outputs/sweeps/final_mdd5k_20260324_120113"),
    ("v10_lingxidiag", "outputs/sweeps/v10_lingxidiag_20260320_222603"),
    ("v10_mdd5k", "outputs/sweeps/v10_mdd5k_20260320_233729"),
    ("contrastive_on_lingxidiag", "outputs/sweeps/contrastive_on_lingxidiag_20260321_115845"),
    ("contrastive_on_mdd5k", "outputs/sweeps/contrastive_on_mdd5k_20260321_165032"),
    ("evidence_lingxidiag", "outputs/sweeps/evidence_lingxidiag_20260321_222749"),
    ("evidence_mdd5k", "outputs/sweeps/evidence_mdd5k_20260322_154253"),
]

ALL_DISORDERS = [
    "F20", "F22", "F31", "F32", "F33", "F40",
    "F41.0", "F41.1", "F42", "F43.1", "F43.2", "F45", "F51",
]

MOOD_CODES = {"F32", "F33"}
ANXIETY_CODES = {"F40", "F41", "F41.0", "F41.1"}


def parent_code(code: str) -> str:
    return code.split(".")[0]


def reconstruct_checker_outputs(pred: dict) -> list[CheckerOutput]:
    """Reconstruct CheckerOutput objects from prediction criteria_results."""
    outputs = []
    for cr_data in pred.get("criteria_results", []):
        if isinstance(cr_data, dict):
            criteria = []
            for c in cr_data.get("criteria", []):
                criteria.append(CriterionResult(
                    criterion_id=c.get("criterion_id", ""),
                    status=c.get("status", "not_met"),
                    confidence=c.get("confidence", 0.0),
                    evidence=c.get("evidence", ""),
                ))
            outputs.append(CheckerOutput(
                disorder=cr_data.get("disorder", ""),
                criteria=criteria,
                criteria_met_count=cr_data.get("criteria_met_count", 0),
                criteria_required=cr_data.get("criteria_required", 0),
            ))
    return outputs


def recompute_diagnoses(checker_outputs: list[CheckerOutput]):
    """Run logic engine + calibrator to get confirmed disorders and full calibration."""
    engine = DiagnosticLogicEngine()
    logic_output = engine.evaluate(checker_outputs)

    if not logic_output.confirmed:
        return [], {}, {}, None

    confirmation_types = {
        r.disorder_code: r.confirmation_type for r in logic_output.confirmed
    }

    cal = ConfidenceCalibrator(abstain_threshold=0.3, comorbid_threshold=0.5)
    cal_output = cal.calibrate(
        confirmed_disorders=logic_output.confirmed_codes,
        checker_outputs=checker_outputs,
        evidence=None,
        confirmation_types=confirmation_types,
    )

    confirmed_codes = []
    confidences = {}

    if cal_output.primary is not None:
        confirmed_codes.append(cal_output.primary.disorder_code)
        confidences[cal_output.primary.disorder_code] = cal_output.primary.confidence

    for c in cal_output.comorbid:
        confirmed_codes.append(c.disorder_code)
        confidences[c.disorder_code] = c.confidence

    return confirmed_codes, confidences, confirmation_types, cal_output


def load_sweep_cases(base_dir: Path) -> list[dict]:
    """Load all hied prediction cases from all sweep directories."""
    all_cases = []

    for label, sweep_path in SWEEP_PATHS:
        sweep_dir = base_dir / sweep_path
        case_list_path = sweep_dir / "case_list.json"
        if not case_list_path.exists():
            logger.info("SKIP: %s (not found)", label)
            continue

        with open(case_list_path, encoding="utf-8") as f:
            cl = json.load(f)
        gold_map = {str(c["case_id"]): c["diagnoses"] for c in cl["cases"]}

        for cond_dir in sorted(sweep_dir.iterdir()):
            if not cond_dir.is_dir() or "hied" not in cond_dir.name:
                continue
            pred_path = cond_dir / "predictions.json"
            if not pred_path.exists():
                continue

            with open(pred_path, encoding="utf-8") as f:
                raw = json.load(f)
            preds = raw["predictions"] if isinstance(raw, dict) else raw

            for pred in preds:
                case_id = str(pred["case_id"])
                if case_id not in gold_map:
                    continue

                gold_codes = gold_map[case_id]
                checker_outputs = reconstruct_checker_outputs(pred)
                if not checker_outputs:
                    continue

                confirmed, confidences, conf_types, cal_output = (
                    recompute_diagnoses(checker_outputs)
                )

                all_cases.append({
                    "sweep": label,
                    "condition": cond_dir.name,
                    "case_id": case_id,
                    "gold_codes": gold_codes,
                    "pred": pred,
                    "checker_outputs": checker_outputs,
                    "confirmed": confirmed,
                    "confidences": confidences,
                    "confirmation_types": conf_types,
                    "cal_output": cal_output,
                })

    return all_cases


def analyze_comorbidity_rates(cases: list[dict]) -> dict:
    """Compute gold and predicted comorbidity rates."""
    gold_comorbid = sum(1 for c in cases if len(c["gold_codes"]) > 1)
    pred_comorbid = sum(1 for c in cases if len(c["confirmed"]) > 1)

    n = len(cases)
    return {
        "n_total": n,
        "gold_comorbid_count": gold_comorbid,
        "gold_comorbid_rate": gold_comorbid / n if n else 0,
        "pred_comorbid_count": pred_comorbid,
        "pred_comorbid_rate": pred_comorbid / n if n else 0,
        "gold_avg_labels": float(np.mean([len(c["gold_codes"]) for c in cases])),
        "pred_avg_labels": float(np.mean([len(c["confirmed"]) for c in cases])),
    }


def analyze_pair_frequencies(cases: list[dict]) -> dict:
    """Find most common comorbidity pairs in gold and predicted."""
    gold_pairs = Counter()
    pred_pairs = Counter()

    for c in cases:
        gold_parents = sorted(set(parent_code(g) for g in c["gold_codes"]))
        pred_parents = sorted(set(parent_code(p) for p in c["confirmed"]))

        for i in range(len(gold_parents)):
            for j in range(i + 1, len(gold_parents)):
                gold_pairs[(gold_parents[i], gold_parents[j])] += 1

        for i in range(len(pred_parents)):
            for j in range(i + 1, len(pred_parents)):
                pred_pairs[(pred_parents[i], pred_parents[j])] += 1

    return {
        "gold_top_pairs": [
            {"pair": list(pair), "count": count}
            for pair, count in gold_pairs.most_common(15)
        ],
        "pred_top_pairs": [
            {"pair": list(pair), "count": count}
            for pair, count in pred_pairs.most_common(15)
        ],
    }


def analyze_pair_precision_recall(cases: list[dict]) -> dict:
    """Compute comorbidity prediction precision/recall per disorder pair."""
    pair_tp = Counter()
    pair_fp = Counter()
    pair_fn = Counter()

    for c in cases:
        gold_set = set(parent_code(g) for g in c["gold_codes"])
        pred_set = set(parent_code(p) for p in c["confirmed"])

        gold_pairs = set()
        pred_pairs = set()

        gold_list = sorted(gold_set)
        pred_list = sorted(pred_set)

        for i in range(len(gold_list)):
            for j in range(i + 1, len(gold_list)):
                gold_pairs.add((gold_list[i], gold_list[j]))

        for i in range(len(pred_list)):
            for j in range(i + 1, len(pred_list)):
                pred_pairs.add((pred_list[i], pred_list[j]))

        for pair in gold_pairs & pred_pairs:
            pair_tp[pair] += 1
        for pair in pred_pairs - gold_pairs:
            pair_fp[pair] += 1
        for pair in gold_pairs - pred_pairs:
            pair_fn[pair] += 1

    all_pairs = set(pair_tp.keys()) | set(pair_fp.keys()) | set(pair_fn.keys())
    results = []
    for pair in sorted(all_pairs):
        tp = pair_tp[pair]
        fp = pair_fp[pair]
        fn = pair_fn[pair]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        results.append({
            "pair": list(pair),
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        })

    results.sort(key=lambda r: r["tp"] + r["fn"], reverse=True)
    return {"pair_metrics": results}


def analyze_criterion_overlap(cases: list[dict]) -> dict:
    """For F32+F41 comorbid cases, analyze criterion-level overlap."""
    results = {
        "f32_f41_gold_cases": 0,
        "shared_evidence_rate": [],
        "f32_unique_criteria": [],
        "f41_unique_criteria": [],
        "f32_met_count": [],
        "f41_met_count": [],
    }

    for c in cases:
        gold_parents = set(parent_code(g) for g in c["gold_codes"])
        has_mood = bool(gold_parents & MOOD_CODES)
        has_anxiety = bool(gold_parents & {"F41"})

        if not (has_mood and has_anxiety):
            continue

        results["f32_f41_gold_cases"] += 1

        co_map = {co.disorder: co for co in c["checker_outputs"]}

        mood_co = None
        anx_co = None
        for d, co in co_map.items():
            dp = parent_code(d)
            if dp in MOOD_CODES and mood_co is None:
                mood_co = co
            if dp == "F41" and anx_co is None:
                anx_co = co

        if mood_co is None or anx_co is None:
            continue

        mood_met = [cr for cr in mood_co.criteria if cr.status == "met"]
        anx_met = [cr for cr in anx_co.criteria if cr.status == "met"]

        results["f32_met_count"].append(len(mood_met))
        results["f41_met_count"].append(len(anx_met))

        mood_evidence = set()
        for cr in mood_met:
            if cr.evidence and cr.evidence.strip():
                mood_evidence.add(cr.evidence.strip()[:200])

        anx_evidence = set()
        for cr in anx_met:
            if cr.evidence and cr.evidence.strip():
                anx_evidence.add(cr.evidence.strip()[:200])

        if mood_evidence and anx_evidence:
            shared = 0
            total_anx = len(anx_evidence)
            for ae in anx_evidence:
                ae_chars = set(ae)
                for me in mood_evidence:
                    me_chars = set(me)
                    union_set = ae_chars | me_chars
                    if union_set:
                        overlap = len(ae_chars & me_chars) / len(union_set)
                        if overlap > 0.4:
                            shared += 1
                            break

            if total_anx > 0:
                shared_rate = shared / total_anx
                results["shared_evidence_rate"].append(shared_rate)

        mood_cids = {cr.criterion_id for cr in mood_met}
        anx_cids = {cr.criterion_id for cr in anx_met}
        results["f32_unique_criteria"].append(len(mood_cids))
        results["f41_unique_criteria"].append(len(anx_cids))

    summary = {
        "f32_f41_gold_cases": results["f32_f41_gold_cases"],
    }
    if results["shared_evidence_rate"]:
        summary["mean_shared_evidence_rate"] = round(
            float(np.mean(results["shared_evidence_rate"])), 4
        )
        summary["std_shared_evidence_rate"] = round(
            float(np.std(results["shared_evidence_rate"])), 4
        )
    if results["f32_met_count"]:
        summary["mean_f32_met_count"] = round(float(np.mean(results["f32_met_count"])), 2)
        summary["mean_f41_met_count"] = round(float(np.mean(results["f41_met_count"])), 2)
    if results["f32_unique_criteria"]:
        summary["mean_f32_unique_criteria"] = round(
            float(np.mean(results["f32_unique_criteria"])), 2
        )
        summary["mean_f41_unique_criteria"] = round(
            float(np.mean(results["f41_unique_criteria"])), 2
        )

    return summary


def extract_comorbidity_features(case: dict) -> dict | None:
    """Extract per-case features for comorbidity classification."""
    confirmed = case["confirmed"]
    confidences = case["confidences"]
    checker_outputs = case["checker_outputs"]
    co_map = {co.disorder: co for co in checker_outputs}

    if len(confirmed) < 1:
        return None

    primary = confirmed[0]
    primary_conf = confidences.get(primary, 0)
    primary_co = co_map.get(primary)
    if primary_co is None:
        return None

    primary_met = [cr for cr in primary_co.criteria if cr.status == "met"]
    primary_met_count = len(primary_met)
    primary_avg_conf = (
        sum(cr.confidence for cr in primary_met) / len(primary_met)
        if primary_met else 0
    )

    has_secondary = len(confirmed) > 1
    if has_secondary:
        secondary = confirmed[1]
        secondary_conf = confidences.get(secondary, 0)
        secondary_co = co_map.get(secondary)

        if secondary_co:
            secondary_met = [cr for cr in secondary_co.criteria if cr.status == "met"]
            secondary_met_count = len(secondary_met)
            secondary_avg_conf = (
                sum(cr.confidence for cr in secondary_met) / len(secondary_met)
                if secondary_met else 0
            )
        else:
            secondary_met_count = 0
            secondary_avg_conf = 0
            secondary_conf = 0

        ratio = secondary_conf / primary_conf if primary_conf > 0 else 0

        primary_evidence_texts = set()
        for cr in primary_met:
            if cr.evidence and cr.evidence.strip():
                primary_evidence_texts.add(cr.evidence.strip()[:200])

        if secondary_co:
            sec_met = [cr for cr in secondary_co.criteria if cr.status == "met"]
            secondary_evidence_texts = set()
            for cr in sec_met:
                if cr.evidence and cr.evidence.strip():
                    secondary_evidence_texts.add(cr.evidence.strip()[:200])
        else:
            secondary_evidence_texts = set()

        shared_evidence = 0
        if secondary_evidence_texts:
            for se in secondary_evidence_texts:
                se_chars = set(se)
                for pe in primary_evidence_texts:
                    pe_chars = set(pe)
                    union_set = se_chars | pe_chars
                    if union_set and len(se_chars & pe_chars) / len(union_set) > 0.4:
                        shared_evidence += 1
                        break
            evidence_overlap = shared_evidence / len(secondary_evidence_texts)
        else:
            evidence_overlap = 0

        all_confs = [cr.confidence for cr in primary_met]
        if secondary_co:
            all_confs.extend(cr.confidence for cr in sec_met if cr.status == "met")
        conf_variance = float(np.var(all_confs)) if all_confs else 0

    else:
        secondary_conf = 0
        secondary_met_count = 0
        secondary_avg_conf = 0
        ratio = 0
        evidence_overlap = 0
        conf_variance = float(np.var([cr.confidence for cr in primary_met])) if primary_met else 0

    n_confirmed = len(confirmed)

    n_somatic_met = 0
    n_total_criteria_met = 0
    for co in checker_outputs:
        for cr in co.criteria:
            if cr.status == "met":
                n_total_criteria_met += 1
                if co.disorder == "F45" or "somatic" in cr.criterion_id.lower():
                    n_somatic_met += 1

    conf_gap = primary_conf - secondary_conf

    primary_parent = parent_code(primary)
    if has_secondary:
        secondary_parent = parent_code(confirmed[1])
        same_family = (
            (primary_parent in MOOD_CODES and secondary_parent in MOOD_CODES)
            or (primary_parent in {"F41", "F40"} and secondary_parent in {"F41", "F40"})
        )
        cross_domain = (
            (primary_parent in MOOD_CODES and secondary_parent in {"F41", "F40"})
            or (primary_parent in {"F41", "F40"} and secondary_parent in MOOD_CODES)
        )
    else:
        same_family = False
        cross_domain = False

    return {
        "primary_conf": round(primary_conf, 6),
        "secondary_conf": round(secondary_conf, 6),
        "ratio": round(ratio, 6),
        "conf_gap": round(conf_gap, 6),
        "primary_met_count": primary_met_count,
        "secondary_met_count": secondary_met_count,
        "primary_avg_conf": round(primary_avg_conf, 6),
        "secondary_avg_conf": round(secondary_avg_conf, 6),
        "evidence_overlap": round(evidence_overlap, 6),
        "conf_variance": round(conf_variance, 6),
        "n_confirmed": n_confirmed,
        "n_total_criteria_met": n_total_criteria_met,
        "n_somatic_met": n_somatic_met,
        "same_family": int(same_family),
        "cross_domain": int(cross_domain),
        "has_secondary_pred": int(has_secondary),
    }


def analyze_discriminative_features(cases: list[dict]) -> dict:
    """What features distinguish true comorbidity from false comorbidity?"""
    true_comorbid_feats = []
    false_positive_feats = []
    false_negative_feats = []
    true_single_feats = []

    for c in cases:
        gold_comorbid = len(c["gold_codes"]) > 1
        pred_comorbid = len(c["confirmed"]) > 1

        feats = extract_comorbidity_features(c)
        if feats is None:
            continue

        if gold_comorbid and pred_comorbid:
            true_comorbid_feats.append(feats)
        elif not gold_comorbid and pred_comorbid:
            false_positive_feats.append(feats)
        elif gold_comorbid and not pred_comorbid:
            false_negative_feats.append(feats)
        else:
            true_single_feats.append(feats)

    def summarize_group(feat_list: list[dict]) -> dict:
        if not feat_list:
            return {"n": 0}
        result = {"n": len(feat_list)}
        keys = feat_list[0].keys()
        for k in keys:
            vals = [f[k] for f in feat_list]
            result[f"{k}_mean"] = round(float(np.mean(vals)), 4)
            result[f"{k}_std"] = round(float(np.std(vals)), 4)
        return result

    return {
        "true_comorbid": summarize_group(true_comorbid_feats),
        "false_positive": summarize_group(false_positive_feats),
        "false_negative": summarize_group(false_negative_feats),
        "true_single": summarize_group(true_single_feats),
    }


def main() -> None:
    base_dir = Path(__file__).resolve().parent.parent

    print("=" * 80)
    print("COMORBIDITY PATTERN ANALYSIS")
    print("=" * 80)

    logger.info("Loading sweep data...")
    cases = load_sweep_cases(base_dir)
    logger.info("Loaded %d cases total", len(cases))

    if not cases:
        logger.error("No cases loaded. Exiting.")
        sys.exit(1)

    # Deduplicate: use unique (sweep, condition, case_id)
    seen = set()
    unique_cases = []
    for c in cases:
        key = (c["sweep"], c["condition"], c["case_id"])
        if key not in seen:
            seen.add(key)
            unique_cases.append(c)
    cases = unique_cases
    logger.info("After dedup: %d unique cases", len(cases))

    results = {}

    # 1. Comorbidity rates
    print("\n" + "-" * 60)
    print("1. COMORBIDITY RATES")
    print("-" * 60)
    rates = analyze_comorbidity_rates(cases)
    results["rates"] = rates
    print(f"  Total cases: {rates['n_total']}")
    print(f"  Gold comorbid: {rates['gold_comorbid_count']} ({rates['gold_comorbid_rate']:.1%})")
    print(f"  Pred comorbid: {rates['pred_comorbid_count']} ({rates['pred_comorbid_rate']:.1%})")
    print(f"  Gold avg labels: {rates['gold_avg_labels']:.2f}")
    print(f"  Pred avg labels: {rates['pred_avg_labels']:.2f}")

    # 2. Comorbidity pair frequencies
    print("\n" + "-" * 60)
    print("2. COMORBIDITY PAIR FREQUENCIES")
    print("-" * 60)
    pairs = analyze_pair_frequencies(cases)
    results["pair_frequencies"] = pairs
    print("\n  GOLD pairs (top 10):")
    for p in pairs["gold_top_pairs"][:10]:
        print(f"    {p['pair'][0]}+{p['pair'][1]}: {p['count']}")
    print("\n  PREDICTED pairs (top 10):")
    for p in pairs["pred_top_pairs"][:10]:
        print(f"    {p['pair'][0]}+{p['pair'][1]}: {p['count']}")

    # 3. Per-pair precision/recall
    print("\n" + "-" * 60)
    print("3. PAIR PRECISION/RECALL")
    print("-" * 60)
    pair_metrics = analyze_pair_precision_recall(cases)
    results["pair_precision_recall"] = pair_metrics
    print(f"  {'Pair':>12s}  {'TP':>4s}  {'FP':>4s}  {'FN':>4s}  "
          f"{'Prec':>5s}  {'Rec':>5s}  {'F1':>5s}")
    for pm in pair_metrics["pair_metrics"][:15]:
        pair_str = f"{pm['pair'][0]}+{pm['pair'][1]}"
        print(f"  {pair_str:>12s}  {pm['tp']:4d}  {pm['fp']:4d}  {pm['fn']:4d}  "
              f"{pm['precision']:5.3f}  {pm['recall']:5.3f}  {pm['f1']:5.3f}")

    # 4. Criterion overlap analysis for F32+F41
    print("\n" + "-" * 60)
    print("4. F32+F41 CRITERION OVERLAP")
    print("-" * 60)
    overlap = analyze_criterion_overlap(cases)
    results["criterion_overlap"] = overlap
    for k, v in overlap.items():
        print(f"  {k}: {v}")

    # 5. Discriminative features
    print("\n" + "-" * 60)
    print("5. DISCRIMINATIVE FEATURES (true vs false comorbidity)")
    print("-" * 60)
    disc = analyze_discriminative_features(cases)
    results["discriminative_features"] = disc

    for group_name, group_data in disc.items():
        print(f"\n  {group_name} (n={group_data['n']}):")
        if group_data["n"] == 0:
            continue
        key_features = [
            "ratio", "conf_gap", "evidence_overlap",
            "primary_met_count", "secondary_met_count",
            "primary_conf", "secondary_conf",
            "cross_domain", "same_family",
        ]
        for feat in key_features:
            mean_key = f"{feat}_mean"
            std_key = f"{feat}_std"
            if mean_key in group_data:
                print(f"    {feat:>25s}: {group_data[mean_key]:8.4f} "
                      f"(+/- {group_data[std_key]:.4f})")

    # Save
    out_path = base_dir / "outputs" / "comorbidity_analysis.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def make_serializable(obj):
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [make_serializable(v) for v in obj]
        return obj

    serializable = make_serializable(results)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {out_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
