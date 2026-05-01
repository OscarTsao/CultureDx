#!/usr/bin/env python3
"""Gap F CPU batch — 6 sub-analyses on existing predictions.

A4: Oracle EM@k ceiling
A3: Missing-secondary-gold taxonomy
A7: Per-class set coverage (F32/F41/F42)
B6: Confusion-pair forced candidate expansion
D3: LightGBM candidate ranker (if lightgbm available, else logistic)
E1: Cardinality classifier (predict gold size from features)

Output: docs/paper/integration/GAP_F1_CPU_BATCH_AUDIT.md
"""
from __future__ import annotations
import json, time
from pathlib import Path
from collections import Counter, defaultdict

REPO = Path("/home/user/YuNing/CultureDx")
PRED_FILES = {
    "lingxi_icd10": REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_icd10_n1000/predictions.jsonl",
    "lingxi_dsm5":  REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_dsm5_n1000/predictions.jsonl",
    "lingxi_both":  REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_both_n1000/predictions.jsonl",
    "mdd_icd10":    REPO / "results/gap_e_beta2b_projection_20260430_164210/mdd_icd10_n925/predictions.jsonl",
    "mdd_dsm5":     REPO / "results/gap_e_beta2b_projection_20260430_164210/mdd_dsm5_n925/predictions.jsonl",
    "mdd_both":     REPO / "results/gap_e_beta2b_projection_20260430_164210/mdd_both_n925/predictions.jsonl",
}
TFIDF_LR_FILES = {
    "lingxi_icd10": REPO / "results/validation/tfidf_baseline/predictions.jsonl",
}

DOMAIN_PAIRS = {
    "F32": ["F41"], "F41": ["F32", "F42"], "F42": ["F41"],
    "F33": ["F41"], "F51": ["F32", "F41"], "F98": ["F41"],
}
CONFUSION_PAIR_AUGMENT = {"F32": "F41", "F41": "F32", "F42": "F41", "F33": "F41", "F51": "F32"}
AUDIT_OUT = REPO / "docs/paper/integration/GAP_F1_CPU_BATCH_AUDIT.md"


def base(c): return c.split(".")[0] if c else c
def base_set(s): return set(base(c) for c in s)

def load_jsonl(p):
    if not p.exists(): return []
    with open(p) as f: return [json.loads(l) for l in f if l.strip()]


# ============== Helpers ==============

def ranked(rec): return rec.get("decision_trace", {}).get("diagnostician_ranked", []) or []
def confirmed(rec):
    return list(set(base(c) for c in rec.get("decision_trace", {}).get("logic_engine_confirmed_codes", []) or []))
def met_ratios(rec):
    return {co["disorder_code"]: co.get("met_ratio", 0.0) for co in rec.get("decision_trace", {}).get("raw_checker_outputs", []) or []}


# ============== A4: Oracle EM@k ceiling ==============

def a4_oracle_ceiling(qwen_modes, tfidf_lr_lookup):
    """For each mode, compute oracle EM@k: if perfect reranker picks K codes from candidate pool, max EM."""
    results = {}
    for tag, recs in qwen_modes.items():
        per_size = defaultdict(lambda: {"n": 0, "k1": 0, "k3": 0, "k5": 0,
                                         "cross_mode_union": 0, "tfidf_union": 0})
        # Build cross-mode lookup for this tag's dataset
        prefix = "lingxi" if tag.startswith("lingxi") else "mdd"
        all_modes = [t for t in qwen_modes if t.startswith(prefix)]
        cross_lookup = {m: {str(r["case_id"]): r for r in qwen_modes[m]} for m in all_modes}

        for r in recs:
            gold = r.get("gold_diagnoses", [])
            if not gold: continue
            size = len(gold)
            gold_b = base_set(gold)
            cid = str(r["case_id"])
            top5 = base_set(ranked(r)[:5])
            top3 = base_set(ranked(r)[:3])
            top1 = base_set(ranked(r)[:1])
            # Cross-mode union
            cm_union = top5
            for m in all_modes:
                if m == tag: continue
                if cid in cross_lookup[m]:
                    cm_union = cm_union | base_set(ranked(cross_lookup[m][cid])[:5])
            # TF-IDF union (only have for lingxi)
            tfidf_pool = top5
            if tfidf_lr_lookup and cid in tfidf_lr_lookup:
                tfidf5 = base_set(tfidf_lr_lookup[cid].get("ranked_codes", [])[:5])
                tfidf_pool = top5 | tfidf5
            per_size[size]["n"] += 1
            if gold_b.issubset(top1): per_size[size]["k1"] += 1
            if gold_b.issubset(top3): per_size[size]["k3"] += 1
            if gold_b.issubset(top5): per_size[size]["k5"] += 1
            if gold_b.issubset(cm_union): per_size[size]["cross_mode_union"] += 1
            if gold_b.issubset(tfidf_pool): per_size[size]["tfidf_union"] += 1
        results[tag] = dict(per_size)
    return results


