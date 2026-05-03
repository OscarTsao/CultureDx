#!/usr/bin/env python3
"""2x2 ablation matrix: TF-IDF channel vs ML learning contribution.
Cells: A (baseline), C (no-ML linear), D (ML no-TF-IDF), E (ML full).
5-fold case-level CV, seed=42.
"""
from __future__ import annotations

import json
import time
import warnings
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from joblib import Parallel, delayed
from sklearn.model_selection import KFold

REPO = Path("/home/user/YuNing/CultureDx")
QWEN_PREDICTIONS = REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_icd10_n1000/predictions.jsonl"
TFIDF_PREDICTIONS = REPO / "results/validation/tfidf_baseline/predictions.jsonl"
OUTPUT_DOC = REPO / "docs/paper/integration/V02_ABLATION_2X2.md"
TIME_LIMIT_SECONDS = 30 * 60
SEED = 42
N_SPLITS = 5

DOMAIN_PAIRS = {
    "F32": ["F41"],
    "F41": ["F32", "F42"],
    "F42": ["F41"],
    "F33": ["F41"],
    "F51": ["F32", "F41"],
    "F98": ["F41"],
}
PRIMARY_CLASSES = ["F32", "F33", "F41", "F42", "F45", "F51", "F98", "Z71", "F39", "F20", "F31"]
BASIC_FEATURES = [
    "rank",
    "met_ratio",
    "in_confirmed",
    "n_confirmed",
    "is_primary",
    "in_pair_with_primary",
] + [f"is_{pc}" for pc in PRIMARY_CLASSES]
TFIDF_FEATURES = [
    "tfidf_prob",
    "tfidf_rank",
    "in_tfidf_top5",
    "in_qwen_and_tfidf_top5",
    "qwen_tfidf_top1_agree",
]
FULL_FEATURES = BASIC_FEATURES + TFIDF_FEATURES
QWEN_WEIGHTS = [0.3, 0.5, 0.7, 1.0, 1.5, 2.0]
TFIDF_WEIGHTS = [0.3, 0.5, 1.0, 1.5, 2.0, 3.0]


def base(c: str | None) -> str | None:
    return c.split(".")[0] if c else c


def check_timeout(start_time: float, stage: str) -> None:
    elapsed = time.monotonic() - start_time
    if elapsed > TIME_LIMIT_SECONDS:
        raise TimeoutError(
            f"Aborting before {stage}: elapsed {elapsed / 60:.1f} min exceeds 30 min limit. "
            "No partial markdown was written by this script."
        )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def qwen_ranked(record: Mapping[str, Any]) -> list[str]:
    trace = record.get("decision_trace", {}) or {}
    ranked = trace.get("diagnostician_ranked", []) or []
    return [str(code) for code in ranked if code]


def gold_primary_base(record: Mapping[str, Any]) -> str | None:
    gold = record.get("gold_diagnoses", []) or []
    return base(str(gold[0])) if gold else None


def index_qwen_by_case(qwen_recs: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r["case_id"]): r for r in qwen_recs if r.get("gold_diagnoses")}


def coerce_qwen_by_case(
    qwen_records_or_by_case: Sequence[dict[str, Any]] | Mapping[str, dict[str, Any]],
) -> Mapping[str, dict[str, Any]]:
    if isinstance(qwen_records_or_by_case, Mapping):
        return qwen_records_or_by_case
    return index_qwen_by_case(qwen_records_or_by_case)


def make_case_folds(case_ids: Iterable[str], n_splits: int = N_SPLITS, seed: int = SEED) -> list[tuple[set[str], set[str]]]:
    unique_case_ids = np.array(sorted({str(cid) for cid in case_ids}), dtype=object)
    splitter = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    folds: list[tuple[set[str], set[str]]] = []
    for train_idx, test_idx in splitter.split(unique_case_ids):
        train = set(str(cid) for cid in unique_case_ids[train_idx])
        test = set(str(cid) for cid in unique_case_ids[test_idx])
        folds.append((train, test))
    return folds


