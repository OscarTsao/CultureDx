#!/usr/bin/env python3
"""Train evidence-based comorbidity classifier using LightGBM.

Extracts rich per-case features from checker outputs and trains a binary
classifier to distinguish true comorbidity from false comorbidity.

Uses 5-fold stratified CV and compares against ratio-based filtering
at the optimal threshold.

Usage:
    uv run python scripts/train_comorbidity_classifier.py
"""
from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from pathlib import Path

import lightgbm as lgb
import numpy as np
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    classification_report, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.core.models import CheckerOutput, CriterionResult
from culturedx.diagnosis.calibrator import ConfidenceCalibrator
from culturedx.diagnosis.comorbidity import ComorbidityResolver
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine
from culturedx.eval.metrics import compute_comorbidity_metrics

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

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
DISORDER_TO_IDX = {d: i for i, d in enumerate(ALL_DISORDERS)}

MOOD_CODES = {"F32", "F33"}
ANXIETY_CODES = {"F40", "F41", "F41.0", "F41.1"}

FEATURE_NAMES = [
    # Primary disorder features
    "primary_confidence",
    "primary_met_count",
    "primary_total_criteria",
    "primary_threshold_ratio",
    "primary_avg_criterion_conf",
    "primary_conf_variance",
    "primary_evidence_rate",
    "primary_core_met",
    # Secondary disorder features (0 if no secondary)
    "secondary_confidence",
    "secondary_met_count",
    "secondary_total_criteria",
    "secondary_threshold_ratio",
    "secondary_avg_criterion_conf",
    "secondary_conf_variance",
    "secondary_evidence_rate",
    "secondary_core_met",
    # Interaction features
    "confidence_ratio",
    "confidence_gap",
    "met_count_ratio",
    "evidence_overlap_rate",
    "shared_criterion_types",
    # Global features
    "n_disorders_confirmed",
    "n_disorders_checked",
    "total_criteria_met_all",
    "total_criteria_checked_all",
    "has_mood_confirmed",
    "has_anxiety_confirmed",
    "cross_domain_pair",
    "same_family_pair",
    # Confidence distribution features
    "conf_range_across_disorders",
    "conf_std_across_disorders",
    "third_conf_if_any",
    # Evidence features
    "primary_unique_evidence_count",
    "secondary_unique_evidence_count",
    "avg_evidence_length_primary",
    "avg_evidence_length_secondary",
]


def parent_code(code: str) -> str:
    return code.split(".")[0]


def reconstruct_checker_outputs(pred: dict) -> list[CheckerOutput]:
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


def recompute_diagnoses(checker_outputs):
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