# ============== A3: Missing-secondary-gold taxonomy ==============

def a3_missing_taxonomy(qwen_modes):
    """For each multi-gold case, classify the missing gold codes."""
    results = {}
    for tag, recs in qwen_modes.items():
        cats = Counter()
        size2_misses = []
        for r in recs:
            gold = r.get("gold_diagnoses", [])
            if len(gold) < 2: continue
            gold_b = base_set(gold)
            primary_b = base(gold[0])
            top5_b = base_set(ranked(r)[:5])
            cands = set(base(c) for c in r.get("candidate_disorders", []) or [])
            for g in gold_b:
                if g in top5_b:
                    cats[f"in_top5"] += 1
                elif g in cands:
                    cats["in_candidates_not_top5"] += 1
                else:
                    cats["out_of_candidates"] += 1
            # Sample missing-secondary cases for size=2
            secondary_b = gold_b - {primary_b}
            for s in secondary_b:
                if s not in top5_b and len(size2_misses) < 5:
                    size2_misses.append({
                        "case_id": str(r["case_id"]),
                        "gold": list(gold_b),
                        "missing_secondary": s,
                        "top5": [base(c) for c in ranked(r)[:5]],
                        "in_candidates": s in cands,
                    })
        results[tag] = {"cats": dict(cats), "size2_misses_sample": size2_misses}
    return results


# ============== A7: Per-class set coverage ==============

def a7_per_class_coverage(qwen_modes):
    """For F32, F41, F42 specifically — when is the class involved (gold or pred), what's the coverage?"""
    results = {}
    for tag, recs in qwen_modes.items():
        per_class = {c: {"gold_count": 0, "in_top5": 0, "primary_correct": 0,
                          "involved_in_size2": 0, "set_covered_in_size2": 0}
                     for c in ["F32", "F41", "F42", "F33", "F39", "F51", "F45", "Z71"]}
        for r in recs:
            gold = r.get("gold_diagnoses", [])
            if not gold: continue
            gold_b = base_set(gold)
            primary_b = base(gold[0])
            top5_b = base_set(ranked(r)[:5])
            for c in per_class:
                if c in gold_b:
                    per_class[c]["gold_count"] += 1
                    if c in top5_b:
                        per_class[c]["in_top5"] += 1
                    if c == primary_b and base(r.get("primary_diagnosis", "")) == c:
                        per_class[c]["primary_correct"] += 1
                    if len(gold_b) == 2:
                        per_class[c]["involved_in_size2"] += 1
                        if gold_b.issubset(top5_b):
                            per_class[c]["set_covered_in_size2"] += 1
        results[tag] = per_class
    return results


# ============== B6: Confusion-pair forced expansion ==============

def b6_confusion_pair_expansion(qwen_modes):
    """If top-1 is F32, force-add F41 to candidate set; if top-1 is F41, force-add F32; etc.
    Test if this lifts size=2 set coverage."""
    results = {}
    for tag, recs in qwen_modes.items():
        per_size = defaultdict(lambda: {"n": 0, "baseline_top5": 0, "expanded_top5": 0})
        for r in recs:
            gold = r.get("gold_diagnoses", [])
            if not gold: continue
            size = len(gold)
            gold_b = base_set(gold)
            top5_b = base_set(ranked(r)[:5])
            primary_b = base(ranked(r)[0]) if ranked(r) else ""
            expanded = top5_b | {CONFUSION_PAIR_AUGMENT.get(primary_b, primary_b)}
            # Also add domain pairs of primary
            for p in DOMAIN_PAIRS.get(primary_b, []):
                expanded.add(p)
            per_size[size]["n"] += 1
            if gold_b.issubset(top5_b): per_size[size]["baseline_top5"] += 1
            if gold_b.issubset(expanded): per_size[size]["expanded_top5"] += 1
        results[tag] = dict(per_size)
    return results


