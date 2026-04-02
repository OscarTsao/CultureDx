#!/usr/bin/env python3
"""Verify alignment between our lingxidiag_paper.py and the official LingxiDiagBench code.

Runs both implementations on identical test inputs and reports any differences.
"""
from __future__ import annotations

import sys
import os
import re
import traceback

# ── Add official repo to path ──────────────────────────────────────
sys.path.insert(0, "/tmp/LingxiDiagBench/evaluation/static")
sys.path.insert(0, "/tmp/LingxiDiagBench/evaluation")

# ── Import official ────────────────────────────────────────────────
from data_utils import (
    extract_f_codes_from_diagnosis_code as official_extract_f_codes,
    extract_detailed_codes as official_extract_detailed,
    classify_2class as official_classify_2class,
    classify_4class as official_classify_4class,
)
from metrics import (
    calculate_singlelabel_metrics as official_singlelabel,
    calculate_multilabel_metrics as official_multilabel,
)

# Also import the doctor_eval version for comparison
from doctor_eval_multilabel import (
    extract_f_codes_from_diagnosis_code as doctor_extract_f_codes,
    extract_detailed_codes as doctor_extract_detailed,
    classify_2class as doctor_classify_2class,
    classify_4class as doctor_classify_4class,
    calculate_multilabel_metrics as doctor_multilabel,
)

# ── Import ours ────────────────────────────────────────────────────
sys.path.insert(0, "/home/user/YuNing/CultureDx/src")
from culturedx.eval.lingxidiag_paper import (
    to_paper_parent,
    gold_to_parent_list,
    classify_2class_from_raw,
    classify_4class_from_raw,
    compute_singlelabel_metrics as our_singlelabel,
    compute_multilabel_metrics as our_multilabel,
)

# ── Counters ───────────────────────────────────────────────────────
PASS_COUNT = 0
FAIL_COUNT = 0

def check(name: str, ours, theirs, context: str = ""):
    global PASS_COUNT, FAIL_COUNT
    if ours == theirs:
        PASS_COUNT += 1
        print(f"  PASS  {name}: {ours}")
    else:
        FAIL_COUNT += 1
        print(f"  FAIL  {name}: ours={ours}  theirs={theirs}  {context}")


def check_close(name: str, ours_val, theirs_val, tol: float = 1e-10, context: str = ""):
    global PASS_COUNT, FAIL_COUNT
    if ours_val is None and theirs_val is None:
        PASS_COUNT += 1
        print(f"  PASS  {name}: None (both)")
        return
    if ours_val is None or theirs_val is None:
        FAIL_COUNT += 1
        print(f"  FAIL  {name}: ours={ours_val}  theirs={theirs_val}  {context}")
        return
    if abs(float(ours_val) - float(theirs_val)) < tol:
        PASS_COUNT += 1
        print(f"  PASS  {name}: {ours_val:.10f}")
    else:
        FAIL_COUNT += 1
        print(f"  FAIL  {name}: ours={ours_val:.10f}  theirs={theirs_val:.10f}  {context}")


# ═══════════════════════════════════════════════════════════════════
# 1. gold_to_parent_list  vs  extract_f_codes_from_diagnosis_code
# ═══════════════════════════════════════════════════════════════════
print("=" * 70)
print("TEST 1: gold_to_parent_list vs official extract_f_codes_from_diagnosis_code")
print("=" * 70)

test_codes = [
    "F32.100",
    "F41.200",
    "F32.100;F41.000",
    "F20.000",
    "",
    "Z71",
    "Z71.900",
    "F39",
    "F99.999",
    "F32.000;F41.100;F43.200",
    "F51.000",
    "F98.100",
    "F42.000",
    "F45.100",
    "garbage",
    "F22.000",    # Not in valid set
    "F33.100",    # Not in valid set
    "F40.000",    # Not in valid set
]

for code in test_codes:
    ours = gold_to_parent_list(code)
    theirs_static = official_extract_f_codes(code)
    theirs_doctor = doctor_extract_f_codes(code)

    # Verify the two official implementations agree
    if theirs_static != theirs_doctor:
        print(f"  WARN  Official static vs doctor DISAGREE on '{code}': "
              f"static={theirs_static}, doctor={theirs_doctor}")

    check(f"gold_to_parent_list('{code}')", ours, theirs_static)


# ═══════════════════════════════════════════════════════════════════
# 2. classify_2class_from_raw  vs  official classify_2class
# ═══════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("TEST 2: classify_2class_from_raw vs official classify_2class")
print("=" * 70)

for code in test_codes:
    # Official: need to go through extract_detailed_codes first
    detail = official_extract_detailed(code)
    theirs = official_classify_2class(detail)
    ours = classify_2class_from_raw(code)
    check(f"classify_2class('{code}')", ours, theirs)


# ═══════════════════════════════════════════════════════════════════
# 3. classify_4class_from_raw  vs  official classify_4class
# ═══════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("TEST 3: classify_4class_from_raw vs official classify_4class")
print("=" * 70)

