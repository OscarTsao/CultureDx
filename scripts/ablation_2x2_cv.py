#!/usr/bin/env python3
"""2×2 ablation: TF-IDF channel vs ML learning contribution (5-fold CV)."""
from __future__ import annotations

import json
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from joblib import Parallel, delayed
from lightgbm import LGBMClassifier
from sklearn.model_selection import KFold

warnings.filterwarnings(
    "ignore",
    message="X does not have valid feature names, but LGBMClassifier was fitted with feature names",
    category=UserWarning,
)

REPO = Path("/home/user/YuNing/CultureDx")
QWEN_PATH = REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_icd10_n1000/predictions.jsonl"
TFIDF_PATH = REPO / "results/validation/tfidf_baseline/predictions.jsonl"
OUT_MD = REPO / "docs/paper/integration/V02_ABLATION_2X2.md"
PRIMARY_CLASSES = ["F32", "F33", "F41", "F42", "F45", "F51", "F98", "Z71", "F39", "F20", "F31"]
DOMAIN_PAIRS = {
    "F32": ["F41"],
    "F41": ["F32", "F42"],
    "F42": ["F41"],
    "F33": ["F41"],
    "F51": ["F32", "F41"],
    "F98": ["F41"],
}

SEED = 42
N_SPLITS = 5
N_JOBS = 5
QWEN_WEIGHTS = [0.3, 0.5, 0.7, 1.0, 1.5, 2.0]
TFIDF_WEIGHTS = [0.3, 0.5, 1.0, 1.5, 2.0, 3.0]

QWEN_FEATURES = [
    "rank",
    "met_ratio",
    "in_confirmed",
    "n_confirmed",
    "is_primary",
    "in_pair_with_primary",
] + [f"is_{code}" for code in PRIMARY_CLASSES]
TFIDF_FEATURES = [
    "tfidf_prob",
    "tfidf_rank",
    "in_tfidf_top5",
    "in_qwen_and_tfidf_top5",
    "qwen_tfidf_top1_agree",
]
FULL_FEATURES = QWEN_FEATURES + TFIDF_FEATURES


@dataclass(frozen=True)
class Fold:
    index: int
    train_cases: set[str]
    test_cases: set[str]


@dataclass(frozen=True)
class CandidateRow:
    case_id: str
    code: str
    rank: int
    label: int
    qwen_features: tuple[float, ...]
    full_features: tuple[float, ...]


def base(code: object | None) -> str | None:
    if code is None:
        return None
    text = str(code)
    return text.split(".", 1)[0] if text else None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def qwen_ranked(record: Mapping[str, Any]) -> list[str]:
    trace = record.get("decision_trace", {}) or {}
    ranked = trace.get("diagnostician_ranked", []) or []
    return [str(code) for code in ranked if code]


def qwen_candidates(record: Mapping[str, Any]) -> list[tuple[str, int]]:
    candidates: list[tuple[str, int]] = []
    for rank, code in enumerate(qwen_ranked(record)[:5]):
        code_base = base(code)
        if not code_base:
            continue
        candidates.append((code_base, rank))
    return candidates


def gold_primary(record: Mapping[str, Any]) -> str | None:
    gold = record.get("gold_diagnoses", []) or []
    return base(gold[0]) if gold else None


def tfidf_lookup(tfidf_record: Mapping[str, Any] | None) -> dict[str, tuple[float, int]]:
    if not tfidf_record:
        return {}
    ranked = tfidf_record.get("ranked_codes", []) or []
    scores = tfidf_record.get("proba_scores", []) or []
    lookup: dict[str, tuple[float, int]] = {}
    for rank, code in enumerate(ranked):
        code_base = base(code)
        if not code_base or code_base in lookup or rank >= len(scores):
            continue
        lookup[code_base] = (float(scores[rank]), rank)
    return lookup


def met_ratio_by_base(record: Mapping[str, Any]) -> dict[str, float]:
    trace = record.get("decision_trace", {}) or {}
    outputs = trace.get("raw_checker_outputs", []) or []
    ratios: dict[str, float] = {}
    for output in outputs:
        if not isinstance(output, Mapping):
            continue
        code_base = base(output.get("disorder_code"))
        if not code_base:
            continue
        ratio = float(output.get("met_ratio", 0.0) or 0.0)
        ratios[code_base] = max(ratio, ratios.get(code_base, 0.0))
    return ratios