def extract_features(pred, checker_outputs, confirmed, confidences, cal_output):
    """Extract rich feature vector for comorbidity classification."""
    co_map = {co.disorder: co for co in checker_outputs}
    features = np.zeros(len(FEATURE_NAMES))

    if not confirmed:
        return features

    primary = confirmed[0]
    primary_conf = confidences.get(primary, 0)
    primary_co = co_map.get(primary)

    # Primary features
    if primary_co:
        met = [cr for cr in primary_co.criteria if cr.status == "met"]
        features[0] = primary_conf
        features[1] = len(met)
        features[2] = len(primary_co.criteria)
        req = primary_co.criteria_required or 1
        features[3] = min(1.0, len(met) / req)
        confs = [cr.confidence for cr in met]
        features[4] = np.mean(confs) if confs else 0
        features[5] = np.var(confs) if len(confs) > 1 else 0
        features[6] = sum(1 for cr in met if cr.evidence and cr.evidence.strip()) / len(met) if met else 0
        # core criteria met (heuristic: B1, B2, B3 type patterns)
        features[7] = sum(1 for cr in met if cr.criterion_id.startswith("B"))

        primary_evidence_texts = set()
        primary_evidence_lengths = []
        for cr in met:
            if cr.evidence and cr.evidence.strip():
                primary_evidence_texts.add(cr.evidence.strip()[:200])
                primary_evidence_lengths.append(len(cr.evidence.strip()))
        features[32] = len(primary_evidence_texts)
        features[34] = np.mean(primary_evidence_lengths) if primary_evidence_lengths else 0
    else:
        primary_evidence_texts = set()

    # Secondary features
    has_secondary = len(confirmed) > 1
    if has_secondary:
        secondary = confirmed[1]
        secondary_conf = confidences.get(secondary, 0)
        secondary_co = co_map.get(secondary)

        if secondary_co:
            sec_met = [cr for cr in secondary_co.criteria if cr.status == "met"]
            features[8] = secondary_conf
            features[9] = len(sec_met)
            features[10] = len(secondary_co.criteria)
            sec_req = secondary_co.criteria_required or 1
            features[11] = min(1.0, len(sec_met) / sec_req)
            sec_confs = [cr.confidence for cr in sec_met]
            features[12] = np.mean(sec_confs) if sec_confs else 0
            features[13] = np.var(sec_confs) if len(sec_confs) > 1 else 0
            features[14] = sum(1 for cr in sec_met if cr.evidence and cr.evidence.strip()) / len(sec_met) if sec_met else 0
            features[15] = sum(1 for cr in sec_met if cr.criterion_id.startswith("B"))

            # Interaction
            features[16] = secondary_conf / primary_conf if primary_conf > 0 else 0
            features[17] = primary_conf - secondary_conf
            features[18] = len(sec_met) / features[1] if features[1] > 0 else 0

            # Evidence overlap
            secondary_evidence_texts = set()
            secondary_evidence_lengths = []
            for cr in sec_met:
                if cr.evidence and cr.evidence.strip():
                    secondary_evidence_texts.add(cr.evidence.strip()[:200])
                    secondary_evidence_lengths.append(len(cr.evidence.strip()))
            features[33] = len(secondary_evidence_texts)
            features[35] = np.mean(secondary_evidence_lengths) if secondary_evidence_lengths else 0

            if secondary_evidence_texts and primary_evidence_texts:
                shared = 0
                for se in secondary_evidence_texts:
                    se_chars = set(se)
                    for pe in primary_evidence_texts:
                        pe_chars = set(pe)
                        union_set = se_chars | pe_chars
                        if union_set and len(se_chars & pe_chars) / len(union_set) > 0.4:
                            shared += 1
                            break
                features[19] = shared / len(secondary_evidence_texts)
            else:
                features[19] = 0

            # Shared criterion type patterns
            if primary_co:
                primary_types = {cr.criterion_id[0] for cr in primary_co.criteria if cr.status == "met"}
                secondary_types = {cr.criterion_id[0] for cr in secondary_co.criteria if cr.status == "met"}
                features[20] = len(primary_types & secondary_types)

            # Domain features
            primary_parent = parent_code(primary)
            secondary_parent = parent_code(secondary)
            features[28] = int(
                (primary_parent in MOOD_CODES and secondary_parent in {"F41", "F40"})
                or (primary_parent in {"F41", "F40"} and secondary_parent in MOOD_CODES)
            )
            features[29] = int(
                (primary_parent in MOOD_CODES and secondary_parent in MOOD_CODES)
                or (primary_parent in {"F41", "F40"} and secondary_parent in {"F41", "F40"})
            )

    # Global features
    features[21] = len(confirmed)
    features[22] = len(checker_outputs)

    total_met_all = 0
    total_checked_all = 0
    for co in checker_outputs:
        total_checked_all += len(co.criteria)
        total_met_all += sum(1 for cr in co.criteria if cr.status == "met")
    features[23] = total_met_all
    features[24] = total_checked_all

    confirmed_parents = {parent_code(c) for c in confirmed}
    features[25] = int(bool(confirmed_parents & MOOD_CODES))
    features[26] = int(bool(confirmed_parents & {"F41", "F40"}))

    # Cross-domain
    features[27] = int(
        bool(confirmed_parents & MOOD_CODES) and bool(confirmed_parents & {"F41", "F40"})
    )

    # Confidence distribution across all confirmed
    all_confs = [confidences.get(c, 0) for c in confirmed]
    features[30] = max(all_confs) - min(all_confs) if len(all_confs) > 1 else 0
    features[31] = np.std(all_confs) if len(all_confs) > 1 else 0
    features[32] = all_confs[2] if len(all_confs) > 2 else 0

    return features


