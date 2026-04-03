"""Hybrid DtV evaluation: primary for classification, diagnostician ranking for top-3."""
import json
import sys
sys.path.insert(0, "/home/user/YuNing/CultureDx/src")

from culturedx.eval.lingxidiag_paper import (
    PAPER_12_CLASSES, PAPER_2_CLASSES, PAPER_4_CLASSES,
    classify_2class_from_raw, classify_2class_prediction, classify_4class_from_raw,
    compute_singlelabel_metrics, gold_to_parent_list,
    pred_to_parent_list, to_paper_parent,
)
from sklearn.metrics import f1_score
from sklearn.preprocessing import MultiLabelBinarizer
import numpy as np


def load_results(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def compute_dtv_table4(cases):
    """Table 4 with hybrid: primary for classification, diagnostician ranking for top-3."""
    gold_12, pred_12_primary, pred_12_ranked = [], [], []
    gold_2, pred_2 = [], []
    gold_4, pred_4 = [], []

    for case in cases:
        raw_code = str(case.get("DiagnosisCode", "") or "")
        gold_parents = gold_to_parent_list(raw_code)

        # Primary prediction (the actual DtV decision)
        primary = case.get("primary_diagnosis", "")
        comorbid = case.get("comorbid_diagnoses", [])
        pred_primary = pred_to_parent_list([primary] + comorbid)

        # Full diagnostician ranking (for top-3)
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

        gold_12.append(gold_parents)
        pred_12_primary.append(pred_primary)
        pred_12_ranked.append(pred_ranked)

        # 4-class
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

        # 2-class
        gold_2_label = classify_2class_from_raw(raw_code)
        if gold_2_label is not None:
            pred_2_label = classify_2class_prediction(pred_p)
            gold_2.append(gold_2_label)
            pred_2.append(pred_2_label)

    # 2-class, 4-class metrics (standard, from primary)
    m2 = compute_singlelabel_metrics(gold_2, pred_2, PAPER_2_CLASSES) if gold_2 else {}
    m4 = compute_singlelabel_metrics(gold_4, pred_4, PAPER_4_CLASSES)

    # 12-class: exact match and F1 from primary, Top-1/Top-3 from ranking
    n = len(gold_12)
    mlb = MultiLabelBinarizer(classes=PAPER_12_CLASSES)
    y_true_bin = mlb.fit_transform(gold_12)
    y_pred_primary_bin = mlb.transform(pred_12_primary)

    exact_match = sum(1 for g, p in zip(gold_12, pred_12_primary) if set(g) == set(p)) / n
    # Top-1 from primary
    top1 = sum(1 for g, p in zip(gold_12, pred_12_primary) if p and p[0] in set(g)) / n
    # Top-3 from diagnostician ranking
    top3 = sum(1 for g, p in zip(gold_12, pred_12_ranked) if set(p[:3]) & set(g)) / n

    m12_f1m = float(f1_score(y_true_bin, y_pred_primary_bin, average="macro", zero_division=0))
    m12_f1w = float(f1_score(y_true_bin, y_pred_primary_bin, average="weighted", zero_division=0))

    table4 = {
        "2class_Acc": m2.get("accuracy"),
        "2class_F1_macro": m2.get("macro_f1"),
        "2class_F1_weighted": m2.get("weighted_f1"),
        "4class_Acc": m4.get("accuracy"),
        "4class_F1_macro": m4.get("macro_f1"),
        "4class_F1_weighted": m4.get("weighted_f1"),
        "12class_Acc": float(exact_match),
        "12class_Top1": float(top1),
        "12class_Top3": float(top3),
        "12class_F1_macro": m12_f1m,
        "12class_F1_weighted": m12_f1w,
        "2class_n": m2.get("n", 0),
        "4class_n": m4.get("n", 0),
        "12class_n": n,
    }
    vals = [float(v) for k, v in table4.items() if not k.endswith("_n") and v is not None]
    table4["Overall"] = float(np.mean(vals)) if vals else None
    return table4


def print_row(label, m, indent="  "):
    def fmt(v):
        return f"{v:.3f}" if v is not None else "N/A"
    print(f"\n{indent}{label}")
    print(f"{indent}  2c: Acc={fmt(m.get('2class_Acc'))} F1m={fmt(m.get('2class_F1_macro'))} F1w={fmt(m.get('2class_F1_weighted'))} (n={m.get('2class_n', 0)})")
    print(f"{indent}  4c: Acc={fmt(m.get('4class_Acc'))} F1m={fmt(m.get('4class_F1_macro'))} F1w={fmt(m.get('4class_F1_weighted'))} (n={m.get('4class_n', 0)})")
    print(f"{indent} 12c: Acc={fmt(m.get('12class_Acc'))} Top1={fmt(m.get('12class_Top1'))} Top3={fmt(m.get('12class_Top3'))} F1m={fmt(m.get('12class_F1_macro'))} F1w={fmt(m.get('12class_F1_weighted'))} (n={m.get('12class_n', 0)})")
    print(f"{indent}  Overall={fmt(m.get('Overall'))}")


if __name__ == "__main__":
    dtv = load_results("/home/user/YuNing/CultureDx/outputs/eval/hied_dtv_validation/results_lingxidiag.jsonl")
    print(f"DtV results: {len(dtv)} cases")
    m = compute_dtv_table4(dtv)
    print_row("HiED-DtV (hybrid: primary for class, ranking for top-3)", m)

    # Baselines
    from culturedx.eval.lingxidiag_paper import compute_table4_metrics, pred_to_parent_list
    def get_pred(case):
        p = case.get("primary_diagnosis", "")
        c = case.get("comorbid_diagnoses", [])
        return pred_to_parent_list([p] + c)

    for label, path in [
        ("HiED-orig", "/home/user/YuNing/CultureDx/outputs/eval/calibrator_validation/results_lingxidiag.jsonl"),
        ("Single-baseline", "/home/user/YuNing/CultureDx/outputs/eval/rescore_gate_only_20260402_223720/single-baseline/results_lingxidiag.jsonl"),
    ]:
        try:
            cases = load_results(path)
            bm = compute_table4_metrics(cases, get_pred)
            print_row(f"{label} (n={len(cases)})", bm)
        except FileNotFoundError:
            print(f"\n  {label}: not found")

    # Extra stats
    veto = sum(1 for c in dtv if c.get("decision_trace", {}).get("veto_applied"))
    print(f"\n  Veto rate: {veto}/{len(dtv)} ({veto/max(len(dtv),1):.1%})")