def met_ratio_by_code(record: Mapping[str, Any]) -> dict[str, float]:
    trace = record.get("decision_trace", {}) or {}
    outputs = trace.get("raw_checker_outputs", []) or []
    ratios: dict[str, float] = {}
    for output in outputs:
        if isinstance(output, Mapping) and output.get("disorder_code"):
            ratios[str(output["disorder_code"])] = float(output.get("met_ratio", 0.0) or 0.0)
    return ratios


def confirmed_bases(record: Mapping[str, Any]) -> set[str]:
    trace = record.get("decision_trace", {}) or {}
    confirmed = trace.get("logic_engine_confirmed_codes", []) or []
    return {code_base for code in confirmed if (code_base := base(code))}


def make_folds(case_ids: Sequence[str]) -> list[Fold]:
    unique_case_ids = np.array(sorted({str(case_id) for case_id in case_ids}), dtype=object)
    splitter = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    folds: list[Fold] = []
    for fold_index, (train_idx, test_idx) in enumerate(splitter.split(unique_case_ids), start=1):
        folds.append(
            Fold(
                index=fold_index,
                train_cases={str(unique_case_ids[index]) for index in train_idx},
                test_cases={str(unique_case_ids[index]) for index in test_idx},
            )
        )
    return folds


def baseline_accuracy(qwen_by_case: Mapping[str, Mapping[str, Any]], test_cases: set[str]) -> float:
    correct = 0
    for case_id in test_cases:
        record = qwen_by_case[case_id]
        candidates = qwen_candidates(record)
        pred = candidates[0][0] if candidates else None
        correct += int(pred == gold_primary(record))
    return correct / len(test_cases)


def predict_linear_combo(
    qwen_record: Mapping[str, Any],
    tfidf_record: Mapping[str, Any] | None,
    w_qwen: float,
    w_tfidf: float,
) -> str | None:
    tfidf = tfidf_lookup(tfidf_record)
    best_code: str | None = None
    best_score = float("-inf")
    for code, rank in qwen_candidates(qwen_record):
        tfidf_prob = tfidf.get(code, (0.0, 99))[0]
        score = w_qwen * (1.0 / (rank + 1.0)) + w_tfidf * tfidf_prob
        if score > best_score:
            best_code = code
            best_score = score
    return best_code


def linear_accuracy(
    qwen_by_case: Mapping[str, Mapping[str, Any]],
    tfidf_by_case: Mapping[str, Mapping[str, Any]],
    cases: set[str],
    w_qwen: float,
    w_tfidf: float,
) -> float:
    correct = 0
    for case_id in cases:
        qwen_record = qwen_by_case[case_id]
        pred = predict_linear_combo(qwen_record, tfidf_by_case.get(case_id), w_qwen, w_tfidf)
        correct += int(pred == gold_primary(qwen_record))
    return correct / len(cases)


def tune_linear_weights(
    qwen_by_case: Mapping[str, Mapping[str, Any]],
    tfidf_by_case: Mapping[str, Mapping[str, Any]],
    train_cases: set[str],
) -> tuple[float, float, float]:
    best_acc = -1.0
    best_w_qwen = QWEN_WEIGHTS[0]
    best_w_tfidf = TFIDF_WEIGHTS[0]
    for w_qwen in QWEN_WEIGHTS:
        for w_tfidf in TFIDF_WEIGHTS:
            acc = linear_accuracy(qwen_by_case, tfidf_by_case, train_cases, w_qwen, w_tfidf)
            if acc > best_acc:
                best_acc = acc
                best_w_qwen = w_qwen
                best_w_tfidf = w_tfidf
    return best_w_qwen, best_w_tfidf, best_acc