def tfidf_codes_and_scores(tfidf_record: Mapping[str, Any] | None) -> tuple[list[str], list[float]]:
    if not tfidf_record:
        return [], []
    codes = [base(str(c)) for c in (tfidf_record.get("ranked_codes", []) or [])[:14]]
    scores = [float(v) for v in (tfidf_record.get("proba_scores", []) or [])]
    return [c for c in codes if c], scores


def tfidf_score_map(tfidf_record: Mapping[str, Any] | None) -> dict[str, float]:
    codes, scores = tfidf_codes_and_scores(tfidf_record)
    return {code: scores[i] for i, code in enumerate(codes) if i < len(scores)}


def build_features(
    qwen_recs: Sequence[Mapping[str, Any]],
    tfidf_lr: Mapping[str, Mapping[str, Any]],
    include_tfidf_features: bool,
) -> tuple[list[dict[str, float]], list[int], list[str], list[int], list[str]]:
    X: list[dict[str, float]] = []
    y: list[int] = []
    case_ids: list[str] = []
    ranks: list[int] = []
    codes: list[str] = []
    for r in qwen_recs:
        gold_b = gold_primary_base(r)
        if not gold_b:
            continue
        cid = str(r["case_id"])
        rk = qwen_ranked(r)
        trace = r.get("decision_trace", {}) or {}
        cf = {base(str(c)) for c in trace.get("logic_engine_confirmed_codes", []) or [] if c}
        raw_outputs = trace.get("raw_checker_outputs", []) or []
        mr = {
            str(co.get("disorder_code")): float(co.get("met_ratio", 0.0) or 0.0)
            for co in raw_outputs
            if isinstance(co, Mapping) and co.get("disorder_code")
        }
        primary_b = base(rk[0]) if rk else None
        tf_codes, tf_probas = tfidf_codes_and_scores(tfidf_lr.get(cid))
        tfidf_top1 = tf_codes[0] if tf_codes else None
        for rank_pos, code in enumerate(rk[:5]):
            cb = base(code)
            if not cb:
                continue
            feat: dict[str, float] = {
                "rank": float(rank_pos),
                "met_ratio": float(mr.get(code, 0.0)),
                "in_confirmed": float(int(cb in cf)),
                "n_confirmed": float(len(cf)),
                "is_primary": float(int(rank_pos == 0)),
                "in_pair_with_primary": float(int(cb in DOMAIN_PAIRS.get(primary_b, []))) if primary_b else 0.0,
            }
            for pc in PRIMARY_CLASSES:
                feat[f"is_{pc}"] = float(int(cb == pc))
            if include_tfidf_features:
                tf_idx = next((i for i, c in enumerate(tf_codes) if c == cb), None)
                if tf_idx is not None and tf_idx < len(tf_probas):
                    feat["tfidf_prob"] = float(tf_probas[tf_idx])
                    feat["tfidf_rank"] = float(tf_idx)
                    feat["in_tfidf_top5"] = float(int(tf_idx < 5))
                    feat["in_qwen_and_tfidf_top5"] = float(int(rank_pos < 5 and tf_idx < 5))
                else:
                    feat["tfidf_prob"] = 0.0
                    feat["tfidf_rank"] = 99.0
                    feat["in_tfidf_top5"] = 0.0
                    feat["in_qwen_and_tfidf_top5"] = 0.0
                feat["qwen_tfidf_top1_agree"] = (
                    float(int(primary_b == tfidf_top1)) if primary_b and tfidf_top1 else 0.0
                )
            X.append(feat)
            y.append(int(cb == gold_b))
            case_ids.append(cid)
            ranks.append(rank_pos)
            codes.append(cb)
    return X, y, case_ids, ranks, codes


def matrix_from_features(X: Sequence[Mapping[str, float]], feature_names: Sequence[str]) -> np.ndarray:
    return np.asarray([[float(row.get(name, 0.0)) for name in feature_names] for row in X], dtype=float)