def load_all_data(base_dir):
    """Load and prepare all data for classification."""
    X_all = []
    y_all = []
    meta_all = []  # For subset accuracy computation

    for label, sweep_path in SWEEP_PATHS:
        sweep_dir = base_dir / sweep_path
        case_list_path = sweep_dir / "case_list.json"
        if not case_list_path.exists():
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

                confirmed, confidences, _, cal_output = recompute_diagnoses(checker_outputs)
                if not confirmed:
                    continue

                features = extract_features(
                    pred, checker_outputs, confirmed, confidences, cal_output,
                )

                # Label: does this case truly have comorbidity?
                gold_parents = set(parent_code(g) for g in gold_codes)
                has_true_comorbid = len(gold_parents) > 1

                X_all.append(features)
                y_all.append(int(has_true_comorbid))
                meta_all.append({
                    "case_id": case_id,
                    "sweep": label,
                    "condition": cond_dir.name,
                    "gold_codes": gold_codes,
                    "confirmed": confirmed,
                    "confidences": confidences,
                    "pred_has_comorbid": len(confirmed) > 1,
                })

    return np.array(X_all), np.array(y_all), meta_all


def evaluate_ratio_baseline(meta_all, y_all, ratio_threshold=0.9):
    """Evaluate the current ratio-based comorbidity filtering."""
    pred_comorbid = []
    for m in meta_all:
        if not m["pred_has_comorbid"]:
            pred_comorbid.append(0)
        else:
            resolver = ComorbidityResolver(max_comorbid=3, comorbid_min_ratio=ratio_threshold)
            result = resolver.resolve(m["confirmed"], m["confidences"])
            has_comorbid = len(result.comorbid) > 0
            pred_comorbid.append(int(has_comorbid))

    pred_comorbid = np.array(pred_comorbid)
    return {
        "accuracy": float(accuracy_score(y_all, pred_comorbid)),
        "precision": float(precision_score(y_all, pred_comorbid, zero_division=0)),
        "recall": float(recall_score(y_all, pred_comorbid, zero_division=0)),
        "f1": float(f1_score(y_all, pred_comorbid, zero_division=0)),
    }


def compute_subset_accuracy(meta_all, y_pred_comorbid):
    """Compute multi-label subset accuracy given comorbidity decisions."""
    preds_lists = []
    golds_lists = []

    for m, keep_comorbid in zip(meta_all, y_pred_comorbid):
        gold_codes = m["gold_codes"]
        confirmed = m["confirmed"]

        if keep_comorbid:
            pred_codes = list(confirmed)
        else:
            pred_codes = [confirmed[0]] if confirmed else []

        preds_lists.append(pred_codes)
        golds_lists.append(gold_codes)

    metrics = compute_comorbidity_metrics(preds_lists, golds_lists, normalize="parent")
    return metrics