for code in test_codes:
    detail = official_extract_detailed(code)
    theirs = official_classify_4class(detail)
    ours = classify_4class_from_raw(code)
    check(f"classify_4class('{code}')", ours, theirs)


# ═══════════════════════════════════════════════════════════════════
# 4. compute_singlelabel_metrics  vs  official calculate_singlelabel_metrics
# ═══════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("TEST 4: compute_singlelabel_metrics vs official calculate_singlelabel_metrics")
print("=" * 70)

# Case A: Perfect predictions
y_true_2 = ["Depression", "Anxiety", "Depression"]
y_pred_2 = ["Depression", "Anxiety", "Depression"]
labels_2 = ["Depression", "Anxiety"]

ours_a = our_singlelabel(y_true_2, y_pred_2, labels_2)
theirs_a = official_singlelabel(y_true_2, y_pred_2, labels_2)

check_close("Perfect 2class accuracy", ours_a["accuracy"], theirs_a["accuracy"])
check_close("Perfect 2class macro_f1", ours_a["macro_f1"], theirs_a["macro_f1"])
check_close("Perfect 2class weighted_f1", ours_a["weighted_f1"], theirs_a["weighted_f1"])

# Case B: Imperfect predictions
y_true_2b = ["Depression", "Anxiety", "Depression", "Anxiety"]
y_pred_2b = ["Depression", "Depression", "Anxiety", "Anxiety"]

ours_b = our_singlelabel(y_true_2b, y_pred_2b, labels_2)
theirs_b = official_singlelabel(y_true_2b, y_pred_2b, labels_2)

check_close("Imperfect 2class accuracy", ours_b["accuracy"], theirs_b["accuracy"])
check_close("Imperfect 2class macro_f1", ours_b["macro_f1"], theirs_b["macro_f1"])
check_close("Imperfect 2class weighted_f1", ours_b["weighted_f1"], theirs_b["weighted_f1"])

# Case C: 4-class
y_true_4 = ["Depression", "Anxiety", "Mixed", "Others", "Depression"]
y_pred_4 = ["Depression", "Others", "Mixed", "Others", "Mixed"]
labels_4 = ["Depression", "Anxiety", "Mixed", "Others"]

ours_c = our_singlelabel(y_true_4, y_pred_4, labels_4)
theirs_c = official_singlelabel(y_true_4, y_pred_4, labels_4)

check_close("4class accuracy", ours_c["accuracy"], theirs_c["accuracy"])
check_close("4class macro_f1", ours_c["macro_f1"], theirs_c["macro_f1"])
check_close("4class weighted_f1", ours_c["weighted_f1"], theirs_c["weighted_f1"])


# ═══════════════════════════════════════════════════════════════════
# 5. compute_multilabel_metrics  vs  official calculate_multilabel_metrics
# ═══════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("TEST 5: compute_multilabel_metrics vs official calculate_multilabel_metrics")
print("=" * 70)

labels_12 = [
    "F20", "F31", "F32", "F39", "F41", "F42", "F43", "F45", "F51", "F98", "Z71", "Others"
]

# Case A: Perfect
y_true_ml = [["F32"], ["F41"], ["F32", "F41"], ["F20"], ["Z71"]]
y_pred_ml = [["F32"], ["F41"], ["F32", "F41"], ["F20"], ["Z71"]]

ours_ml_a = our_multilabel(y_true_ml, y_pred_ml, labels_12)
theirs_ml_a = official_multilabel(y_true_ml, y_pred_ml, labels_12)

check_close("ML perfect accuracy", ours_ml_a["accuracy"], theirs_ml_a["accuracy"])
check_close("ML perfect top1", ours_ml_a["top1_accuracy"], theirs_ml_a["top1_accuracy"])
check_close("ML perfect top3", ours_ml_a["top3_accuracy"], theirs_ml_a["top3_accuracy"])
check_close("ML perfect macro_f1", ours_ml_a["macro_f1"], theirs_ml_a["macro_f1"])
check_close("ML perfect weighted_f1", ours_ml_a["weighted_f1"], theirs_ml_a["weighted_f1"])

# Case B: Imperfect
y_true_ml_b = [["F32"], ["F41"], ["F32", "F41"], ["F43"], ["Others"]]
y_pred_ml_b = [["F32", "F41"], ["F32"], ["F32"], ["F43", "F45"], ["F32"]]

ours_ml_b = our_multilabel(y_true_ml_b, y_pred_ml_b, labels_12)
theirs_ml_b = official_multilabel(y_true_ml_b, y_pred_ml_b, labels_12)

check_close("ML imperfect accuracy", ours_ml_b["accuracy"], theirs_ml_b["accuracy"])
check_close("ML imperfect top1", ours_ml_b["top1_accuracy"], theirs_ml_b["top1_accuracy"])
check_close("ML imperfect top3", ours_ml_b["top3_accuracy"], theirs_ml_b["top3_accuracy"])
check_close("ML imperfect macro_f1", ours_ml_b["macro_f1"], theirs_ml_b["macro_f1"])
check_close("ML imperfect weighted_f1", ours_ml_b["weighted_f1"], theirs_ml_b["weighted_f1"])

