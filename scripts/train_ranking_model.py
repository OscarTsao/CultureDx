#!/usr/bin/env python3
"""Train LightGBM evidence-aware learned ranker for disorder ranking.

Loads the parquet features from extract_ranking_features.py and trains:
1. LightGBM with objective='binary' (pointwise) - simpler, robust
2. LightGBM with objective='lambdarank' (listwise) - learns ranking directly
3. 5-fold cross-validation grouped by case_id
4. Feature importance analysis
5. Comparison: ranker Top-1 accuracy vs calibrator Top-1 accuracy

Usage:
    uv run python scripts/train_ranking_model.py
    uv run python scripts/train_ranking_model.py \
        --features outputs/ranker_features/ranking_features.parquet \
        --output-dir outputs/ranker_features
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

# Feature columns for the ranker (excludes identifiers and labels)
FEATURE_COLS = [
    # Checker features
    "criteria_met_count",
    "criteria_total",
    "criteria_required",
    "avg_confidence",
    "threshold_ratio",
    "core_score",
    "margin",
    "variance_penalty",
    "info_content",
    "min_confidence",
    "max_confidence",
    "std_confidence",
    # Evidence features
    "n_evidence_spans",
    "evidence_coverage",
    "avg_span_confidence",
    "n_disorders_with_evidence",
    "n_insufficient",
    "insufficient_ratio",
    # Somatization features
    "n_somatic_mappings",
    "somatic_criteria_met",
    # Cross-disorder features
    "confidence_margin",
    "rank_position",
    "n_confirmed_disorders",
    # Calibrator confidence (current system output)
    "calibrator_confidence",
]

# Label column
LABEL_COL = "is_gold_primary"


def compute_top1_accuracy(
    df: pd.DataFrame, score_col: str, group_cols: list[str]
) -> dict:
    """Compute Top-1 accuracy: is the highest-scored disorder the gold primary?

    Args:
        df: DataFrame with features, labels, and scores.
        score_col: Column name for the ranking score.
        group_cols: Columns to group by (case_id + dataset + condition).

    Returns:
        Dict with top1, n_cases, n_correct.
    """
    correct = 0
    total = 0
    for _, group in df.groupby(group_cols):
        if len(group) == 0:
            continue
        total += 1
        best_idx = group[score_col].idxmax()
        if group.loc[best_idx, LABEL_COL] == 1:
            correct += 1
    return {
        "top1": correct / total if total > 0 else 0.0,
        "n_cases": total,
        "n_correct": correct,
    }


def compute_flip_analysis(
    df: pd.DataFrame,
    old_score_col: str,
    new_score_col: str,
    group_cols: list[str],
) -> dict:
    """Analyze ranking flips between old and new scores."""
    flips_good = 0
    flips_bad = 0
    flip_details = []

    for name, group in df.groupby(group_cols):
        if len(group) < 2:
            continue

        old_best_idx = group[old_score_col].idxmax()
        new_best_idx = group[new_score_col].idxmax()

        old_dx = group.loc[old_best_idx, "disorder"]
        new_dx = group.loc[new_best_idx, "disorder"]

        if old_dx == new_dx:
            continue

        old_correct = group.loc[old_best_idx, LABEL_COL] == 1
        new_correct = group.loc[new_best_idx, LABEL_COL] == 1

        case_id = name[0] if isinstance(name, tuple) else name
        if new_correct and not old_correct:
            flips_good += 1
            flip_details.append({
                "case_id": case_id,
                "old": old_dx,
                "new": new_dx,
                "type": "GOOD",
            })
        elif not new_correct and old_correct:
            flips_bad += 1
            flip_details.append({
                "case_id": case_id,
                "old": old_dx,
                "new": new_dx,
                "type": "BAD",
            })

    return {
        "flips_good": flips_good,
        "flips_bad": flips_bad,
        "net_flips": flips_good - flips_bad,
        "flip_details": flip_details,
    }


def train_binary_lgbm(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray | None = None,
    y_val: np.ndarray | None = None,
) -> lgb.LGBMClassifier:
    """Train LightGBM binary classifier for pointwise ranking."""
    model = lgb.LGBMClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        min_child_samples=5,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        verbose=-1,
    )
    callbacks = []
    eval_set = None
    if X_val is not None and y_val is not None:
        eval_set = [(X_val, y_val)]
        callbacks = [lgb.early_stopping(stopping_rounds=20, verbose=False)]

    model.fit(
        X_train, y_train,
        eval_set=eval_set,
        callbacks=callbacks if callbacks else None,
    )
    return model


def train_lambdarank_lgbm(
    X_train: np.ndarray,
    y_train: np.ndarray,
    group_train: list[int],
    X_val: np.ndarray | None = None,
    y_val: np.ndarray | None = None,
    group_val: list[int] | None = None,
) -> lgb.LGBMRanker:
    """Train LightGBM LambdaRank model for listwise ranking."""
    model = lgb.LGBMRanker(
        objective="lambdarank",
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        min_child_samples=5,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        verbose=-1,
    )
    callbacks = []
    eval_set = None
    eval_group = None
    if X_val is not None and y_val is not None and group_val is not None:
        eval_set = [(X_val, y_val)]
        eval_group = [group_val]
        callbacks = [lgb.early_stopping(stopping_rounds=20, verbose=False)]

    model.fit(
        X_train, y_train,
        group=group_train,
        eval_set=eval_set,
        eval_group=eval_group,
        callbacks=callbacks if callbacks else None,
    )
    return model


def get_group_sizes(df: pd.DataFrame, group_cols: list[str]) -> list[int]:
    """Get group sizes for LambdaRank in the correct row order."""
    sizes = []
    for _, group in df.groupby(group_cols, sort=False):
        sizes.append(len(group))
    return sizes


def run_cv(
    df: pd.DataFrame,
    model_type: str,
    n_folds: int = 5,
    group_cols: list[str] | None = None,
) -> dict:
    """Run grouped k-fold cross-validation.

    Args:
        df: Full feature DataFrame.
        model_type: 'binary' or 'lambdarank'.
        n_folds: Number of folds.
        group_cols: Columns for grouping (case_id + dataset + condition).

    Returns:
        Dict with fold results and aggregated metrics.
    """
    if group_cols is None:
        group_cols = ["case_id", "dataset", "condition"]

    # Create a unique group key per case (combining case_id, dataset, condition)
    df = df.copy()
    df["_group_key"] = df[group_cols].astype(str).agg("||".join, axis=1)
    unique_groups = df["_group_key"].unique()

    gkf = GroupKFold(n_splits=min(n_folds, len(unique_groups)))
    groups = df["_group_key"].values

    X = df[FEATURE_COLS].values
    y = df[LABEL_COL].values

    fold_results = []
    all_predictions = []

    for fold_idx, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        df_test = df.iloc[test_idx].copy()

        if model_type == "binary":
            model = train_binary_lgbm(X_train, y_train)
            scores = model.predict_proba(X_test)[:, 1]
        elif model_type == "lambdarank":
            df_train = df.iloc[train_idx]
            # Build group sizes in training data order
            train_groups = []
            for _, group in df_train.groupby("_group_key", sort=False):
                train_groups.append(len(group))
            test_groups = []
            for _, group in df_test.groupby("_group_key", sort=False):
                test_groups.append(len(group))

            model = train_lambdarank_lgbm(
                X_train, y_train, train_groups,
            )
            scores = model.predict(X_test)
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        df_test["ranker_score"] = scores

        # Compute top-1 accuracy for this fold
        baseline = compute_top1_accuracy(df_test, "calibrator_confidence", group_cols)
        ranker = compute_top1_accuracy(df_test, "ranker_score", group_cols)
        flips = compute_flip_analysis(
            df_test, "calibrator_confidence", "ranker_score", group_cols
        )

        fold_result = {
            "fold": fold_idx,
            "n_test_cases": baseline["n_cases"],
            "baseline_top1": baseline["top1"],
            "ranker_top1": ranker["top1"],
            "delta_pp": round((ranker["top1"] - baseline["top1"]) * 100, 1),
            "flips_good": flips["flips_good"],
            "flips_bad": flips["flips_bad"],
            "net_flips": flips["net_flips"],
        }
        fold_results.append(fold_result)
        all_predictions.append(df_test)

        print(f"    Fold {fold_idx}: baseline={baseline['top1']:.3f}, "
              f"ranker={ranker['top1']:.3f}, "
              f"delta={fold_result['delta_pp']:+.1f}pp, "
              f"flips=+{flips['flips_good']}/-{flips['flips_bad']}")

    # Aggregate
    baseline_top1s = [r["baseline_top1"] for r in fold_results]
    ranker_top1s = [r["ranker_top1"] for r in fold_results]

    # Also compute on the full concatenated predictions
    all_preds_df = pd.concat(all_predictions, ignore_index=True)
    overall_baseline = compute_top1_accuracy(
        all_preds_df, "calibrator_confidence", group_cols
    )
    overall_ranker = compute_top1_accuracy(
        all_preds_df, "ranker_score", group_cols
    )
    overall_flips = compute_flip_analysis(
        all_preds_df, "calibrator_confidence", "ranker_score", group_cols
    )

    return {
        "model_type": model_type,
        "n_folds": len(fold_results),
        "mean_baseline_top1": float(np.mean(baseline_top1s)),
        "std_baseline_top1": float(np.std(baseline_top1s)),
        "mean_ranker_top1": float(np.mean(ranker_top1s)),
        "std_ranker_top1": float(np.std(ranker_top1s)),
        "mean_delta_pp": float(np.mean(ranker_top1s) - np.mean(baseline_top1s)) * 100,
        "overall_baseline_top1": overall_baseline["top1"],
        "overall_ranker_top1": overall_ranker["top1"],
        "overall_delta_pp": round(
            (overall_ranker["top1"] - overall_baseline["top1"]) * 100, 1
        ),
        "overall_flips_good": overall_flips["flips_good"],
        "overall_flips_bad": overall_flips["flips_bad"],
        "overall_net_flips": overall_flips["net_flips"],
        "overall_flip_details": overall_flips["flip_details"],
        "fold_results": fold_results,
    }


def train_final_model(
    df: pd.DataFrame,
    model_type: str,
    group_cols: list[str] | None = None,
) -> tuple:
    """Train final model on all data."""
    if group_cols is None:
        group_cols = ["case_id", "dataset", "condition"]

    df = df.copy()
    df["_group_key"] = df[group_cols].astype(str).agg("||".join, axis=1)

    X = df[FEATURE_COLS].values
    y = df[LABEL_COL].values

    if model_type == "binary":
        model = train_binary_lgbm(X, y)
        scores = model.predict_proba(X)[:, 1]
    elif model_type == "lambdarank":
        groups = get_group_sizes(df, ["_group_key"])
        model = train_lambdarank_lgbm(X, y, groups)
        scores = model.predict(X)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    df["ranker_score"] = scores
    return model, df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train LightGBM evidence-aware ranking model."
    )
    parser.add_argument(
        "--features",
        default="outputs/ranker_features/ranking_features.parquet",
        help="Input parquet features file",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/ranker_features",
        help="Output directory for model and report",
    )
    parser.add_argument(
        "--condition-filter",
        default=None,
        help="Only use rows from this condition (e.g., hied_no_evidence)",
    )
    args = parser.parse_args()

    features_path = Path(args.features)
    if not features_path.exists():
        print(f"ERROR: Features file not found: {features_path}")
        print("Run scripts/extract_ranking_features.py first.")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load features
    df = pd.read_parquet(features_path)
    print(f"Loaded {len(df)} rows from {features_path}")
    print(f"  Datasets: {df['dataset'].unique().tolist()}")
    print(f"  Conditions: {df['condition'].unique().tolist()}")
    print(f"  Cases: {df['case_id'].nunique()}")

    # Optional condition filter
    if args.condition_filter:
        df = df[df["condition"] == args.condition_filter].copy()
        print(f"  Filtered to condition={args.condition_filter}: {len(df)} rows")

    # Verify features exist
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"ERROR: Missing feature columns: {missing}")
        sys.exit(1)

    group_cols = ["case_id", "dataset", "condition"]

    # ==========================================
    # 1. Baseline: calibrator ranking accuracy
    # ==========================================
    print(f"\n{'='*60}")
    print("CALIBRATOR BASELINE")
    baseline = compute_top1_accuracy(df, "calibrator_confidence", group_cols)
    print(f"  Overall Top-1: {baseline['n_correct']}/{baseline['n_cases']} "
          f"= {baseline['top1']:.1%}")

    # Per-dataset baseline
    for ds_name in df["dataset"].unique():
        ds_df = df[df["dataset"] == ds_name]
        ds_baseline = compute_top1_accuracy(ds_df, "calibrator_confidence", group_cols)
        print(f"  {ds_name}: {ds_baseline['n_correct']}/{ds_baseline['n_cases']} "
              f"= {ds_baseline['top1']:.1%}")

    # Per-condition baseline
    for cond_name in df["condition"].unique():
        cond_df = df[df["condition"] == cond_name]
        cond_baseline = compute_top1_accuracy(
            cond_df, "calibrator_confidence", group_cols
        )
        print(f"  {cond_name}: {cond_baseline['n_correct']}/{cond_baseline['n_cases']} "
              f"= {cond_baseline['top1']:.1%}")

    results = {"baseline": baseline}

    # ==========================================
    # 2. 5-fold CV for each model type
    # ==========================================
    for model_type in ["binary", "lambdarank"]:
        print(f"\n{'='*60}")
        print(f"5-FOLD CV: LightGBM {model_type}")
        cv_result = run_cv(df, model_type, n_folds=5, group_cols=group_cols)
        results[f"cv_{model_type}"] = cv_result

        print(f"\n  Summary:")
        print(f"    Baseline: {cv_result['mean_baseline_top1']:.1%} "
              f"+/- {cv_result['std_baseline_top1']:.1%}")
        print(f"    Ranker:   {cv_result['mean_ranker_top1']:.1%} "
              f"+/- {cv_result['std_ranker_top1']:.1%}")
        print(f"    Delta:    {cv_result['mean_delta_pp']:+.1f}pp")
        print(f"    Overall:  baseline={cv_result['overall_baseline_top1']:.1%}, "
              f"ranker={cv_result['overall_ranker_top1']:.1%}, "
              f"delta={cv_result['overall_delta_pp']:+.1f}pp")
        print(f"    Flips:    +{cv_result['overall_flips_good']}/"
              f"-{cv_result['overall_flips_bad']} "
              f"(net={cv_result['overall_net_flips']:+d})")

        if cv_result["overall_flip_details"]:
            print(f"\n    Flip details:")
            for fd in cv_result["overall_flip_details"][:20]:
                print(f"      {fd['case_id']:20s}  {fd['old']:8s} -> {fd['new']:8s}  "
                      f"[{fd['type']}]")

    # ==========================================
    # 3. Train final model on all data + feature importance
    # ==========================================
    # Pick best model type from CV
    best_type = max(
        ["binary", "lambdarank"],
        key=lambda t: results[f"cv_{t}"]["overall_ranker_top1"],
    )
    print(f"\n{'='*60}")
    print(f"FINAL MODEL: LightGBM {best_type}")

    model, scored_df = train_final_model(df, best_type, group_cols)

    # Feature importance
    importances = model.feature_importances_
    feat_importance = sorted(
        zip(FEATURE_COLS, importances.tolist()),
        key=lambda x: -x[1],
    )

    print(f"\n  Feature importance (split count):")
    for name, imp in feat_importance:
        bar = "#" * int(imp / max(importances) * 40) if max(importances) > 0 else ""
        print(f"    {name:30s}: {imp:6.0f}  {bar}")

    # Final model accuracy on training data (upper bound)
    final_baseline = compute_top1_accuracy(scored_df, "calibrator_confidence", group_cols)
    final_ranker = compute_top1_accuracy(scored_df, "ranker_score", group_cols)
    final_flips = compute_flip_analysis(
        scored_df, "calibrator_confidence", "ranker_score", group_cols
    )

    print(f"\n  Training set accuracy (upper bound):")
    print(f"    Baseline: {final_baseline['top1']:.1%}")
    print(f"    Ranker:   {final_ranker['top1']:.1%}")
    print(f"    Flips:    +{final_flips['flips_good']}/"
          f"-{final_flips['flips_bad']} "
          f"(net={final_flips['net_flips']:+d})")

    results["final_model"] = {
        "model_type": best_type,
        "train_baseline_top1": final_baseline["top1"],
        "train_ranker_top1": final_ranker["top1"],
        "train_flips_good": final_flips["flips_good"],
        "train_flips_bad": final_flips["flips_bad"],
        "feature_importance": {n: float(i) for n, i in feat_importance},
    }

    # ==========================================
    # 4. Per-dataset and per-condition breakdown
    # ==========================================
    print(f"\n{'='*60}")
    print("PER-DATASET BREAKDOWN (final model, training data)")
    for ds_name in scored_df["dataset"].unique():
        ds_df = scored_df[scored_df["dataset"] == ds_name]
        ds_baseline = compute_top1_accuracy(ds_df, "calibrator_confidence", group_cols)
        ds_ranker = compute_top1_accuracy(ds_df, "ranker_score", group_cols)
        delta = (ds_ranker["top1"] - ds_baseline["top1"]) * 100
        print(f"  {ds_name:15s}: baseline={ds_baseline['top1']:.1%}, "
              f"ranker={ds_ranker['top1']:.1%}, delta={delta:+.1f}pp")

    print(f"\nPER-CONDITION BREAKDOWN (final model, training data)")
    for cond_name in scored_df["condition"].unique():
        cond_df = scored_df[scored_df["condition"] == cond_name]
        cond_baseline = compute_top1_accuracy(
            cond_df, "calibrator_confidence", group_cols
        )
        cond_ranker = compute_top1_accuracy(cond_df, "ranker_score", group_cols)
        delta = (cond_ranker["top1"] - cond_baseline["top1"]) * 100
        print(f"  {cond_name:30s}: baseline={cond_baseline['top1']:.1%}, "
              f"ranker={cond_ranker['top1']:.1%}, delta={delta:+.1f}pp")

    # ==========================================
    # 5. Save model and report
    # ==========================================
    # Save model
    model_path = output_dir / "ranking_model.txt"
    model.booster_.save_model(str(model_path))
    print(f"\n  Saved model to {model_path}")

    # Save report
    # Clean up non-serializable values
    def clean_for_json(obj):
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean_for_json(v) for v in obj]
        return obj

    report = clean_for_json(results)
    report["feature_columns"] = FEATURE_COLS
    report["n_features"] = len(FEATURE_COLS)
    report["n_rows"] = len(df)
    report["n_cases"] = int(df["case_id"].nunique())

    report_path = output_dir / "ranking_model_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  Saved report to {report_path}")

    # Summary
    best_cv = results[f"cv_{best_type}"]
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"  Best model: LightGBM {best_type}")
    print(f"  CV Top-1:   {best_cv['mean_ranker_top1']:.1%} "
          f"+/- {best_cv['std_ranker_top1']:.1%}")
    print(f"  Baseline:   {best_cv['mean_baseline_top1']:.1%}")
    print(f"  Delta:      {best_cv['mean_delta_pp']:+.1f}pp")
    print(f"  Top features: "
          f"{', '.join(n for n, _ in feat_importance[:5])}")


if __name__ == "__main__":
    main()