def evaluate_qwen_baseline(qwen_by_case: Mapping[str, Mapping[str, Any]], test_cases: set[str]) -> float:
    correct = 0
    for cid in test_cases:
        record = qwen_by_case[cid]
        ranked = qwen_ranked(record)
        pred_b = base(ranked[0]) if ranked else None
        correct += int(pred_b == gold_primary_base(record))
    return correct / len(test_cases) if test_cases else 0.0


def predict_linear_combo(
    record: Mapping[str, Any],
    tfidf_record: Mapping[str, Any] | None,
    w_qwen: float,
    w_tfidf: float,
) -> str | None:
    ranked = qwen_ranked(record)[:5]
    if not ranked:
        return None
    tf_scores = tfidf_score_map(tfidf_record)
    best_code: str | None = None
    best_score = float("-inf")
    for rank_pos, code in enumerate(ranked):
        cb = base(code)
        if not cb:
            continue
        qwen_score = 1.0 / (1.0 + rank_pos)
        combined = w_qwen * qwen_score + w_tfidf * tf_scores.get(cb, 0.0)
        if combined > best_score:
            best_score = combined
            best_code = cb
    return best_code


def evaluate_linear_combo(
    qwen_records_or_by_case: Sequence[dict[str, Any]] | Mapping[str, dict[str, Any]],
    tfidf_lr: Mapping[str, Mapping[str, Any]],
    eval_cases: set[str],
    w_qwen: float,
    w_tfidf: float,
) -> float:
    qwen_by_case = coerce_qwen_by_case(qwen_records_or_by_case)
    correct = 0
    for cid in eval_cases:
        record = qwen_by_case[cid]
        pred_b = predict_linear_combo(record, tfidf_lr.get(cid), w_qwen, w_tfidf)
        correct += int(pred_b == gold_primary_base(record))
    return correct / len(eval_cases) if eval_cases else 0.0


def select_linear_weights(
    qwen_by_case: Mapping[str, dict[str, Any]],
    tfidf_lr: Mapping[str, Mapping[str, Any]],
    train_cases: set[str],
) -> tuple[float, float, float]:
    best_acc = float("-inf")
    best_wq = QWEN_WEIGHTS[0]
    best_wt = TFIDF_WEIGHTS[0]
    for w_qwen in QWEN_WEIGHTS:
        for w_tfidf in TFIDF_WEIGHTS:
            acc = evaluate_linear_combo(qwen_by_case, tfidf_lr, train_cases, w_qwen, w_tfidf)
            if acc > best_acc:
                best_acc = acc
                best_wq = w_qwen
                best_wt = w_tfidf
    return best_wq, best_wt, best_acc


def evaluate_ml_fold(
    X_arr: np.ndarray,
    y_arr: np.ndarray,
    case_ids_arr: np.ndarray,
    ranks_arr: np.ndarray,
    train_cases: set[str],
    test_cases: set[str],
) -> float:
    import lightgbm as lgb

    train_idx = np.flatnonzero(np.isin(case_ids_arr, list(train_cases)))
    test_idx = np.flatnonzero(np.isin(case_ids_arr, list(test_cases)))
    clf = lgb.LGBMClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        n_jobs=-1,
        verbose=-1,
        random_state=SEED,
    )
    clf.fit(X_arr[train_idx], y_arr[train_idx])
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="X does not have valid feature names.*",
            category=UserWarning,
        )
        proba = clf.predict_proba(X_arr[test_idx])
    classes = list(clf.classes_)
    if 1 in classes:
        scores = proba[:, classes.index(1)]
    else:
        scores = np.zeros(len(test_idx), dtype=float)

    by_case: dict[str, list[tuple[float, int, int]]] = {cid: [] for cid in test_cases}
    for row_pos, row_idx in enumerate(test_idx):
        cid = str(case_ids_arr[row_idx])
        by_case.setdefault(cid, []).append((float(scores[row_pos]), int(y_arr[row_idx]), int(ranks_arr[row_idx])))

    correct = 0
    for cid in test_cases:
        candidates = by_case.get(cid, [])
        if not candidates:
            continue
        best = sorted(candidates, key=lambda item: (-item[0], item[2]))[0]
        correct += int(best[1] == 1)
    return correct / len(test_cases) if test_cases else 0.0