# Case C: All wrong
y_true_ml_c = [["F32"], ["F41"], ["F20"]]
y_pred_ml_c = [["F41"], ["F32"], ["F43"]]

ours_ml_c = our_multilabel(y_true_ml_c, y_pred_ml_c, labels_12)
theirs_ml_c = official_multilabel(y_true_ml_c, y_pred_ml_c, labels_12)

check_close("ML all-wrong accuracy", ours_ml_c["accuracy"], theirs_ml_c["accuracy"])
check_close("ML all-wrong macro_f1", ours_ml_c["macro_f1"], theirs_ml_c["macro_f1"])
check_close("ML all-wrong weighted_f1", ours_ml_c["weighted_f1"], theirs_ml_c["weighted_f1"])


# ═══════════════════════════════════════════════════════════════════
# 6. Cross-check: doctor_eval_multilabel.calculate_multilabel_metrics
#    This uses a DIFFERENT interface (list of tuples) and DIFFERENT
#    computation (manual TP/FP/FN vs sklearn). Compare both officials.
# ═══════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("TEST 6: Static vs Doctor multilabel metrics (both official)")
print("=" * 70)

# The doctor version takes list of (pred, true) tuples
doctor_input_b = list(zip(y_pred_ml_b, y_true_ml_b))
doctor_ml_b = doctor_multilabel(doctor_input_b)

# Compare static (sklearn) vs doctor (manual)
# These should be close but may differ because the doctor version
# only counts classes with support>0 for macro averaging, while
# sklearn's MultiLabelBinarizer includes all classes.
print("  NOTE: Macro F1 may differ: doctor filters to support>0 classes only")
check_close("Static vs Doctor exact_match",
            theirs_ml_b["exact_match_accuracy"], doctor_ml_b["exact_match_accuracy"])
check_close("Static vs Doctor top1",
            theirs_ml_b["top1_accuracy"], doctor_ml_b["top1_accuracy"])
check_close("Static vs Doctor top3",
            theirs_ml_b["top3_accuracy"], doctor_ml_b["top3_accuracy"])

# Macro F1 comparison between the two official implementations
static_macro_f1 = theirs_ml_b["macro_f1"]
doctor_macro_f1 = doctor_ml_b["macro_f1"]
print(f"  INFO  Static macro_f1 = {static_macro_f1:.10f}")
print(f"  INFO  Doctor macro_f1 = {doctor_macro_f1:.10f}")
if abs(static_macro_f1 - doctor_macro_f1) > 0.001:
    print(f"  WARN  Official static and doctor macro_f1 DIFFER by "
          f"{abs(static_macro_f1 - doctor_macro_f1):.6f}")
    print(f"         This is because sklearn includes all 12 classes in macro avg")
    print(f"         while doctor version only includes classes with support>0")

# Compare our macro_f1 against static (sklearn) version, since we also use sklearn
check_close("Our vs static macro_f1", ours_ml_b["macro_f1"], theirs_ml_b["macro_f1"])


# ═══════════════════════════════════════════════════════════════════
# 7. Edge cases
# ═══════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("TEST 7: Edge cases")
print("=" * 70)

# Empty string
check("empty gold_parents", gold_to_parent_list(""), official_extract_f_codes(""))
check("empty 2class", classify_2class_from_raw(""),
      official_classify_2class(official_extract_detailed("")))
check("empty 4class", classify_4class_from_raw(""),
      official_classify_4class(official_extract_detailed("")))

# Pure Z71
check("Z71 gold_parents", gold_to_parent_list("Z71"), official_extract_f_codes("Z71"))
check("Z71 2class", classify_2class_from_raw("Z71"),
      official_classify_2class(official_extract_detailed("Z71")))
check("Z71 4class", classify_4class_from_raw("Z71"),
      official_classify_4class(official_extract_detailed("Z71")))

# Trailing comma
check("trailing comma", gold_to_parent_list("F41.900,"), official_extract_f_codes("F41.900,"))

# F41.2 specifically
check("F41.200 2class excl", classify_2class_from_raw("F41.200"),
      official_classify_2class(official_extract_detailed("F41.200")))
check("F41.200 4class mixed", classify_4class_from_raw("F41.200"),
      official_classify_4class(official_extract_detailed("F41.200")))

# Multiple same-parent codes
check("F32.100;F32.200", gold_to_parent_list("F32.100;F32.200"),
      official_extract_f_codes("F32.100;F32.200"))


# ═══════════════════════════════════════════════════════════════════
# VERDICT
# ═══════════════════════════════════════════════════════════════════
print()
print("=" * 70)
if FAIL_COUNT == 0:
    print(f"VERDICT:  ALIGNED  ({PASS_COUNT} checks passed, 0 failed)")
else:
    print(f"VERDICT:  NOT ALIGNED  ({PASS_COUNT} passed, {FAIL_COUNT} FAILED)")
print("=" * 70)

sys.exit(1 if FAIL_COUNT > 0 else 0)