def main():
    base_dir = Path(__file__).resolve().parent.parent
    np.random.seed(42)

    print("=" * 80)
    print("COMORBIDITY CLASSIFIER TRAINING (LightGBM)")
    print("=" * 80)

    logger.info("Loading data...")
    X, y, meta = load_all_data(base_dir)
    logger.info("Loaded %d cases, %d features", len(X), X.shape[1])
    logger.info("Label distribution: %s", dict(Counter(y)))
    logger.info("Positive rate: %.1f%%", y.mean() * 100)

    # Baseline: ratio=0.9
    print("\n" + "-" * 60)
    print("BASELINE: RATIO-BASED FILTERING")
    print("-" * 60)

    for ratio in [0.0, 0.7, 0.8, 0.9, 0.95, 1.0]:
        baseline = evaluate_ratio_baseline(meta, y, ratio)
        # Also compute subset accuracy
        pred_comorbid_bl = []
        for m in meta:
            if not m["pred_has_comorbid"]:
                pred_comorbid_bl.append(0)
            else:
                resolver = ComorbidityResolver(max_comorbid=3, comorbid_min_ratio=ratio)
                result = resolver.resolve(m["confirmed"], m["confidences"])
                pred_comorbid_bl.append(int(len(result.comorbid) > 0))

        subset_metrics = compute_subset_accuracy(meta, pred_comorbid_bl)
        print(f"  ratio={ratio:.2f}: acc={baseline['accuracy']:.4f} "
              f"P={baseline['precision']:.4f} R={baseline['recall']:.4f} "
              f"F1={baseline['f1']:.4f} | subset_acc={subset_metrics['subset_accuracy']:.4f}")

    # LightGBM 5-fold CV
    print("\n" + "-" * 60)
    print("LIGHTGBM 5-FOLD CROSS-VALIDATION")
    print("-" * 60)

    kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    fold_metrics = []
    fold_subset_metrics = []
    all_importances = np.zeros(X.shape[1])
    oof_predictions = np.zeros(len(y))
    oof_probas = np.zeros(len(y))

    for fold, (train_idx, test_idx) in enumerate(kf.split(X, y)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Class imbalance: scale_pos_weight
        n_neg = (y_train == 0).sum()
        n_pos = (y_train == 1).sum()
        spw = n_neg / n_pos if n_pos > 0 else 1.0

        params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "learning_rate": 0.05,
            "num_leaves": 15,
            "max_depth": 4,
            "min_child_samples": 20,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "scale_pos_weight": spw,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "verbose": -1,
            "seed": 42 + fold,
        }

        train_data = lgb.Dataset(X_train, label=y_train, feature_name=FEATURE_NAMES)
        valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

        callbacks = [
            lgb.early_stopping(stopping_rounds=30),
            lgb.log_evaluation(0),
        ]

        model = lgb.train(
            params, train_data,
            num_boost_round=500,
            valid_sets=[valid_data],
            callbacks=callbacks,
        )

        # Predictions
        probas = model.predict(X_test)
        preds = (probas > 0.5).astype(int)

        oof_predictions[test_idx] = preds
        oof_probas[test_idx] = probas

        # Feature importance
        all_importances += model.feature_importance(importance_type="gain")

        acc = accuracy_score(y_test, preds)
        prec = precision_score(y_test, preds, zero_division=0)
        rec = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        try:
            auc = roc_auc_score(y_test, probas)
        except ValueError:
            auc = 0.0

        fold_metrics.append({
            "accuracy": acc, "precision": prec, "recall": rec,
            "f1": f1, "auc": auc,
        })

        # Subset accuracy for this fold
        test_meta = [meta[i] for i in test_idx]
        subset = compute_subset_accuracy(test_meta, preds)
        fold_subset_metrics.append(subset)

        print(f"  Fold {fold+1}: acc={acc:.4f} P={prec:.4f} R={rec:.4f} "
              f"F1={f1:.4f} AUC={auc:.4f} | subset={subset['subset_accuracy']:.4f}")

    # Aggregate
    print("\n  MEAN across folds:")
    for metric_name in ["accuracy", "precision", "recall", "f1", "auc"]:
        vals = [f[metric_name] for f in fold_metrics]
        print(f"    {metric_name:>10s}: {np.mean(vals):.4f} +/- {np.std(vals):.4f}")

    subset_vals = [f["subset_accuracy"] for f in fold_subset_metrics]
    print(f"    {'subset_acc':>10s}: {np.mean(subset_vals):.4f} +/- {np.std(subset_vals):.4f}")

    # Feature importance
    print("\n" + "-" * 60)
    print("FEATURE IMPORTANCE (gain)")
    print("-" * 60)
    importance_mean = all_importances / 5
    sorted_idx = np.argsort(importance_mean)[::-1]
    for i in sorted_idx[:20]:
        if importance_mean[i] > 0:
            print(f"  {FEATURE_NAMES[i]:>35s}: {importance_mean[i]:10.2f}")

    # OOF evaluation
    print("\n" + "-" * 60)
    print("OUT-OF-FOLD EVALUATION")
    print("-" * 60)

    oof_preds_binary = (oof_predictions > 0.5).astype(int)
    print(f"  OOF Accuracy:  {accuracy_score(y, oof_preds_binary):.4f}")
    print(f"  OOF Precision: {precision_score(y, oof_preds_binary, zero_division=0):.4f}")
    print(f"  OOF Recall:    {recall_score(y, oof_preds_binary, zero_division=0):.4f}")
    print(f"  OOF F1:        {f1_score(y, oof_preds_binary, zero_division=0):.4f}")

    # OOF subset accuracy
    oof_subset = compute_subset_accuracy(meta, oof_preds_binary)
    print(f"  OOF Subset Acc: {oof_subset['subset_accuracy']:.4f}")
    print(f"  OOF Hamming:    {oof_subset['hamming_accuracy']:.4f}")
    print(f"  OOF Label Cov:  {oof_subset['label_coverage']:.4f}")
    print(f"  OOF Label Prec: {oof_subset['label_precision']:.4f}")

    # Compare with various ratio baselines at subset accuracy
    print("\n" + "-" * 60)
    print("COMPARISON: CLASSIFIER vs RATIO BASELINES (subset accuracy)")
    print("-" * 60)

    for ratio in [0.0, 0.7, 0.8, 0.9, 0.95, 1.0]:
        pred_comorbid_bl = []
        for m in meta:
            if not m["pred_has_comorbid"]:
                pred_comorbid_bl.append(0)
            else:
                resolver = ComorbidityResolver(max_comorbid=3, comorbid_min_ratio=ratio)
                result = resolver.resolve(m["confirmed"], m["confidences"])
                pred_comorbid_bl.append(int(len(result.comorbid) > 0))

        bl_subset = compute_subset_accuracy(meta, pred_comorbid_bl)
        print(f"  ratio={ratio:.2f}: subset={bl_subset['subset_accuracy']:.4f} "
              f"hamming={bl_subset['hamming_accuracy']:.4f} "
              f"cov={bl_subset['label_coverage']:.4f} "
              f"prec={bl_subset['label_precision']:.4f}")

    print(f"\n  CLASSIFIER:  subset={oof_subset['subset_accuracy']:.4f} "
          f"hamming={oof_subset['hamming_accuracy']:.4f} "
          f"cov={oof_subset['label_coverage']:.4f} "
          f"prec={oof_subset['label_precision']:.4f}")

    # Threshold sweep for the classifier
    print("\n" + "-" * 60)
    print("CLASSIFIER THRESHOLD SWEEP")
    print("-" * 60)
    best_subset = 0
    best_thresh = 0.5
    for thresh in np.arange(0.05, 0.95, 0.05):
        preds_t = (oof_probas > thresh).astype(int)
        subset_t = compute_subset_accuracy(meta, preds_t)
        f1_t = f1_score(y, preds_t, zero_division=0)
        prec_t = precision_score(y, preds_t, zero_division=0)
        rec_t = recall_score(y, preds_t, zero_division=0)
        if subset_t["subset_accuracy"] > best_subset:
            best_subset = subset_t["subset_accuracy"]
            best_thresh = thresh
        print(f"  thresh={thresh:.2f}: subset={subset_t['subset_accuracy']:.4f} "
              f"P={prec_t:.4f} R={rec_t:.4f} F1={f1_t:.4f}")

    print(f"\n  BEST threshold: {best_thresh:.2f} -> subset={best_subset:.4f}")

    # Save results
    output = {
        "n_cases": len(X),
        "n_features": int(X.shape[1]),
        "label_distribution": dict(Counter(int(v) for v in y)),
        "positive_rate": float(y.mean()),
        "ratio_baselines": {},
        "classifier_cv": {
            "mean": {m: float(np.mean([f[m] for f in fold_metrics]))
                     for m in fold_metrics[0].keys()},
            "std": {m: float(np.std([f[m] for f in fold_metrics]))
                    for m in fold_metrics[0].keys()},
        },
        "oof_metrics": {
            "accuracy": float(accuracy_score(y, oof_preds_binary)),
            "precision": float(precision_score(y, oof_preds_binary, zero_division=0)),
            "recall": float(recall_score(y, oof_preds_binary, zero_division=0)),
            "f1": float(f1_score(y, oof_preds_binary, zero_division=0)),
            "subset_accuracy": float(oof_subset["subset_accuracy"]),
            "hamming_accuracy": float(oof_subset["hamming_accuracy"]),
        },
        "best_threshold": float(best_thresh),
        "best_subset_accuracy": float(best_subset),
        "feature_importance": {
            FEATURE_NAMES[i]: round(float(importance_mean[i]), 2)
            for i in sorted_idx if importance_mean[i] > 0
        },
    }

    for ratio in [0.0, 0.7, 0.8, 0.9, 0.95, 1.0]:
        bl = evaluate_ratio_baseline(meta, y, ratio)
        pred_bl = []
        for m in meta:
            if not m["pred_has_comorbid"]:
                pred_bl.append(0)
            else:
                resolver = ComorbidityResolver(max_comorbid=3, comorbid_min_ratio=ratio)
                result = resolver.resolve(m["confirmed"], m["confidences"])
                pred_bl.append(int(len(result.comorbid) > 0))
        bl_subset = compute_subset_accuracy(meta, pred_bl)
        output["ratio_baselines"][str(ratio)] = {
            **bl,
            "subset_accuracy": float(bl_subset["subset_accuracy"]),
        }

    out_path = base_dir / "outputs" / "comorbidity_classifier_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {out_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