def evaluate_c_fold(
    fold: Fold,
    qwen_by_case: Mapping[str, Mapping[str, Any]],
    tfidf_by_case: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    w_qwen, w_tfidf, train_acc = tune_linear_weights(qwen_by_case, tfidf_by_case, fold.train_cases)
    test_acc = linear_accuracy(qwen_by_case, tfidf_by_case, fold.test_cases, w_qwen, w_tfidf)
    return {
        "fold": fold.index,
        "acc": test_acc,
        "w_qwen": w_qwen,
        "w_tfidf": w_tfidf,
        "train_acc": train_acc,
    }


def build_candidate_rows(
    qwen_by_case: Mapping[str, Mapping[str, Any]],
    tfidf_by_case: Mapping[str, Mapping[str, Any]],
) -> list[CandidateRow]:
    rows: list[CandidateRow] = []
    for case_id in sorted(qwen_by_case):
        record = qwen_by_case[case_id]
        gold = gold_primary(record)
        if not gold:
            continue
        ranked = qwen_ranked(record)[:5]
        primary = base(ranked[0]) if ranked else None
        confirmed = confirmed_bases(record)
        base_ratios = met_ratio_by_base(record)
        exact_ratios = met_ratio_by_code(record)
        tfidf = tfidf_lookup(tfidf_by_case.get(case_id))
        tfidf_top1 = next(iter(tfidf), None)
        for rank, raw_code in enumerate(ranked):
            code = base(raw_code)
            if not code:
                continue
            qwen_feature_map = {
                "rank": float(rank),
                "met_ratio": exact_ratios.get(raw_code, base_ratios.get(code, 0.0)),
                "in_confirmed": float(int(code in confirmed)),
                "n_confirmed": float(len(confirmed)),
                "is_primary": float(int(rank == 0)),
                "in_pair_with_primary": float(int(primary is not None and code in DOMAIN_PAIRS.get(primary, []))),
            }
            for primary_class in PRIMARY_CLASSES:
                qwen_feature_map[f"is_{primary_class}"] = float(int(code == primary_class))
            tfidf_prob, tfidf_rank = tfidf.get(code, (0.0, 99))
            full_feature_map = {
                **qwen_feature_map,
                "tfidf_prob": float(tfidf_prob),
                "tfidf_rank": float(tfidf_rank),
                "in_tfidf_top5": float(int(tfidf_rank < 5)),
                "in_qwen_and_tfidf_top5": float(int(rank < 5 and tfidf_rank < 5)),
                "qwen_tfidf_top1_agree": float(int(primary == tfidf_top1)) if primary and tfidf_top1 else 0.0,
            }
            rows.append(
                CandidateRow(
                    case_id=case_id,
                    code=code,
                    rank=rank,
                    label=int(code == gold),
                    qwen_features=tuple(qwen_feature_map[name] for name in QWEN_FEATURES),
                    full_features=tuple(full_feature_map[name] for name in FULL_FEATURES),
                )
            )
    return rows


def evaluate_ml_fold(
    fold: Fold,
    rows: Sequence[CandidateRow],
    include_tfidf: bool,
) -> dict[str, Any]:
    train_rows = [row for row in rows if row.case_id in fold.train_cases]
    test_rows = [row for row in rows if row.case_id in fold.test_cases]
    feature_rows = [row.full_features if include_tfidf else row.qwen_features for row in train_rows]
    test_feature_rows = [row.full_features if include_tfidf else row.qwen_features for row in test_rows]
    x_train = np.asarray(feature_rows, dtype=float)
    y_train = np.asarray([row.label for row in train_rows], dtype=int)
    x_test = np.asarray(test_feature_rows, dtype=float)

    model = LGBMClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        n_jobs=-1,
        verbose=-1,
        random_state=42,
    )
    model.fit(x_train, y_train)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="X does not have valid feature names, but LGBMClassifier was fitted with feature names",
            category=UserWarning,
        )
        proba = model.predict_proba(x_test)
    classes = list(model.classes_)
    if 1 in classes:
        scores = proba[:, classes.index(1)]
    else:
        scores = np.zeros(len(test_rows), dtype=float)

    by_case: dict[str, list[tuple[float, int, int, str]]] = {case_id: [] for case_id in fold.test_cases}
    for row, score in zip(test_rows, scores, strict=True):
        by_case[row.case_id].append((float(score), row.label, row.rank, row.code))

    correct = 0
    for case_id in fold.test_cases:
        candidates = by_case.get(case_id, [])
        if not candidates:
            continue
        _score, label, _rank, _code = sorted(candidates, key=lambda item: (-item[0], item[2], item[3]))[0]
        correct += int(label == 1)
    return {"fold": fold.index, "acc": correct / len(fold.test_cases)}


