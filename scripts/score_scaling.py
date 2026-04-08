"""Score all model scaling experiments with Table 4 + per-class recall."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.lingxidiag_paper import (
    PAPER_12_CLASSES, PAPER_2_CLASSES, PAPER_4_CLASSES,
    classify_2class_from_raw, classify_2class_prediction, classify_4class_from_raw,
    compute_singlelabel_metrics, gold_to_parent_list,
    pred_to_parent_list, to_paper_parent,
)
from sklearn.metrics import f1_score
from sklearn.preprocessing import MultiLabelBinarizer
import numpy as np


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def compute_table4(cases, mode="dtv"):
    gold_12, pred_12, pred_12_ranked = [], [], []
    gold_2, pred_2 = [], []
    gold_4, pred_4 = [], []

    for case in cases:
        raw_code = str(case.get("DiagnosisCode", "") or case.get("gold_code", "") or "")
        gold_parents = gold_to_parent_list(raw_code)

        if mode == "dtv":
            primary = case.get("primary_diagnosis", "")
            comorbid = case.get("comorbid_diagnoses", [])
            pred_primary = pred_to_parent_list([primary] + comorbid)
            trace = case.get("decision_trace", {})
            ranked = trace.get("diagnostician_ranked", [])
            if ranked:
                parents_ranked = []
                seen = set()
                for code in ranked:
                    p = to_paper_parent(code)
                    if p not in seen:
                        seen.add(p)
                        parents_ranked.append(p)
                pred_ranked = parents_ranked or pred_primary
            else:
                pred_ranked = pred_primary
        else:
            pred_raw = str(case.get("primary_diagnosis", "") or case.get("prediction", "") or "")
            pred_primary = pred_to_parent_list([pred_raw]) if pred_raw else []
            pred_ranked = pred_primary

        gold_12.append(gold_parents)
        pred_12.append(pred_primary)
        pred_12_ranked.append(pred_ranked)

        gold_4_label = classify_4class_from_raw(raw_code)
        pred_p = pred_primary[0] if pred_primary else "Others"
        pred_ps = set(pred_primary)
        if "F32" in pred_ps and "F41" in pred_ps:
            pred_4_label = "Mixed"
        elif pred_p == "F32":
            pred_4_label = "Depression"
        elif pred_p == "F41":
            pred_4_label = "Anxiety"
        else:
            pred_4_label = "Others"
        gold_4.append(gold_4_label)
        pred_4.append(pred_4_label)

        gold_2_label = classify_2class_from_raw(raw_code)
        if gold_2_label is not None:
            pred_2_label = classify_2class_prediction(pred_p)
            gold_2.append(gold_2_label)
            pred_2.append(pred_2_label)

    m2 = compute_singlelabel_metrics(gold_2, pred_2, PAPER_2_CLASSES) if gold_2 else {}
    m4 = compute_singlelabel_metrics(gold_4, pred_4, PAPER_4_CLASSES)

    n = len(gold_12)
    mlb = MultiLabelBinarizer(classes=PAPER_12_CLASSES)
    y_true_bin = mlb.fit_transform(gold_12)
    y_pred_bin = mlb.transform(pred_12)

    exact_match = sum(1 for g, p in zip(gold_12, pred_12) if set(g) == set(p)) / n
    top1 = sum(1 for g, p in zip(gold_12, pred_12) if p and p[0] in set(g)) / n
    top3 = sum(1 for g, p in zip(gold_12, pred_12_ranked) if set(p[:3]) & set(g)) / n

    m12_f1m = float(f1_score(y_true_bin, y_pred_bin, average="macro", zero_division=0))
    m12_f1w = float(f1_score(y_true_bin, y_pred_bin, average="weighted", zero_division=0))

    table4 = {
        "2class_Acc": m2.get("accuracy"), "2class_F1_macro": m2.get("macro_f1"),
        "2class_F1_weighted": m2.get("weighted_f1"),
        "4class_Acc": m4.get("accuracy"), "4class_F1_macro": m4.get("macro_f1"),
        "4class_F1_weighted": m4.get("weighted_f1"),
        "12class_Acc": float(exact_match), "12class_Top1": float(top1),
        "12class_Top3": float(top3), "12class_F1_macro": m12_f1m,
        "12class_F1_weighted": m12_f1w,
        "2class_n": m2.get("n", 0), "4class_n": m4.get("n", 0), "12class_n": n,
    }
    vals = [float(v) for k, v in table4.items() if not k.endswith("_n") and v is not None]
    table4["Overall"] = float(np.mean(vals)) if vals else None
    return table4


def per_class_recall(cases, mode="dtv"):
    tp = Counter()
    fn = Counter()

    for case in cases:
        raw_code = str(case.get("DiagnosisCode", "") or case.get("gold_code", "") or "")
        gold_parents = set(gold_to_parent_list(raw_code))

        if mode == "dtv":
            primary = case.get("primary_diagnosis", "")
            comorbid = case.get("comorbid_diagnoses", [])
            pred_parents = set(pred_to_parent_list([primary] + comorbid))
        else:
            pred_raw = str(case.get("primary_diagnosis", "") or case.get("prediction", "") or "")
            pred_parents = set(pred_to_parent_list([pred_raw])) if pred_raw else set()

        for cls in gold_parents:
            if cls in pred_parents:
                tp[cls] += 1
            else:
                fn[cls] += 1

    results = {}
    for cls in PAPER_12_CLASSES:
        total = tp[cls] + fn[cls]
        results[cls] = {"recall": tp[cls] / total if total > 0 else 0.0, "n": total}
    return results


def print_table4(label, m, indent="  "):
    def fmt(v):
        return f"{v:.3f}" if v is not None else "N/A"
    print(f"\n{indent}{label}")
    print(f"{indent}  2c: Acc={fmt(m.get('2class_Acc'))} F1m={fmt(m.get('2class_F1_macro'))} F1w={fmt(m.get('2class_F1_weighted'))} (n={m.get('2class_n', 0)})")
    print(f"{indent}  4c: Acc={fmt(m.get('4class_Acc'))} F1m={fmt(m.get('4class_F1_macro'))} F1w={fmt(m.get('4class_F1_weighted'))} (n={m.get('4class_n', 0)})")
    print(f"{indent} 12c: Acc={fmt(m.get('12class_Acc'))} Top1={fmt(m.get('12class_Top1'))} Top3={fmt(m.get('12class_Top3'))} F1m={fmt(m.get('12class_F1_macro'))} F1w={fmt(m.get('12class_F1_weighted'))} (n={m.get('12class_n', 0)})")
    print(f"{indent}  Overall={fmt(m.get('Overall'))}")


def print_per_class(recall_data, indent="  "):
    dominant = ["F32", "F41"]
    rare = ["F39", "F51", "F98", "Z71"]
    rest = [c for c in PAPER_12_CLASSES if c not in dominant + rare]
    order = dominant + rest + rare

    print(f"{indent}Per-class recall:")
    for cls in order:
        d = recall_data.get(cls, {"recall": 0.0, "n": 0})
        marker = " <- rare" if cls in rare else (" <- dominant" if cls in dominant else "")
        print(f"{indent}  {cls}: {d['recall']:.3f}  (n={d['n']}){marker}")


EVAL_DIR = Path("/home/user/YuNing/CultureDx/outputs/eval")

EXPERIMENTS = [
    ("Qwen3-8B Single", EVAL_DIR / "qwen3_8b_single/results_lingxidiag.jsonl", "single"),
    ("Qwen3-8B DtV", EVAL_DIR / "qwen3_8b_dtv/results_lingxidiag.jsonl", "dtv"),
    ("Qwen3-14B Single", EVAL_DIR / "qwen3_14b_single/results_lingxidiag.jsonl", "single"),
    ("Qwen3-14B DtV", EVAL_DIR / "qwen3_14b_dtv/results_lingxidiag.jsonl", "dtv"),
    ("Qwen3-30B-A3B Single", EVAL_DIR / "qwen3_30b_a3b_single/results_lingxidiag.jsonl", "single"),
    ("Qwen3-30B-A3B DtV", EVAL_DIR / "qwen3_30b_a3b_dtv/results_lingxidiag.jsonl", "dtv"),
    ("Qwen3-32B Single", EVAL_DIR / "qwen3_32b_single/results_lingxidiag.jsonl", "single"),
    ("Qwen3-32B DtV", EVAL_DIR / "qwen3_32b_dtv_top3/results_lingxidiag.jsonl", "dtv"),
]

if __name__ == "__main__":
    print("=" * 70)
    print("Model Scaling Results - Table 4 + Per-Class Recall")
    print("=" * 70)

    results = {}
    for label, path, mode in EXPERIMENTS:
        if path.exists():
            cases = load_jsonl(path)
            m = compute_table4(cases, mode=mode)
            print_table4(f"{label} ({mode}, n={len(cases)})", m)
            recall = per_class_recall(cases, mode=mode)
            print_per_class(recall)
            results[label] = m
        else:
            print(f"\n  {label}: NOT FOUND")

    # Summary table
    print("\n" + "=" * 70)
    print("Summary Table")
    print("=" * 70)
    models = ["Qwen3-8B", "Qwen3-14B", "Qwen3-30B-A3B", "Qwen3-32B"]
    fmt_v = lambda v: f"{v:.3f}" if v is not None else "  ???"
    header = f"{'Backbone':<20} {'Single':>8} {'DtV':>8} {'Delta':>8} {'12c F1m':>8}"
    print(header)
    print("-" * len(header))
    for model in models:
        s = results.get(f"{model} Single", {})
        d = results.get(f"{model} DtV", {})
        so = s.get("Overall")
        do_ = d.get("Overall")
        delta = do_ - so if so is not None and do_ is not None else None
        f1m = d.get("12class_F1_macro")
        print(f"{model:<20} {fmt_v(so):>8} {fmt_v(do_):>8} {(f'+{delta:.3f}' if delta is not None else '  ???'):>8} {fmt_v(f1m):>8}")