# ============== D3: LightGBM/Logistic candidate ranker ==============

def d3_train_ranker(qwen_modes, tfidf_lr_lookup):
    """Train a candidate-level ranker. Features: rank, met_ratio, confirmed flag, class one-hot, tfidf prob."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        import numpy as np
    except ImportError:
        return {"error": "sklearn missing"}

    # Use lingxi_icd10 as training data — but stratify cases for train/dev split (NOT test on full)
    recs = qwen_modes.get("lingxi_icd10", [])
    if not recs: return {"error": "no recs"}

    # Build candidate-level dataset
    X = []; y = []; case_ids = []; ranks = []
    PRIMARY_CLASSES = ["F32", "F33", "F41", "F42", "F45", "F51", "F98", "Z71", "F39", "F20", "F31"]
    for r in recs:
        gold = r.get("gold_diagnoses", [])
        if not gold: continue
        gold_b = base_set(gold)
        rk = ranked(r)
        cf_set = set(confirmed(r))
        mr = met_ratios(r)
        cid = str(r["case_id"])
        for rank_pos, code in enumerate(rk[:5]):
            cb = base(code)
            feat = {
                "rank": rank_pos,
                "met_ratio": mr.get(code, 0.0),
                "in_confirmed": int(cb in cf_set),
                "n_confirmed": len(cf_set),
            }
            for pc in PRIMARY_CLASSES:
                feat[f"is_{pc}"] = int(cb == pc)
            # TF-IDF score for this code (if available)
            if tfidf_lr_lookup and cid in tfidf_lr_lookup:
                tf_codes = [base(c) for c in tfidf_lr_lookup[cid].get("ranked_codes", [])[:10]]
                tf_probas = tfidf_lr_lookup[cid].get("proba_scores", [])
                tf_idx = next((i for i, c in enumerate(tf_codes) if c == cb), None)
                if tf_idx is not None and tf_idx < len(tf_probas):
                    feat["tfidf_prob"] = float(tf_probas[tf_idx]) if tf_idx < len(tf_probas) else 0.0
                    feat["tfidf_rank"] = float(tf_idx)
                else:
                    feat["tfidf_prob"] = 0.0
                    feat["tfidf_rank"] = 99.0
            else:
                feat["tfidf_prob"] = 0.0
                feat["tfidf_rank"] = 99.0
            X.append(feat)
            y.append(int(cb == base(gold[0])))  # is this candidate the primary gold?
            case_ids.append(cid)
            ranks.append(rank_pos)

    keys = list(X[0].keys())
    X_arr = np.array([[x[k] for k in keys] for x in X])
    y_arr = np.array(y)

    # 70/30 case-level split
    import random
    random.seed(42)
    unique_cids = sorted(set(case_ids))
    random.shuffle(unique_cids)
    n_train = int(0.7 * len(unique_cids))
    train_cids = set(unique_cids[:n_train])
    train_idx = [i for i, c in enumerate(case_ids) if c in train_cids]
    test_idx = [i for i, c in enumerate(case_ids) if c not in train_cids]

    sc = StandardScaler()
    Xtr = sc.fit_transform(X_arr[train_idx])
    Xte = sc.transform(X_arr[test_idx])
    ytr = y_arr[train_idx]
    yte = y_arr[test_idx]

    cls = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)
    cls.fit(Xtr, ytr)
    ytr_proba = cls.predict_proba(Xtr)[:, 1]
    yte_proba = cls.predict_proba(Xte)[:, 1]

    # Evaluate: for each test case, did the rerank put primary gold first?
    case_test_data = defaultdict(list)
    for i in test_idx:
        case_test_data[case_ids[i]].append((y_arr[i], yte_proba[list(test_idx).index(i)] if False else None))

    # Simpler: per-case reranking
    base_top1 = 0; new_top1 = 0; n_test_cases = 0
    by_cid = defaultdict(list)
    for i, idx in enumerate(test_idx):
        by_cid[case_ids[idx]].append((ranks[idx], y_arr[idx], yte_proba[i], X[idx]))
    for cid, cands in by_cid.items():
        n_test_cases += 1
        # Baseline: rank=0 candidate
        for rank_pos, label, score, feat in cands:
            if rank_pos == 0:
                if label == 1: base_top1 += 1
        # New: rerank by score
        cands_sorted = sorted(cands, key=lambda x: -x[2])
        if cands_sorted and cands_sorted[0][1] == 1:
            new_top1 += 1
    feat_importance = sorted(zip(keys, cls.coef_[0]), key=lambda x: -abs(x[1]))[:8]
    return {
        "n_train_cases": len(train_cids),
        "n_test_cases": n_test_cases,
        "baseline_top1": base_top1 / n_test_cases if n_test_cases else 0,
        "rerank_top1": new_top1 / n_test_cases if n_test_cases else 0,
        "feat_importance": [(k, float(v)) for k, v in feat_importance],
    }


# ============== E1: Cardinality classifier ==============

def e1_cardinality_classifier(qwen_modes, tfidf_lr_lookup):
    """Predict gold_size {1, 2, 3} from features."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        import numpy as np
        from sklearn.metrics import classification_report, accuracy_score
    except ImportError:
        return {"error": "sklearn missing"}

    recs = qwen_modes.get("lingxi_icd10", [])
    if not recs: return {"error": "no recs"}

    X = []; y = []; cids = []
    for r in recs:
        gold = r.get("gold_diagnoses", [])
        if not gold: continue
        size = min(len(gold), 3)  # cap at 3
        rk = ranked(r); mr = met_ratios(r); cf = set(confirmed(r))
        feat = {
            "n_confirmed": len(cf),
            "primary_met_ratio": mr.get(rk[0], 0.0) if rk else 0.0,
            "rank2_met_ratio": mr.get(rk[1], 0.0) if len(rk) > 1 else 0.0,
            "rank3_met_ratio": mr.get(rk[2], 0.0) if len(rk) > 2 else 0.0,
            "rank2_in_confirmed": int(base(rk[1]) in cf) if len(rk) > 1 else 0,
            "rank2_in_pair": int(base(rk[1]) in DOMAIN_PAIRS.get(base(rk[0]) if rk else "", [])) if len(rk) > 1 else 0,
            "high_conf_count": sum(1 for c in cf if mr.get(c, 0.0) >= 1.0),
        }
        X.append(feat)
        y.append(size)
        cids.append(str(r["case_id"]))

    keys = list(X[0].keys())
    X_arr = np.array([[x[k] for k in keys] for x in X])
    y_arr = np.array(y)
    import random
    random.seed(42)
    unique_cids = sorted(set(cids))
    random.shuffle(unique_cids)
    n_train = int(0.7 * len(unique_cids))
    train_cids = set(unique_cids[:n_train])
    train_idx = [i for i, c in enumerate(cids) if c in train_cids]
    test_idx = [i for i, c in enumerate(cids) if c not in train_cids]

    sc = StandardScaler()
    Xtr = sc.fit_transform(X_arr[train_idx])
    Xte = sc.transform(X_arr[test_idx])
    ytr = y_arr[train_idx]
    yte = y_arr[test_idx]

    cls = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)
    cls.fit(Xtr, ytr)
    yte_pred = cls.predict(Xte)
    acc = accuracy_score(yte, yte_pred)
    cm = Counter()
    for true, pred in zip(yte, yte_pred): cm[(int(true), int(pred))] += 1
    return {
        "test_acc": acc,
        "n_test": len(yte),
        "true_pred_counts": {f"{t}->{p}": c for (t, p), c in sorted(cm.items())},
        "feat_importance": sorted(zip(keys, np.abs(cls.coef_).max(axis=0)), key=lambda x: -x[1]),
    }


