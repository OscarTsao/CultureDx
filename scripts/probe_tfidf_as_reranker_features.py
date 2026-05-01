#!/usr/bin/env python3
"""TF-IDF as reranker FEATURES (not as candidate source).

Tests whether TF-IDF probabilities, ranks, and Qwen-TFIDF-disagreement
features can be used to rerank Qwen's top-5 to improve Top-1 selection.

Compares:
  Baseline: rank-1 = primary (Qwen3 top-1)
  Logistic ranker (basic features only)
  Logistic ranker (basic + TF-IDF features)
  LightGBM ranker (full features)

Output: docs/paper/integration/GAP_F_TFIDF_RERANKER_FEATURES.md
"""
from __future__ import annotations
import json, time, random
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

REPO = Path("/home/user/YuNing/CultureDx")
AUDIT_OUT = REPO / "docs/paper/integration/GAP_F_TFIDF_RERANKER_FEATURES.md"

DOMAIN_PAIRS = {
    "F32": ["F41"], "F41": ["F32", "F42"], "F42": ["F41"],
    "F33": ["F41"], "F51": ["F32", "F41"], "F98": ["F41"],
}
PRIMARY_CLASSES = ["F32", "F33", "F41", "F42", "F45", "F51", "F98", "Z71", "F39", "F20", "F31"]


def base(c): return c.split('.')[0] if c else c


def build_dataset(qwen_recs, tfidf_lr, include_tfidf_features):
    X = []; y = []; case_ids = []; ranks = []
    for r in qwen_recs:
        gold = r.get("gold_diagnoses", [])
        if not gold: continue
        cid = str(r["case_id"])
        rk = r.get("decision_trace", {}).get("diagnostician_ranked", [])
        cf = set(base(c) for c in r.get("decision_trace", {}).get("logic_engine_confirmed_codes", []))
        mr = {co["disorder_code"]: co.get("met_ratio", 0.0) for co in r.get("decision_trace", {}).get("raw_checker_outputs", []) or []}
        primary_b = base(rk[0]) if rk else None
        for rank_pos, code in enumerate(rk[:5]):
            cb = base(code)
            feat = {
                "rank": rank_pos,
                "met_ratio": mr.get(code, 0.0),
                "in_confirmed": int(cb in cf),
                "n_confirmed": len(cf),
                "is_primary": int(rank_pos == 0),
                "in_pair_with_primary": int(cb in DOMAIN_PAIRS.get(primary_b, [])) if primary_b else 0,
            }
            for pc in PRIMARY_CLASSES:
                feat[f"is_{pc}"] = int(cb == pc)
            if include_tfidf_features and tfidf_lr.get(cid):
                tf_codes = [base(c) for c in tfidf_lr[cid].get("ranked_codes", [])[:14]]
                tf_probas = tfidf_lr[cid].get("proba_scores", [])
                tf_idx = next((i for i, c in enumerate(tf_codes) if c == cb), None)
                if tf_idx is not None and tf_idx < len(tf_probas):
                    feat["tfidf_prob"] = float(tf_probas[tf_idx])
                    feat["tfidf_rank"] = float(tf_idx)
                    feat["in_tfidf_top5"] = int(tf_idx < 5)
                    feat["in_qwen_and_tfidf_top5"] = int(rank_pos < 5 and tf_idx < 5)
                else:
                    feat["tfidf_prob"] = 0.0
                    feat["tfidf_rank"] = 99.0
                    feat["in_tfidf_top5"] = 0
                    feat["in_qwen_and_tfidf_top5"] = 0
                # Qwen-TF-IDF disagreement on top-1
                qwen_top1 = primary_b
                tfidf_top1 = tf_codes[0] if tf_codes else None
                feat["qwen_tfidf_top1_agree"] = int(qwen_top1 == tfidf_top1) if qwen_top1 and tfidf_top1 else 0
            X.append(feat)
            y.append(int(cb == base(gold[0])))
            case_ids.append(cid)
            ranks.append(rank_pos)
    return X, y, case_ids, ranks


def stratified_case_split(case_ids, seed=42):
    unique_cids = sorted(set(case_ids))
    rng = random.Random(seed)
    rng.shuffle(unique_cids)
    n_train = int(0.7 * len(unique_cids))
    train = set(unique_cids[:n_train])
    return train