def mean_std(values: Sequence[float]) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    return float(arr.mean()), float(arr.std(ddof=0))


def fmt_abs_list(values: Sequence[float]) -> str:
    return "[" + ", ".join(f"{value:.4f}" for value in values) + "]"


def fmt_pp(value: float) -> str:
    return f"{value * 100:+.2f}pp"


def fmt_pp_list(values: Sequence[float]) -> str:
    return "[" + ", ".join(fmt_pp(value) for value in values) + "]"


def framing_paragraph(mean_c: float, mean_d: float, mean_e: float) -> str:
    e_minus_c = mean_e - mean_c
    e_minus_d = mean_e - mean_d
    return (
        f"The 5-fold matrix shows that the no-ML TF-IDF channel contributes {fmt_pp(mean_c)} over the "
        f"same-fold Qwen rank-1 baseline, while the Qwen-only learned reranker contributes {fmt_pp(mean_d)}. "
        f"Adding TF-IDF to the learned reranker yields {fmt_pp(mean_e)} overall, leaving a marginal ML-given-TF-IDF "
        f"effect of {fmt_pp(e_minus_c)} and a marginal TF-IDF-given-ML effect of {fmt_pp(e_minus_d)}. These values "
        "frame v0.2 as a decomposition of lexical-channel signal versus learned candidate selection, rather than "
        "as evidence for a single undifferentiated reranking gain."
    )