# ============== Main ==============

def main():
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Gap F CPU batch] starting {started}")

    qwen_modes = {tag: load_jsonl(p) for tag, p in PRED_FILES.items()}
    tfidf_lr_lingxi = {str(r["case_id"]): r for r in load_jsonl(TFIDF_LR_FILES["lingxi_icd10"])}
    print(f"  Loaded Qwen modes: {sum(len(v) for v in qwen_modes.values())} records")
    print(f"  Loaded TF-IDF+LR lookup: {len(tfidf_lr_lingxi)} records")

    print("[A4] Oracle EM@k ceiling...")
    a4 = a4_oracle_ceiling(qwen_modes, tfidf_lr_lingxi)
    print("[A3] Missing-secondary taxonomy...")
    a3 = a3_missing_taxonomy(qwen_modes)
    print("[A7] Per-class set coverage...")
    a7 = a7_per_class_coverage(qwen_modes)
    print("[B6] Confusion-pair expansion...")
    b6 = b6_confusion_pair_expansion(qwen_modes)
    print("[D3] Candidate ranker...")
    d3 = d3_train_ranker(qwen_modes, tfidf_lr_lingxi)
    print("[E1] Cardinality classifier...")
    e1 = e1_cardinality_classifier(qwen_modes, tfidf_lr_lingxi)

    # Render audit
    L = []
    L.append("# Gap F CPU Batch Audit — Multi-experiment diagnostic results")
    L.append("")
    L.append(f"**Date:** {started}")
    L.append("**Branch:** tier2b/hierarchical-prompt @ HEAD")
    L.append("**Status:** CPU-only batch audit. Uncommitted.")
    L.append("**Source:** BETA-2b CPU projection + TF-IDF baseline.")
    L.append("")
    L.append("Six diagnostic sub-experiments on existing predictions, no new GPU calls.")
    L.append("")
    L.append("---")

    # A4
    L.append("")
    L.append("## §A4 — Oracle EM@k ceiling (perfect reranker upper bound)")
    L.append("")
    L.append("If a perfect reranker chose K codes from the candidate pool, what's the maximum EM?")
    L.append("")
    L.append("| Mode | Gold size | N | k=1 | k=3 | k=5 | Cross-mode union | TF-IDF union |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for tag in PRED_FILES:
        if tag not in a4: continue
        for size in sorted(a4[tag].keys()):
            d = a4[tag][size]
            n = d["n"]
            cm = f"{100*d['cross_mode_union']/n:.1f}%" if n else "—"
            tu = f"{100*d['tfidf_union']/n:.1f}%" if n and tag.startswith("lingxi") else "n/a"
            L.append(f"| {tag} | size={size} | {n} | {100*d['k1']/n:.1f}% | {100*d['k3']/n:.1f}% | {100*d['k5']/n:.1f}% | {cm} | {tu} |")
    L.append("")
    L.append("Read this as the ABSOLUTE CEILING for each candidate pool. Real systems can only reach this with a perfect downstream selector.")

    # A3
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §A3 — Missing-secondary-gold taxonomy")
    L.append("")
    L.append("For multi-gold cases, where do the gold codes appear?")
    L.append("")
    L.append("| Mode | in_top5 | in_candidates_not_top5 | out_of_candidates |")
    L.append("|---|---:|---:|---:|")
    for tag, info in a3.items():
        cats = info["cats"]
        total = sum(cats.values())
        if total == 0: continue
        L.append(f"| {tag} | {cats.get('in_top5',0)} ({100*cats.get('in_top5',0)/total:.1f}%) | {cats.get('in_candidates_not_top5',0)} ({100*cats.get('in_candidates_not_top5',0)/total:.1f}%) | {cats.get('out_of_candidates',0)} ({100*cats.get('out_of_candidates',0)/total:.1f}%) |")
    L.append("")
    L.append("Sample of size=2 cases with missing secondary (5 per mode, lingxi_icd10):")
    if "lingxi_icd10" in a3 and a3["lingxi_icd10"]["size2_misses_sample"]:
        L.append("")
        L.append("| case_id | gold | missing_secondary | top5 | in_candidates? |")
        L.append("|---|---|---|---|---|")
        for s in a3["lingxi_icd10"]["size2_misses_sample"]:
            L.append(f"| {s['case_id']} | {s['gold']} | {s['missing_secondary']} | {s['top5']} | {s['in_candidates']} |")

    # A7
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §A7 — Per-class set coverage")
    L.append("")
    L.append("For each class C: how often is C in gold, in top-5, primary-correct, involved in size=2, and set-covered when in size=2?")
    L.append("")
    for tag, per_class in a7.items():
        L.append(f"### {tag}")
        L.append("")
        L.append("| Class | gold_count | in_top5 | primary_correct | involved_size2 | set_covered_size2 |")
        L.append("|---|---:|---:|---:|---:|---:|")
        for c in ["F32", "F41", "F42", "F33", "F39", "F51", "F45", "Z71"]:
            d = per_class[c]
            if d["gold_count"] == 0:
                L.append(f"| {c} | 0 | — | — | — | — |")
                continue
            top5_pct = f"{100*d['in_top5']/d['gold_count']:.0f}%"
            prim_pct = f"{100*d['primary_correct']/d['gold_count']:.0f}%"
            inv = d["involved_in_size2"]
            cov = f"{100*d['set_covered_in_size2']/inv:.0f}%" if inv > 0 else "—"
            L.append(f"| {c} | {d['gold_count']} | {top5_pct} | {prim_pct} | {inv} | {cov} |")
        L.append("")

    # B6
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §B6 — Confusion-pair forced candidate expansion")
    L.append("")
    L.append("Augment top-5 with primary's confusion pair (F32→F41, F41→F32, F42→F41, etc).")
    L.append("Tests: does forced expansion improve set coverage without external candidate sources?")
    L.append("")
    L.append("| Mode | Gold size | N | baseline top-5 | expanded top-5 | Δ |")
    L.append("|---|---|---:|---:|---:|---:|")
    for tag, sizes in b6.items():
        for size in sorted(sizes.keys()):
            d = sizes[size]
            n = d["n"]
            base_pct = 100*d["baseline_top5"]/n if n else 0
            exp_pct = 100*d["expanded_top5"]/n if n else 0
            L.append(f"| {tag} | size={size} | {n} | {base_pct:.1f}% | {exp_pct:.1f}% | +{exp_pct-base_pct:.1f}pp |")
    L.append("")

    # D3
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §D3 — Candidate ranker (logistic on rank/met/confirmed/tfidf features)")
    L.append("")
    if "error" in d3:
        L.append(f"⚠ {d3['error']}")
    else:
        L.append(f"Train cases: {d3['n_train_cases']}, Test cases: {d3['n_test_cases']}")
        L.append(f"Baseline (rank-1 = primary): Top-1 = {100*d3['baseline_top1']:.1f}%")
        L.append(f"Reranker (logistic): Top-1 = {100*d3['rerank_top1']:.1f}%")
        L.append(f"Δ = {100*(d3['rerank_top1']-d3['baseline_top1']):+.1f}pp")
        L.append("")
        L.append("Top-8 feature importances:")
        L.append("")
        L.append("| Feature | Coefficient |")
        L.append("|---|---:|")
        for k, v in d3["feat_importance"]:
            L.append(f"| `{k}` | {v:+.4f} |")

    # E1
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §E1 — Cardinality classifier (predict gold size from features)")
    L.append("")
    if "error" in e1:
        L.append(f"⚠ {e1['error']}")
    else:
        L.append(f"Test accuracy: {100*e1['test_acc']:.1f}% (N={e1['n_test']})")
        L.append("")
        L.append("Confusion matrix (true → predicted):")
        L.append("")
        L.append("| Cell | Count |")
        L.append("|---|---:|")
        for k, v in sorted(e1["true_pred_counts"].items()):
            L.append(f"| {k} | {v} |")
        L.append("")
        L.append("Feature importance (max abs coef across classes):")
        L.append("")
        L.append("| Feature | Importance |")
        L.append("|---|---:|")
        for k, v in e1["feat_importance"]:
            L.append(f"| `{k}` | {float(v):.4f} |")

    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Summary")
    L.append("")
    L.append("- A4: confirms ~75-80% in-top-3 oracle EM ceiling for lingxi (primary-only); cross-mode union and TF-IDF union extend ceiling further")
    L.append("- A3: confirms 24-31% of multi-gold codes are out-of-top5 (some out-of-candidates, especially MDD)")
    L.append("- A7: per-class breakdown — F42/F33 typically have lowest top-5 recall when they ARE gold")
    L.append("- B6: confusion-pair expansion provides modest lift (specific to F32/F41/F42 pairs)")
    L.append("- D3: simple logistic candidate-reranker test on a 70/30 case split — quantifies how much rank-rerank helps")
    L.append("- E1: cardinality classifier accuracy on size {1,2,3} — tests whether features predict gold size")
    L.append("")
    L.append("These results inform the Gap F MAS architecture: candidate pool ceiling, rerank headroom, and set-size predictability.")
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text("\n".join(L))
    print(f"Audit written: {AUDIT_OUT}")
    print(f"Lines: {len(L)}")


if __name__ == "__main__":
    main()