def evaluate_ranker(X, y, case_ids, ranks, train_cids):
    keys = list(X[0].keys())
    X_arr = np.array([[x[k] for k in keys] for x in X])
    y_arr = np.array(y)
    train_idx = [i for i, c in enumerate(case_ids) if c in train_cids]
    test_idx = [i for i, c in enumerate(case_ids) if c not in train_cids]
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler()
    Xtr = sc.fit_transform(X_arr[train_idx])
    Xte = sc.transform(X_arr[test_idx])
    ytr = y_arr[train_idx]
    cls = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)
    cls.fit(Xtr, ytr)
    yte_proba = cls.predict_proba(Xte)[:, 1]

    by_cid = defaultdict(list)
    for i, idx in enumerate(test_idx):
        by_cid[case_ids[idx]].append((ranks[idx], y_arr[idx], yte_proba[i], keys, X_arr[idx]))

    base_top1 = 0; new_top1 = 0; n_test_cases = 0
    for cid, cands in by_cid.items():
        n_test_cases += 1
        for rank_pos, label, score, _, _ in cands:
            if rank_pos == 0 and label == 1: base_top1 += 1
        cands_sorted = sorted(cands, key=lambda x: -x[2])
        if cands_sorted and cands_sorted[0][1] == 1: new_top1 += 1
    importance = sorted(zip(keys, cls.coef_[0]), key=lambda x: -abs(x[1]))[:10]
    return {
        "n_test": n_test_cases,
        "baseline_top1": base_top1 / n_test_cases if n_test_cases else 0,
        "rerank_top1": new_top1 / n_test_cases if n_test_cases else 0,
        "delta_top1": (new_top1 - base_top1) / n_test_cases if n_test_cases else 0,
        "importance": importance,
    }


def evaluate_lgbm(X, y, case_ids, ranks, train_cids):
    try:
        import lightgbm as lgb
    except ImportError:
        return None
    keys = list(X[0].keys())
    X_arr = np.array([[x[k] for k in keys] for x in X])
    y_arr = np.array(y)
    train_idx = [i for i, c in enumerate(case_ids) if c in train_cids]
    test_idx = [i for i, c in enumerate(case_ids) if c not in train_cids]
    cls = lgb.LGBMClassifier(n_estimators=200, max_depth=6, learning_rate=0.1, n_jobs=2, verbose=-1, random_state=42)
    cls.fit(X_arr[train_idx], y_arr[train_idx])
    yte_proba = cls.predict_proba(X_arr[test_idx])[:, 1]
    by_cid = defaultdict(list)
    for i, idx in enumerate(test_idx):
        by_cid[case_ids[idx]].append((ranks[idx], y_arr[idx], yte_proba[i]))
    base_top1 = 0; new_top1 = 0; n_test_cases = 0
    for cid, cands in by_cid.items():
        n_test_cases += 1
        for rank_pos, label, score in cands:
            if rank_pos == 0 and label == 1: base_top1 += 1
        cands_sorted = sorted(cands, key=lambda x: -x[2])
        if cands_sorted and cands_sorted[0][1] == 1: new_top1 += 1
    importance = sorted(zip(keys, cls.feature_importances_), key=lambda x: -x[1])[:10]
    return {
        "n_test": n_test_cases,
        "baseline_top1": base_top1 / n_test_cases if n_test_cases else 0,
        "rerank_top1": new_top1 / n_test_cases if n_test_cases else 0,
        "delta_top1": (new_top1 - base_top1) / n_test_cases if n_test_cases else 0,
        "importance": [(k, int(v)) for k, v in importance],
    }