def render_markdown(
    a_accs: Sequence[float],
    c_lifts: Sequence[float],
    d_lifts: Sequence[float],
    e_lifts: Sequence[float],
) -> str:
    mean_a, std_a = mean_std(a_accs)
    mean_c, std_c = mean_std(c_lifts)
    mean_d, std_d = mean_std(d_lifts)
    mean_e, std_e = mean_std(e_lifts)

    lines = [
        "# v0.2 2×2 Ablation: TF-IDF Channel vs ML Learning Contribution",
        "",
        "**Date:** 2026-05-02",
        "**Protocol:** 5-fold case-level CV, seed=42, same fold assignment across all cells",
        "**Goal:** Disentangle TF-IDF lexical channel contribution from learned reranker contribution.",
        "",
        "## Results",
        "",
        "| Cell | Config | 5-fold CV Top-1 lift | Mean ± std | Per-fold |",
        "|---|---|---:|---:|---:|",
        f"| A | Qwen rank-1 baseline | — | {mean_a:.4f} ± {std_a:.4f} abs | {fmt_abs_list(a_accs)} |",
        (
            "| C | NO-ML linear combo (per-fold tuned weights) | "
            f"{fmt_pp(mean_c)} | ± {std_c * 100:.2f}pp | {fmt_pp_list(c_lifts)} |"
        ),
        (
            "| D | ML w/o TF-IDF (Qwen features only) | "
            f"{fmt_pp(mean_d)} | ± {std_d * 100:.2f}pp | {fmt_pp_list(d_lifts)} |"
        ),
        (
            "| E | ML w/ TF-IDF (full features) | "
            f"{fmt_pp(mean_e)} | ± {std_e * 100:.2f}pp | {fmt_pp_list(e_lifts)} |"
        ),
        "",
        "## Decompositions",
        "",
        "| Comparison | Value | Interpretation |",
        "|---:|---|---|",
        f"| C − A | {fmt_pp(mean_c)} | TF-IDF channel contribution without learning |",
        f"| D − A | {fmt_pp(mean_d)} | ML contribution without orthogonal channel |",
        f"| E − C | {fmt_pp(mean_e - mean_c)} | ML's marginal contribution given TF-IDF |",
        f"| E − D | {fmt_pp(mean_e - mean_d)} | TF-IDF channel contribution given ML |",
        "",
        "## Architectural framing implications",
        "",
        framing_paragraph(mean_c, mean_d, mean_e),
        "",
        "## Per-fold detail",
        "",
        "| Fold | A baseline | C lift | D lift | E lift |",
        "|---:|---:|---:|---:|---:|",
    ]
    for fold_index, (a_acc, c_lift, d_lift, e_lift) in enumerate(
        zip(a_accs, c_lifts, d_lifts, e_lifts, strict=True),
        start=1,
    ):
        lines.append(
            f"| {fold_index} | {a_acc:.4f} | {fmt_pp(c_lift)} | {fmt_pp(d_lift)} | {fmt_pp(e_lift)} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    start = time.monotonic()
    print("[ablation_2x2_cv] loading input JSONL files")
    qwen_records = read_jsonl(QWEN_PATH)
    tfidf_records = read_jsonl(TFIDF_PATH)
    qwen_by_case = {str(record["case_id"]): record for record in qwen_records if gold_primary(record)}
    tfidf_by_case = {str(record["case_id"]): record for record in tfidf_records}

    missing_tfidf = sorted(set(qwen_by_case) - set(tfidf_by_case))
    if missing_tfidf:
        raise RuntimeError(f"Missing TF-IDF predictions for {len(missing_tfidf)} Qwen cases")

    folds = make_folds(sorted(qwen_by_case))
    print(f"[ablation_2x2_cv] cases={len(qwen_by_case)} folds={len(folds)}")

    a_accs = [baseline_accuracy(qwen_by_case, fold.test_cases) for fold in folds]

    print("[ablation_2x2_cv] evaluating cell C with fold-parallel grid search")
    c_results = Parallel(n_jobs=N_JOBS)(
        delayed(evaluate_c_fold)(fold, qwen_by_case, tfidf_by_case) for fold in folds
    )

    print("[ablation_2x2_cv] building candidate features")
    candidate_rows = build_candidate_rows(qwen_by_case, tfidf_by_case)
    print(f"[ablation_2x2_cv] candidate_rows={len(candidate_rows)}")

    print("[ablation_2x2_cv] evaluating cell D with fold-parallel LightGBM")
    d_results = Parallel(n_jobs=N_JOBS)(
        delayed(evaluate_ml_fold)(fold, candidate_rows, False) for fold in folds
    )

    print("[ablation_2x2_cv] evaluating cell E with fold-parallel LightGBM")
    e_results = Parallel(n_jobs=N_JOBS)(
        delayed(evaluate_ml_fold)(fold, candidate_rows, True) for fold in folds
    )

    c_by_fold = {int(result["fold"]): result for result in c_results}
    d_by_fold = {int(result["fold"]): result for result in d_results}
    e_by_fold = {int(result["fold"]): result for result in e_results}
    c_lifts = [float(c_by_fold[fold.index]["acc"]) - a_accs[fold.index - 1] for fold in folds]
    d_lifts = [float(d_by_fold[fold.index]["acc"]) - a_accs[fold.index - 1] for fold in folds]
    e_lifts = [float(e_by_fold[fold.index]["acc"]) - a_accs[fold.index - 1] for fold in folds]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(render_markdown(a_accs, c_lifts, d_lifts, e_lifts), encoding="utf-8")

    mean_a, std_a = mean_std(a_accs)
    mean_c, std_c = mean_std(c_lifts)
    mean_d, std_d = mean_std(d_lifts)
    mean_e, std_e = mean_std(e_lifts)
    elapsed = time.monotonic() - start
    print(f"[ablation_2x2_cv] wrote {OUT_MD}")
    print(f"[ablation_2x2_cv] A={mean_a:.4f} ± {std_a:.4f} abs; per-fold={fmt_abs_list(a_accs)}")
    print(f"[ablation_2x2_cv] C={fmt_pp(mean_c)} ± {std_c * 100:.2f}pp; per-fold={fmt_pp_list(c_lifts)}")
    print(f"[ablation_2x2_cv] D={fmt_pp(mean_d)} ± {std_d * 100:.2f}pp; per-fold={fmt_pp_list(d_lifts)}")
    print(f"[ablation_2x2_cv] E={fmt_pp(mean_e)} ± {std_e * 100:.2f}pp; per-fold={fmt_pp_list(e_lifts)}")
    for result in sorted(c_results, key=lambda item: int(item["fold"])):
        print(
            "[ablation_2x2_cv] "
            f"fold={int(result['fold'])} C weights="
            f"({float(result['w_qwen'])}, {float(result['w_tfidf'])}) train_acc={float(result['train_acc']):.4f}"
        )
    print(f"[ablation_2x2_cv] elapsed={elapsed:.1f}s")


if __name__ == "__main__":
    main()