def evaluate_fold(
    fold_index: int,
    train_cases: set[str],
    test_cases: set[str],
    qwen_by_case: Mapping[str, dict[str, Any]],
    tfidf_lr: Mapping[str, Mapping[str, Any]],
    X_basic_arr: np.ndarray,
    X_full_arr: np.ndarray,
    y_arr: np.ndarray,
    case_ids_arr: np.ndarray,
    ranks_arr: np.ndarray,
) -> dict[str, Any]:
    a_acc = evaluate_qwen_baseline(qwen_by_case, test_cases)
    w_qwen, w_tfidf, c_train_acc = select_linear_weights(qwen_by_case, tfidf_lr, train_cases)
    c_acc = evaluate_linear_combo(qwen_by_case, tfidf_lr, test_cases, w_qwen, w_tfidf)
    d_acc = evaluate_ml_fold(X_basic_arr, y_arr, case_ids_arr, ranks_arr, train_cases, test_cases)
    e_acc = evaluate_ml_fold(X_full_arr, y_arr, case_ids_arr, ranks_arr, train_cases, test_cases)
    return {
        "fold": fold_index,
        "n_train": len(train_cases),
        "n_test": len(test_cases),
        "a_acc": a_acc,
        "c_acc": c_acc,
        "d_acc": d_acc,
        "e_acc": e_acc,
        "c_delta": c_acc - a_acc,
        "d_delta": d_acc - a_acc,
        "e_delta": e_acc - a_acc,
        "c_weights": (w_qwen, w_tfidf),
        "c_train_acc": c_train_acc,
    }


def mean_std(values: Sequence[float]) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    return float(arr.mean()), float(arr.std(ddof=0))


def fmt_acc(value: float) -> str:
    return f"{value:.3f}"


def fmt_acc_list(values: Sequence[float]) -> str:
    return "[" + ", ".join(fmt_acc(v) for v in values) + "]"


def fmt_delta_pp(value: float) -> str:
    return f"{value * 100:+.1f}pp"


def fmt_delta_list(values: Sequence[float]) -> str:
    return "[" + ", ".join(fmt_delta_pp(v) for v in values) + "]"


def fmt_acc_mean_std(values: Sequence[float]) -> str:
    mean, std = mean_std(values)
    return f"{mean:.3f} ± {std:.3f}"


def fmt_delta_mean_std(values: Sequence[float]) -> str:
    mean, std = mean_std(values)
    return f"{mean * 100:+.1f}pp ± {std * 100:.1f}pp"


def framing_paragraph(c_mean: float, d_mean: float, e_mean: float) -> str:
    e_minus_c = e_mean - c_mean
    e_minus_d = e_mean - d_mean
    if e_mean >= max(c_mean, d_mean) and e_minus_c > 0 and e_minus_d > 0:
        return (
            f"The clean 2x2 pattern supports framing TF-IDF as a complementary lexical channel "
            f"that is most useful when learned jointly with Qwen-derived evidence. The no-ML "
            f"linear channel alone contributes {fmt_delta_pp(c_mean)}, while Qwen-only ML contributes "
            f"{fmt_delta_pp(d_mean)}. The full Cell E lift of {fmt_delta_pp(e_mean)} exceeds both, "
            f"with {fmt_delta_pp(e_minus_c)} marginal gain over the tuned linear combo and "
            f"{fmt_delta_pp(e_minus_d)} over Qwen-only ML, so the v0.2 framing should describe the "
            f"reranker as learned evidence-channel integration rather than a simple TF-IDF fallback."
        )
    if d_mean >= c_mean and e_minus_d <= 0:
        return (
            f"The decomposition suggests most of the observed lift comes from learned use of Qwen-side "
            f"features ({fmt_delta_pp(d_mean)} without TF-IDF), while adding TF-IDF under ML changes "
            f"the result by {fmt_delta_pp(e_minus_d)}. The v0.2 framing should therefore avoid claiming "
            f"an independent lexical-channel effect beyond the learned reranker unless supported by "
            f"additional validation."
        )
    return (
        f"The decomposition separates a no-ML lexical-channel lift of {fmt_delta_pp(c_mean)} from a "
        f"Qwen-only ML lift of {fmt_delta_pp(d_mean)} and a full learned-channel lift of "
        f"{fmt_delta_pp(e_mean)}. The resulting marginals, {fmt_delta_pp(e_minus_c)} for ML given "
        f"TF-IDF and {fmt_delta_pp(e_minus_d)} for TF-IDF given ML, should be used as the paper's "
        f"primary architectural framing numbers."
    )