def main():
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[TF-IDF reranker features] starting {started}")

    qwen_recs = [json.loads(l) for l in open(REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_icd10_n1000/predictions.jsonl")]
    tfidf_lr = {str(r["case_id"]): r for r in (json.loads(l) for l in open(REPO / "results/validation/tfidf_baseline/predictions.jsonl"))}
    print(f"  Qwen: {len(qwen_recs)}, TFIDF+LR: {len(tfidf_lr)}")

    # Build datasets
    X_basic, y, cids, ranks = build_dataset(qwen_recs, tfidf_lr, include_tfidf_features=False)
    X_full, _, _, _ = build_dataset(qwen_recs, tfidf_lr, include_tfidf_features=True)
    train_cids = stratified_case_split(cids, seed=42)
    print(f"  Candidates: {len(X_basic)}, train cases: {len(train_cids)}")

    print("[basic] training logistic ranker (no TF-IDF features)...")
    basic = evaluate_ranker(X_basic, y, cids, ranks, train_cids)
    print(f"  Top-1: baseline {basic['baseline_top1']:.4f} -> rerank {basic['rerank_top1']:.4f} (Δ {basic['delta_top1']:+.4f})")

    print("[full] training logistic ranker (basic + TF-IDF features)...")
    full = evaluate_ranker(X_full, y, cids, ranks, train_cids)
    print(f"  Top-1: baseline {full['baseline_top1']:.4f} -> rerank {full['rerank_top1']:.4f} (Δ {full['delta_top1']:+.4f})")

    print("[lgbm] training LightGBM ranker (full features)...")
    lgbm = evaluate_lgbm(X_full, y, cids, ranks, train_cids)
    if lgbm:
        print(f"  Top-1: baseline {lgbm['baseline_top1']:.4f} -> rerank {lgbm['rerank_top1']:.4f} (Δ {lgbm['delta_top1']:+.4f})")

    # Render audit
    L = []
    L.append("# Gap F TF-IDF as Reranker Features (not as candidate source)")
    L.append("")
    L.append(f"**Date:** {started}")
    L.append("**Branch:** tier2b/hierarchical-prompt @ HEAD")
    L.append("**Status:** CPU-only. Uncommitted.")
    L.append("")
    L.append("## TL;DR")
    L.append("")
    L.append("Tests whether using TF-IDF probabilities/ranks/disagreement as features in a learned ranker (rather than as a candidate source) improves Top-1 selection from Qwen3 top-5.")
    L.append("")
    L.append("Train/test: 70/30 case-level split (no test-tuning), N=1000 lingxi_icd10 cases.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Reranker comparison")
    L.append("")
    L.append("| Ranker | Features | Test cases | Baseline Top-1 | Rerank Top-1 | Δ |")
    L.append("|---|---|---:|---:|---:|---:|")
    L.append(f"| Logistic | basic only (rank, met, confirmed, class one-hot) | {basic['n_test']} | {basic['baseline_top1']:.4f} | {basic['rerank_top1']:.4f} | {basic['delta_top1']:+.4f} |")
    L.append(f"| Logistic | basic + TF-IDF features | {full['n_test']} | {full['baseline_top1']:.4f} | {full['rerank_top1']:.4f} | {full['delta_top1']:+.4f} |")
    if lgbm:
        L.append(f"| LightGBM | basic + TF-IDF features | {lgbm['n_test']} | {lgbm['baseline_top1']:.4f} | {lgbm['rerank_top1']:.4f} | {lgbm['delta_top1']:+.4f} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Feature importance")
    L.append("")
    L.append("### Logistic basic (no TF-IDF features)")
    L.append("")
    L.append("| Feature | Coefficient |")
    L.append("|---|---:|")
    for k, v in basic["importance"]:
        L.append(f"| `{k}` | {v:+.4f} |")
    L.append("")
    L.append("### Logistic full (basic + TF-IDF features)")
    L.append("")
    L.append("| Feature | Coefficient |")
    L.append("|---|---:|")
    for k, v in full["importance"]:
        L.append(f"| `{k}` | {v:+.4f} |")
    L.append("")
    if lgbm:
        L.append("### LightGBM full")
        L.append("")
        L.append("| Feature | Importance (split count) |")
        L.append("|---|---:|")
        for k, v in lgbm["importance"]:
            L.append(f"| `{k}` | {v} |")
        L.append("")
    L.append("---")
    L.append("")
    L.append("## §Conclusion")
    L.append("")
    if lgbm:
        if lgbm["delta_top1"] > 0.05:
            v = f"LightGBM ranker with TF-IDF features achieves Top-1 = {lgbm['rerank_top1']:.4f} (+{100*lgbm['delta_top1']:.1f}pp over Qwen rank-1 baseline). Strong evidence that TF-IDF as reranker features is high-impact."
        elif full["delta_top1"] > 0.05:
            v = f"Logistic ranker with TF-IDF features achieves +{100*full['delta_top1']:.1f}pp Top-1 lift. TF-IDF as feature is the right architectural use."
        else:
            v = "Reranker improvements modest (<5pp). TF-IDF as feature has limited value vs as candidate source."
    else:
        if full["delta_top1"] > 0.05:
            v = f"Logistic ranker with TF-IDF features achieves +{100*full['delta_top1']:.1f}pp Top-1 lift. TF-IDF as feature is the right architectural use."
        else:
            v = "Reranker improvements modest. Need additional features or better classifier."
    L.append(v)
    L.append("")
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text("\n".join(L))
    print(f"\nAudit written: {AUDIT_OUT}")


if __name__ == "__main__":
    main()
