"""
Comprehensive analysis of MDD-5k N=200 experiment results.
Covers: confusion matrices, per-class metrics, McNemar's tests,
bootstrap CIs, error analysis, abstention analysis, confidence
calibration, and cross-mode agreement analysis.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import chi2

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
ROOT = Path("/home/user/YuNing/CultureDx")
SWEEP3 = ROOT / "outputs/sweeps/n200_3mode_20260320_131920"
SWEEP_NODIFF = ROOT / "outputs/sweeps/n200_nodiff_ablation_20260320_163137"

PRED_PATHS = {
    "hied":      SWEEP3 / "hied_no_evidence/predictions.json",
    "single":    SWEEP3 / "single_no_evidence/predictions.json",
    "psycot":    SWEEP3 / "psycot_no_evidence/predictions.json",
    "v8_nodiff": SWEEP_NODIFF / "hied_no_evidence/predictions.json",
}
CASE_LIST = SWEEP3 / "case_list.json"

# ICD-10 chapter-F disorder labels we care about (all that appear in gold)
DISORDER_LABELS = [
    "F20", "F22", "F23", "F28", "F30", "F31", "F32", "F33",
    "F34", "F39", "F41", "F42", "F43", "F45", "F48", "F50",
    "F51", "F64", "F90", "F93", "F98", "G47",
]

DISORDER_NAMES = {
    "F20": "Schizophrenia",
    "F22": "Persistent Delusional",
    "F23": "Acute Psychosis",
    "F28": "Other Nonorganic Psychosis",
    "F30": "Mania",
    "F31": "Bipolar",
    "F32": "Depressive Episode",
    "F33": "Recurrent Depression",
    "F34": "Persistent Mood",
    "F39": "Unspecified Mood",
    "F41": "Anxiety",
    "F42": "OCD",
    "F43": "Stress Reaction",
    "F45": "Somatoform",
    "F48": "Other Neurotic",
    "F50": "Eating Disorder",
    "F51": "Non-organic Sleep",
    "F64": "Gender Identity",
    "F90": "ADHD",
    "F93": "Childhood Emotional",
    "F98": "Other Child/Adolescent",
    "G47": "Sleep Disorder (G47)",
}

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def parent_code(code: str) -> str:
    """Strip sub-specifier: 'F32.1' -> 'F32', 'F32' -> 'F32'."""
    return code.split(".")[0] if code else code


def is_correct(predicted: str | None, gold_labels: list[str]) -> bool:
    """
    True if predicted matches any gold label via exact or parent-code match.
    'F32.1' matches 'F32' (predicted is more specific than gold).
    'F32' matches 'F32.1' (gold is more specific than predicted).
    Also handles exact sub-code match: 'F32.1' matches 'F32.1'.
    """
    if predicted is None:
        return False
    pred_parent = parent_code(predicted)
    for g in gold_labels:
        g_parent = parent_code(g)
        if pred_parent == g_parent:
            return True
        if predicted == g:
            return True
        # predicted is F32.1, gold is F32 → pred_parent F32 == g F32 ✓ (handled above)
        # predicted is F32, gold is F32.1 → pred_parent F32 == g_parent F32 ✓ (handled above)
    return False


def get_gold_primary(gold_labels: list[str]) -> str:
    """Use first gold label as primary for per-class analysis."""
    return parent_code(gold_labels[0]) if gold_labels else "UNK"


def normalize_predicted(predicted: str | None) -> str | None:
    """Normalize to parent code for confusion matrix (strip sub-specifiers)."""
    return parent_code(predicted) if predicted else None


# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────

def load_all_data():
    case_list_raw = load_json(CASE_LIST)
    gold_map = {c["case_id"]: c["diagnoses"] for c in case_list_raw["cases"]}
    case_order = [c["case_id"] for c in case_list_raw["cases"]]

    modes = {}
    for name, path in PRED_PATHS.items():
        raw = load_json(path)
        by_id = {p["case_id"]: p for p in raw["predictions"]}
        modes[name] = by_id

    return gold_map, case_order, modes


# ─────────────────────────────────────────────────────────────────────────────
# Formatting utilities
# ─────────────────────────────────────────────────────────────────────────────

def hr(char="═", width=100):
    print(char * width)

def section(title: str):
    print()
    hr("═")
    print(f"  {title}")
    hr("═")

def subsection(title: str):
    print()
    hr("─", 80)
    print(f"  {title}")
    hr("─", 80)

def table_row(*cols, widths):
    parts = []
    for val, w in zip(cols, widths):
        s = str(val)
        parts.append(s.ljust(w) if w > 0 else s.rjust(-w))
    print("  " + "  ".join(parts))

def fmt(val, decimals=3):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "  N/A  "
    return f"{val:.{decimals}f}"

def pct(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "  N/A  "
    return f"{val*100:.1f}%"


# ─────────────────────────────────────────────────────────────────────────────
# Section 1: Overall accuracy
# ─────────────────────────────────────────────────────────────────────────────

def compute_accuracy(gold_map, case_order, mode_preds):
    results = {}
    for name, by_id in mode_preds.items():
        correct = 0
        total = 0
        for cid in case_order:
            gold = gold_map[cid]
            pred = by_id[cid].get("primary_diagnosis")
            total += 1
            if is_correct(pred, gold):
                correct += 1
        results[name] = (correct, total, correct / total)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Full confusion matrix
# ─────────────────────────────────────────────────────────────────────────────

def build_confusion_matrix(gold_map, case_order, by_id):
    """
    Rows = gold primary class, Cols = predicted class.
    Abstentions land in a special 'ABSTAIN' column.
    """
    all_gold = sorted({parent_code(g) for gold in gold_map.values() for g in gold})
    all_pred = sorted({parent_code(p["primary_diagnosis"])
                       for p in by_id.values()
                       if p.get("primary_diagnosis")})
    classes = sorted(set(all_gold) | set(all_pred))
    class_idx = {c: i for i, c in enumerate(classes)}

    cm = np.zeros((len(classes), len(classes) + 1), dtype=int)  # +1 for ABSTAIN
    abstain_col = len(classes)

    for cid in case_order:
        gold = gold_map[cid]
        gold_primary = parent_code(gold[0])
        pred = by_id[cid].get("primary_diagnosis")
        row = class_idx.get(gold_primary, -1)
        if row < 0:
            continue
        if pred is None:
            cm[row, abstain_col] += 1
        else:
            pred_parent = parent_code(pred)
            col = class_idx.get(pred_parent, -1)
            if col >= 0:
                cm[row, col] += 1
            else:
                cm[row, abstain_col] += 1

    return cm, classes


def print_confusion_matrix(cm, classes, mode_name):
    subsection(f"Confusion Matrix — {mode_name.upper()}")
    col_labels = classes + ["ABSTAIN"]
    col_w = 8
    label_w = 8
    # Header
    header = "Gold\\Pred".ljust(label_w) + "  " + "  ".join(
        c.ljust(col_w) for c in col_labels
    )
    print("  " + header)
    hr("·", 80)
    for i, gold_c in enumerate(classes):
        row = cm[i]
        if row.sum() == 0:
            continue
        cells = "  ".join(str(v).rjust(col_w) for v in row)
        print(f"  {gold_c.ljust(label_w)}  {cells}")


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Per-class precision, recall, F1
# ─────────────────────────────────────────────────────────────────────────────

def per_class_metrics(gold_map, case_order, by_id):
    """
    TP, FP, FN per gold class using parent-code matching.
    Abstentions count as FN for the gold class.
    """
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    support = defaultdict(int)

    for cid in case_order:
        gold = gold_map[cid]
        gold_primary = parent_code(gold[0])
        pred = by_id[cid].get("primary_diagnosis")
        pred_parent = normalize_predicted(pred)
        support[gold_primary] += 1

        if pred_parent is not None and pred_parent == gold_primary:
            tp[gold_primary] += 1
        elif pred_parent is not None:
            fp[pred_parent] += 1
            fn[gold_primary] += 1
        else:
            fn[gold_primary] += 1  # abstention

    metrics = {}
    for cls in sorted(set(support.keys()) | set(fp.keys())):
        t = tp[cls]
        p = t + fp[cls]
        r = t + fn[cls]
        prec = t / p if p > 0 else float("nan")
        rec = t / r if r > 0 else float("nan")
        f1 = (2 * prec * rec / (prec + rec)
               if not (np.isnan(prec) or np.isnan(rec) or (prec + rec) == 0)
               else float("nan"))
        metrics[cls] = {
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "support": support[cls],
            "tp": tp[cls],
            "fp": fp[cls],
            "fn": fn[cls],
        }
    return metrics


def macro_f1(metrics):
    f1s = [v["f1"] for v in metrics.values() if not np.isnan(v["f1"]) and v["support"] > 0]
    return float(np.mean(f1s)) if f1s else float("nan")


def print_per_class_metrics(metrics, mode_name):
    subsection(f"Per-Class Precision / Recall / F1 — {mode_name.upper()}")
    w = [8, 22, 8, 8, 8, 8, 8, 8]
    header = ["Class", "Name", "Prec", "Rec", "F1", "Supp", "TP", "FP/FN"]
    table_row(*header, widths=w)
    hr("·", 90)
    for cls, m in sorted(metrics.items()):
        if m["support"] == 0 and m["fp"] == 0:
            continue
        name = DISORDER_NAMES.get(cls, cls)[:20]
        table_row(
            cls, name,
            fmt(m["precision"]), fmt(m["recall"]), fmt(m["f1"]),
            m["support"], m["tp"], f"{m['fp']}/{m['fn']}",
            widths=w
        )
    mf1 = macro_f1(metrics)
    hr("·", 90)
    table_row("MACRO", "", "", "", fmt(mf1), "", "", "", widths=w)


# ─────────────────────────────────────────────────────────────────────────────
# Section 4: McNemar's test
# ─────────────────────────────────────────────────────────────────────────────

def mcnemar_test(correct_a, correct_b):
    """
    Exact McNemar's test (mid-p corrected).
    b = correct in A but wrong in B
    c = wrong in A but correct in B
    Returns: statistic, p_value
    """
    n = len(correct_a)
    b = sum(a and not b_ for a, b_ in zip(correct_a, correct_b))
    c = sum(not a and b_ for a, b_ in zip(correct_a, correct_b))
    discordant = b + c
    if discordant == 0:
        return 0.0, 1.0, b, c
    # Mid-p exact McNemar
    from scipy.stats import binom
    p_exact = 2 * binom.cdf(min(b, c), discordant, 0.5)
    # Chi-sq with continuity correction
    chi2_stat = (abs(b - c) - 1) ** 2 / (b + c) if (b + c) > 0 else 0
    from scipy.stats import chi2 as chi2_dist
    p_chi2 = chi2_dist.sf(chi2_stat, df=1)
    return chi2_stat, p_chi2, b, c


def print_mcnemar(gold_map, case_order, mode_preds):
    section("4. McNemar's Tests (Pairwise Mode Comparison)")
    pairs = [
        ("hied", "single"),
        ("hied", "psycot"),
        ("hied", "v8_nodiff"),
        ("single", "psycot"),
    ]
    correct_cache = {}
    for name, by_id in mode_preds.items():
        correct_cache[name] = [
            is_correct(by_id[cid].get("primary_diagnosis"), gold_map[cid])
            for cid in case_order
        ]

    w = [14, 14, 8, 8, 12, 12, 10]
    table_row("Mode A", "Mode B", "Acc_A", "Acc_B",
              "Chi2", "p-value", "b / c", widths=w)
    hr("·", 90)
    for a, b in pairs:
        if a not in correct_cache or b not in correct_cache:
            continue
        ca = correct_cache[a]
        cb = correct_cache[b]
        acc_a = sum(ca) / len(ca)
        acc_b = sum(cb) / len(cb)
        chi2_stat, p_val, b_cnt, c_cnt = mcnemar_test(ca, cb)
        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
        table_row(
            a, b,
            pct(acc_a), pct(acc_b),
            f"{chi2_stat:.3f}", f"{p_val:.4f} {sig}",
            f"{b_cnt}/{c_cnt}",
            widths=w
        )
    print()
    print("  b = A correct, B wrong; c = A wrong, B correct")
    print("  *** p<0.001  ** p<0.01  * p<0.05  ns not significant")


# ─────────────────────────────────────────────────────────────────────────────
# Section 5: Bootstrap 95% CIs
# ─────────────────────────────────────────────────────────────────────────────

def bootstrap_ci(values: np.ndarray, metric_fn, B=10000, seed=42, alpha=0.05):
    rng = np.random.default_rng(seed)
    n = len(values)
    stats = []
    for _ in range(B):
        idx = rng.integers(0, n, size=n)
        stats.append(metric_fn(values[idx]))
    lower = float(np.percentile(stats, 100 * alpha / 2))
    upper = float(np.percentile(stats, 100 * (1 - alpha / 2)))
    point = metric_fn(values)
    return point, lower, upper


def bootstrap_accuracy(gold_map, case_order, by_id, B=10000, seed=42):
    """Bootstrap accuracy CI."""
    correct = np.array([
        1 if is_correct(by_id[cid].get("primary_diagnosis"), gold_map[cid]) else 0
        for cid in case_order
    ])
    return bootstrap_ci(correct, np.mean, B=B, seed=seed)


def bootstrap_macro_f1(gold_map, case_order, by_id, B=10000, seed=42):
    """Bootstrap macro-F1 CI using case-level resampling."""
    pairs = []
    for cid in case_order:
        gold_primary = parent_code(gold_map[cid][0])
        pred = normalize_predicted(by_id[cid].get("primary_diagnosis"))
        pairs.append((gold_primary, pred))
    pairs_arr = np.array(pairs, dtype=object)

    def _macro_f1(sample):
        tp = defaultdict(int)
        fp = defaultdict(int)
        fn = defaultdict(int)
        for gold, pred in sample:
            if pred is not None and pred == gold:
                tp[gold] += 1
            elif pred is not None:
                fp[pred] += 1
                fn[gold] += 1
            else:
                fn[gold] += 1
        f1s = []
        for cls in set(gold for gold, _ in sample):
            t = tp[cls]
            p_cnt = t + fp[cls]
            r_cnt = t + fn[cls]
            prec = t / p_cnt if p_cnt > 0 else 0.0
            rec = t / r_cnt if r_cnt > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            f1s.append(f1)
        return float(np.mean(f1s)) if f1s else 0.0

    rng = np.random.default_rng(seed)
    n = len(pairs_arr)
    boot_f1s = []
    for _ in range(B):
        idx = rng.integers(0, n, size=n)
        boot_f1s.append(_macro_f1(pairs_arr[idx]))
    point = _macro_f1(pairs_arr)
    lower = float(np.percentile(boot_f1s, 2.5))
    upper = float(np.percentile(boot_f1s, 97.5))
    return point, lower, upper


def print_bootstrap(gold_map, case_order, mode_preds):
    section("5. Bootstrap 95% CIs for Accuracy and Macro F1 (B=10,000, seed=42)")
    w = [14, 16, 16]
    table_row("Mode", "Accuracy 95% CI", "Macro-F1 95% CI", widths=w)
    hr("·", 60)
    for name, by_id in mode_preds.items():
        acc, acc_lo, acc_hi = bootstrap_accuracy(gold_map, case_order, by_id)
        mf1, mf1_lo, mf1_hi = bootstrap_macro_f1(gold_map, case_order, by_id)
        acc_str = f"{acc:.3f} [{acc_lo:.3f}, {acc_hi:.3f}]"
        mf1_str = f"{mf1:.3f} [{mf1_lo:.3f}, {mf1_hi:.3f}]"
        table_row(name, acc_str, mf1_str, widths=w)


# ─────────────────────────────────────────────────────────────────────────────
# Section 6: Error analysis
# ─────────────────────────────────────────────────────────────────────────────

def print_error_analysis(gold_map, case_order, mode_preds):
    section("6. Error Analysis: All-Wrong vs. At-Least-One-Right Cases")
    mode_names = list(mode_preds.keys())

    correct_by_mode = {}
    for name, by_id in mode_preds.items():
        correct_by_mode[name] = {
            cid: is_correct(by_id[cid].get("primary_diagnosis"), gold_map[cid])
            for cid in case_order
        }

    all_wrong_cases = []
    at_least_one_right_cases = []
    for cid in case_order:
        if all(not correct_by_mode[m][cid] for m in mode_names):
            all_wrong_cases.append(cid)
        elif any(correct_by_mode[m][cid] for m in mode_names):
            at_least_one_right_cases.append(cid)

    print(f"\n  Total cases: {len(case_order)}")
    print(f"  All modes wrong:          {len(all_wrong_cases):4d} ({len(all_wrong_cases)/len(case_order)*100:.1f}%)")
    print(f"  At least one mode right:  {len(at_least_one_right_cases):4d} ({len(at_least_one_right_cases)/len(case_order)*100:.1f}%)")

    # Gold class distribution for all-wrong cases
    if all_wrong_cases:
        subsection("Gold Label Distribution — All-Modes-Wrong Cases")
        gold_dist = Counter(parent_code(gold_map[cid][0]) for cid in all_wrong_cases)
        print(f"  {'Class':<8} {'Count':>6}  {'Name'}")
        hr("·", 50)
        for cls, cnt in gold_dist.most_common():
            print(f"  {cls:<8} {cnt:>6}  {DISORDER_NAMES.get(cls, cls)}")

        # What do modes predict for all-wrong cases?
        subsection("Predicted Labels for All-Modes-Wrong Cases")
        for name, by_id in mode_preds.items():
            preds = Counter(
                normalize_predicted(by_id[cid].get("primary_diagnosis"))
                for cid in all_wrong_cases
            )
            print(f"\n  {name}: {dict(preds.most_common(8))}")
            gold_for_wrong = [parent_code(gold_map[cid][0]) for cid in all_wrong_cases]
            pred_for_wrong = [normalize_predicted(by_id[cid].get("primary_diagnosis")) for cid in all_wrong_cases]
            confusion_pairs = Counter(zip(gold_for_wrong, pred_for_wrong))
            print(f"  Top confusion pairs (gold→pred): {dict(confusion_pairs.most_common(5))}")

    # Cases where only one mode is right
    subsection("Which Mode Is Right (for cases where exactly one mode is correct)")
    for name in mode_names:
        only_this = sum(
            1 for cid in case_order
            if correct_by_mode[name][cid]
            and all(not correct_by_mode[m][cid] for m in mode_names if m != name)
        )
        print(f"  Only {name:12s} correct: {only_this}")


# ─────────────────────────────────────────────────────────────────────────────
# Section 7: Abstention analysis
# ─────────────────────────────────────────────────────────────────────────────

def print_abstention_analysis(gold_map, case_order, mode_preds):
    section("7. Abstention Analysis")
    for name, by_id in mode_preds.items():
        abstained = [
            cid for cid in case_order
            if by_id[cid].get("decision") == "abstain"
            or by_id[cid].get("primary_diagnosis") is None
        ]
        subsection(f"Abstentions — {name.upper()}: {len(abstained)}/{len(case_order)}")
        if not abstained:
            print("  No abstentions.")
            continue
        gold_dist = Counter(parent_code(gold_map[cid][0]) for cid in abstained)
        print(f"  {'Class':<8} {'Count':>6}  {'Name'}")
        hr("·", 50)
        for cls, cnt in gold_dist.most_common():
            print(f"  {cls:<8} {cnt:>6}  {DISORDER_NAMES.get(cls, cls)}")
        # Correct if not abstained?
        other_modes = [m for m in mode_preds if m != name]
        if other_modes:
            ref = other_modes[0]
            ref_correct_on_abstained = sum(
                1 for cid in abstained
                if is_correct(mode_preds[ref][cid].get("primary_diagnosis"), gold_map[cid])
            )
            print(f"\n  {ref} correctness on these abstained cases: "
                  f"{ref_correct_on_abstained}/{len(abstained)}")


# ─────────────────────────────────────────────────────────────────────────────
# Section 8: Confidence calibration
# ─────────────────────────────────────────────────────────────────────────────

def print_confidence_calibration(gold_map, case_order, mode_preds):
    section("8. Confidence Calibration (accuracy per confidence bin)")
    bins = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
    bin_labels = ["[0.0,0.5)", "[0.5,0.6)", "[0.6,0.7)", "[0.7,0.8)", "[0.8,0.9)", "[0.9,1.0]"]

    for name, by_id in mode_preds.items():
        subsection(f"Confidence Calibration — {name.upper()}")
        bin_correct = defaultdict(list)
        for cid in case_order:
            p = by_id[cid]
            conf = p.get("confidence")
            pred = p.get("primary_diagnosis")
            if conf is None:
                continue
            correct = is_correct(pred, gold_map[cid])
            for i in range(len(bins) - 1):
                if bins[i] <= conf < bins[i + 1]:
                    bin_correct[bin_labels[i]].append(correct)
                    break

        w = [12, 8, 8, 10, 14]
        table_row("Conf Bin", "Count", "Correct", "Acc", "Calibration Gap", widths=w)
        hr("·", 70)
        total_correct = 0
        total_count = 0
        for bl in bin_labels:
            vals = bin_correct[bl]
            if not vals:
                table_row(bl, 0, 0, "N/A", "N/A", widths=w)
                continue
            n = len(vals)
            c = sum(vals)
            acc = c / n
            mid_conf = (bins[bin_labels.index(bl)] + bins[bin_labels.index(bl) + 1]) / 2
            gap = acc - mid_conf
            total_correct += c
            total_count += n
            table_row(bl, n, c, pct(acc), f"{gap:+.3f}", widths=w)
        hr("·", 70)
        overall_acc = total_correct / total_count if total_count > 0 else float("nan")
        table_row("TOTAL", total_count, total_correct, pct(overall_acc), "", widths=w)

        # ECE
        ece_sum = 0.0
        for bl in bin_labels:
            vals = bin_correct[bl]
            if not vals:
                continue
            n = len(vals)
            acc = sum(vals) / n
            mid_conf = (bins[bin_labels.index(bl)] + bins[bin_labels.index(bl) + 1]) / 2
            ece_sum += (n / total_count) * abs(acc - mid_conf)
        print(f"\n  Expected Calibration Error (ECE): {ece_sum:.4f}")


# ─────────────────────────────────────────────────────────────────────────────
# Section 9: Agreement analysis
# ─────────────────────────────────────────────────────────────────────────────

def print_agreement_analysis(gold_map, case_order, mode_preds):
    section("9. Cross-Mode Agreement Analysis")
    mode_names = list(mode_preds.keys())
    N = len(case_order)

    # Pairwise agreement
    subsection("Pairwise Agreement (same prediction)")
    from itertools import combinations
    w = [14, 14, 10, 10, 10]
    table_row("Mode A", "Mode B", "Agree", "Pct", "When agree: Acc", widths=w)
    hr("·", 70)
    for a, b in combinations(mode_names, 2):
        agree = 0
        agree_correct = 0
        for cid in case_order:
            pa = normalize_predicted(mode_preds[a][cid].get("primary_diagnosis"))
            pb = normalize_predicted(mode_preds[b][cid].get("primary_diagnosis"))
            if pa == pb:
                agree += 1
                if is_correct(mode_preds[a][cid].get("primary_diagnosis"), gold_map[cid]):
                    agree_correct += 1
        acc_when_agree = agree_correct / agree if agree > 0 else float("nan")
        table_row(
            a, b,
            agree, pct(agree / N), pct(acc_when_agree),
            widths=w
        )

    # Full N-way agreement
    subsection("N-Way Agreement Breakdown")
    full_agree = 0
    all_disagree = 0
    partial_agree = 0
    full_agree_correct = 0

    for cid in case_order:
        preds = {name: normalize_predicted(mode_preds[name][cid].get("primary_diagnosis"))
                 for name in mode_names}
        unique_preds = set(v for v in preds.values() if v is not None)
        if len(unique_preds) == 1 and None not in preds.values():
            full_agree += 1
            if is_correct(list(mode_preds.values())[0][cid].get("primary_diagnosis"), gold_map[cid]):
                full_agree_correct += 1
        elif len(unique_preds) == len(mode_names):
            all_disagree += 1
        else:
            partial_agree += 1

    print(f"\n  All {len(mode_names)} modes agree (same non-null pred): "
          f"{full_agree} ({full_agree/N*100:.1f}%)")
    print(f"  Accuracy when all agree: "
          f"{full_agree_correct}/{full_agree} "
          f"({full_agree_correct/full_agree*100:.1f}%)" if full_agree > 0 else "")
    print(f"  All modes disagree:   {all_disagree} ({all_disagree/N*100:.1f}%)")
    print(f"  Partial agreement:    {partial_agree} ({partial_agree/N*100:.1f}%)")

    # When modes disagree, who is right more often?
    subsection("Who Is Right on Disagreement Cases?")
    disagree_cases = []
    for cid in case_order:
        preds = {name: normalize_predicted(mode_preds[name][cid].get("primary_diagnosis"))
                 for name in mode_names}
        unique_preds = set(v for v in preds.values() if v is not None)
        # Disagreement: not all the same
        if len(unique_preds) > 1 or any(v is None for v in preds.values()):
            disagree_cases.append(cid)

    print(f"\n  Total disagreement cases: {len(disagree_cases)}")
    print()
    for name, by_id in mode_preds.items():
        n_right = sum(
            is_correct(by_id[cid].get("primary_diagnosis"), gold_map[cid])
            for cid in disagree_cases
        )
        print(f"  {name:14s}: {n_right:3d}/{len(disagree_cases)} correct on disagreement cases "
              f"({n_right/len(disagree_cases)*100:.1f}%)")

    # Majority vote accuracy
    subsection("Majority Vote Accuracy (plurality of non-null predictions)")
    mv_correct = 0
    mv_total = 0
    for cid in case_order:
        preds = [
            normalize_predicted(mode_preds[name][cid].get("primary_diagnosis"))
            for name in mode_names
        ]
        non_null = [p for p in preds if p is not None]
        if not non_null:
            continue
        vote = Counter(non_null).most_common(1)[0][0]
        mv_total += 1
        if is_correct(vote, gold_map[cid]):
            mv_correct += 1
    print(f"\n  Majority vote accuracy: {mv_correct}/{mv_total} = {mv_correct/mv_total*100:.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    gold_map, case_order, mode_preds = load_all_data()

    print("\n" + "═" * 100)
    print("  CultureDx  |  MDD-5k N=200  |  Comprehensive Analysis Report")
    print("  Modes: hied, single, psycot, v8_nodiff (ablation)")
    print("═" * 100)

    # ── 1. Overall accuracy summary ────────────────────────────────────────
    section("1. Overall Accuracy Summary")
    acc_results = compute_accuracy(gold_map, case_order, mode_preds)
    w = [14, 10, 10, 10]
    table_row("Mode", "Correct", "Total", "Accuracy", widths=w)
    hr("·", 55)
    for name, (correct, total, acc) in acc_results.items():
        table_row(name, correct, total, pct(acc), widths=w)

    # ── 2. Confusion matrices ──────────────────────────────────────────────
    section("2. Full Confusion Matrices (parent-code level)")
    for name, by_id in mode_preds.items():
        cm, classes = build_confusion_matrix(gold_map, case_order, by_id)
        print_confusion_matrix(cm, classes, name)

    # ── 3. Per-class metrics ───────────────────────────────────────────────
    section("3. Per-Class Precision / Recall / F1")
    all_metrics = {}
    for name, by_id in mode_preds.items():
        m = per_class_metrics(gold_map, case_order, by_id)
        all_metrics[name] = m
        print_per_class_metrics(m, name)

    # Comparative macro F1 summary
    subsection("Macro F1 Summary Across Modes")
    for name, m in all_metrics.items():
        mf = macro_f1(m)
        print(f"  {name:14s}: macro-F1 = {mf:.4f}")

    # ── 4. McNemar ─────────────────────────────────────────────────────────
    print_mcnemar(gold_map, case_order, mode_preds)

    # ── 5. Bootstrap CIs ───────────────────────────────────────────────────
    print_bootstrap(gold_map, case_order, mode_preds)

    # ── 6. Error analysis ──────────────────────────────────────────────────
    print_error_analysis(gold_map, case_order, mode_preds)

    # ── 7. Abstention ──────────────────────────────────────────────────────
    print_abstention_analysis(gold_map, case_order, mode_preds)

    # ── 8. Confidence calibration ──────────────────────────────────────────
    print_confidence_calibration(gold_map, case_order, mode_preds)

    # ── 9. Agreement analysis ──────────────────────────────────────────────
    print_agreement_analysis(gold_map, case_order, mode_preds)

    print("\n" + "═" * 100)
    print("  End of Report")
    print("═" * 100 + "\n")


if __name__ == "__main__":
    main()