def render_markdown(results: Sequence[Mapping[str, Any]]) -> str:
    ordered = sorted(results, key=lambda row: int(row["fold"]))
    a_values = [float(r["a_acc"]) for r in ordered]
    c_deltas = [float(r["c_delta"]) for r in ordered]
    d_deltas = [float(r["d_delta"]) for r in ordered]
    e_deltas = [float(r["e_delta"]) for r in ordered]

    a_mean, a_std = mean_std(a_values)
    c_mean, c_std = mean_std(c_deltas)
    d_mean, d_std = mean_std(d_deltas)
    e_mean, e_std = mean_std(e_deltas)
    e_minus_c = e_mean - c_mean
    e_minus_d = e_mean - d_mean

    lines: list[str] = []
    lines.append("# v0.2 2×2 Ablation: TF-IDF Channel vs ML Learning Contribution")
    lines.append("")
    lines.append("**Date:** 2026-05-02")
    lines.append("**Protocol:** 5-fold case-level CV, seed=42, same fold assignment across all cells")
    lines.append("**Goal:** Disentangle TF-IDF lexical channel contribution from learned reranker contribution.")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| Cell | Config | Mean ± std | Per-fold deltas |")
    lines.append("|---|---|---:|---|")
    lines.append(
        f"| A | Qwen rank-1 baseline (floor) | {a_mean:.3f} ± {a_std:.3f} | {fmt_acc_list(a_values)} |"
    )
    lines.append(
        f"| C | NO-ML linear combo (per-fold tuned weights) | {c_mean * 100:+.1f}pp ± {c_std * 100:.1f}pp | {fmt_delta_list(c_deltas)} |"
    )
    lines.append(
        f"| D | ML w/o TF-IDF (Qwen features only) | {d_mean * 100:+.1f}pp ± {d_std * 100:.1f}pp | {fmt_delta_list(d_deltas)} |"
    )
    lines.append(
        f"| E | ML w/ TF-IDF (full features) | {e_mean * 100:+.1f}pp ± {e_std * 100:.1f}pp | {fmt_delta_list(e_deltas)} |"
    )
    lines.append("")
    lines.append("## Decompositions")
    lines.append("")
    lines.append("| Comparison | Value | Interpretation |")
    lines.append("|---|---:|---|")
    lines.append(f"| C − A | {fmt_delta_pp(c_mean)} | TF-IDF channel contribution without learning |")
    lines.append(f"| D − A | {fmt_delta_pp(d_mean)} | ML contribution without orthogonal channel |")
    lines.append(f"| E − C | {fmt_delta_pp(e_minus_c)} | ML's marginal contribution given TF-IDF |")
    lines.append(f"| E − D | {fmt_delta_pp(e_minus_d)} | TF-IDF channel contribution given ML |")
    lines.append("")
    lines.append("## Architectural framing implications")
    lines.append("")
    lines.append(framing_paragraph(c_mean, d_mean, e_mean))
    lines.append("")
    lines.append("## Per-fold detail")
    lines.append("")
    lines.append("| Fold | A (baseline acc) | C delta | D delta | E delta |")
    lines.append("|---:|---:|---:|---:|---:|")
    for r in ordered:
        lines.append(
            f"| {int(r['fold'])} | {float(r['a_acc']):.3f} | {fmt_delta_pp(float(r['c_delta']))} | "
            f"{fmt_delta_pp(float(r['d_delta']))} | {fmt_delta_pp(float(r['e_delta']))} |"
        )
    lines.append(
        f"| **Mean** | **{a_mean:.3f}** | **{fmt_delta_pp(c_mean)}** | **{fmt_delta_pp(d_mean)}** | **{fmt_delta_pp(e_mean)}** |"
    )
    lines.append(
        f"| **Std** | **{a_std:.3f}** | **±{c_std * 100:.1f}pp** | **±{d_std * 100:.1f}pp** | **±{e_std * 100:.1f}pp** |"
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    start_time = time.monotonic()
    print("[ablation_2x2] loading inputs")
    qwen_recs = read_jsonl(QWEN_PREDICTIONS)
    tfidf_lr = {str(r["case_id"]): r for r in read_jsonl(TFIDF_PREDICTIONS)}
    qwen_by_case = index_qwen_by_case(qwen_recs)
    check_timeout(start_time, "feature construction")

    case_ids = sorted(qwen_by_case)
    folds = make_case_folds(case_ids, n_splits=N_SPLITS, seed=SEED)
    print(f"[ablation_2x2] cases={len(case_ids)} qwen_records={len(qwen_recs)} tfidf_records={len(tfidf_lr)}")

    X_basic, y, row_case_ids, ranks, _codes = build_features(qwen_recs, tfidf_lr, include_tfidf_features=False)
    X_full, y_full, row_case_ids_full, ranks_full, _codes_full = build_features(
        qwen_recs, tfidf_lr, include_tfidf_features=True
    )
    if y_full != y or row_case_ids_full != row_case_ids or ranks_full != ranks:
        raise RuntimeError("Basic and full feature rows are not aligned")
    X_basic_arr = matrix_from_features(X_basic, BASIC_FEATURES)
    X_full_arr = matrix_from_features(X_full, FULL_FEATURES)
    y_arr = np.asarray(y, dtype=int)
    case_ids_arr = np.asarray(row_case_ids, dtype=object)
    ranks_arr = np.asarray(ranks, dtype=int)
    print(f"[ablation_2x2] candidate_rows={len(y_arr)} folds={len(folds)}")
    check_timeout(start_time, "fold evaluation")

    results = Parallel(n_jobs=5)(
        delayed(evaluate_fold)(
            fold_index,
            train_cases,
            test_cases,
            qwen_by_case,
            tfidf_lr,
            X_basic_arr,
            X_full_arr,
            y_arr,
            case_ids_arr,
            ranks_arr,
        )
        for fold_index, (train_cases, test_cases) in enumerate(folds, start=1)
    )
    check_timeout(start_time, "markdown rendering")

    markdown = render_markdown(results)
    check_timeout(start_time, "markdown write")
    OUTPUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DOC.write_text(markdown, encoding="utf-8")

    ordered = sorted(results, key=lambda row: int(row["fold"]))
    c_mean, c_std = mean_std([float(r["c_delta"]) for r in ordered])
    d_mean, d_std = mean_std([float(r["d_delta"]) for r in ordered])
    e_mean, e_std = mean_std([float(r["e_delta"]) for r in ordered])
    a_mean, a_std = mean_std([float(r["a_acc"]) for r in ordered])
    elapsed = time.monotonic() - start_time
    print(f"[ablation_2x2] wrote {OUTPUT_DOC}")
    print(f"[ablation_2x2] A={a_mean:.3f} ± {a_std:.3f}")
    print(f"[ablation_2x2] C={c_mean * 100:+.2f}pp ± {c_std * 100:.2f}pp")
    print(f"[ablation_2x2] D={d_mean * 100:+.2f}pp ± {d_std * 100:.2f}pp")
    print(f"[ablation_2x2] E={e_mean * 100:+.2f}pp ± {e_std * 100:.2f}pp")
    print(f"[ablation_2x2] elapsed={elapsed:.1f}s")


if __name__ == "__main__":
    main()
