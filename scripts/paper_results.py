"""Generate all publication-ready tables and statistics from existing sweep data.

Produces 6 markdown tables for the CultureDx paper:
  Table 1 — Main Results (3 modes x 2 datasets)
  Table 2 — Per-Disorder Recall
  Table 3 — F41->F32 Error Analysis
  Table 4 — Confidence Calibration
  Table 5 — V10 Ablation (LingxiDiag only)
  Table 6 — Cross-Mode Agreement (LingxiDiag)

Usage:
    uv run python scripts/paper_results.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Sequence

# -- Project imports -----------------------------------------------------------
from culturedx.eval.calibration import compute_calibration
from culturedx.eval.statistical_tests import mcnemar_test

# -- Paths ---------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
SWEEPS = ROOT / "outputs" / "sweeps"

SWEEP_DIRS: dict[str, dict[str, Path | None]] = {
    "LingxiDiag": {
        "baseline": SWEEPS / "lingxidiag_3mode_crossval_20260320_195057",
        "v10": SWEEPS / "v10_lingxidiag_20260320_222603",
    },
    "MDD-5k": {
        "baseline": SWEEPS / "n200_3mode_20260320_131920",
        "v10": None,  # NOT COMPLETE YET
    },
}

MODE_ORDER = ["hied", "psycot", "single"]
MODE_LABELS = {"hied": "HiED", "psycot": "PsyCoT", "single": "Single"}
DATASET_ORDER = ["LingxiDiag", "MDD-5k"]
PRIMARY_TARGETS = {"F32", "F41"}

# F32 parent-code group: F32 matches predictions F32.x and F33.x
F32_MATCH_PARENTS = {"F32", "F33"}


# -- Helpers -------------------------------------------------------------------

def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def parent_code(code: str | None) -> str | None:
    """F32.1 -> F32, F41 -> F41, None -> None."""
    return code.split(".", 1)[0] if code else None


def gold_parent_codes(labels: list[str]) -> set[str]:
    """Set of parent codes for gold labels."""
    return {parent_code(lb) for lb in labels if lb} - {None}


def gold_primary(labels: list[str]) -> str | None:
    """Parent code of first gold label."""
    return parent_code(labels[0]) if labels else None


# -- Data Structures -----------------------------------------------------------

@dataclass
class Prediction:
    case_id: str
    primary_diagnosis: str | None
    comorbid_diagnoses: list[str]
    confidence: float | None
    decision: str | None


@dataclass
class SweepData:
    dataset_name: str
    sweep_dir: Path
    case_ids: list[str]
    gold_map: dict[str, list[str]]
    mode_preds: dict[str, dict[str, Prediction]]


def is_abstention(pred: Prediction | None) -> bool:
    return (
        pred is None
        or pred.primary_diagnosis is None
        or pred.decision == "abstain"
    )


def pred_parent(pred: Prediction | None) -> str | None:
    if is_abstention(pred):
        return None
    return parent_code(pred.primary_diagnosis)


def top1_correct(pred: Prediction | None, gold_labels: list[str]) -> bool:
    pp = pred_parent(pred)
    if pp is None:
        return False
    gp = gold_primary(gold_labels)
    if gp is None:
        return False
    # parent-code matching: F32 gold matches F32/F33 prediction
    if gp in F32_MATCH_PARENTS:
        return pp in F32_MATCH_PARENTS
    return pp == gp


def top3_codes(pred: Prediction | None) -> list[str]:
    """Return up to 3 parent-normalised diagnosis codes (primary + comorbids)."""
    if is_abstention(pred):
        return []
    codes: list[str] = []
    seen: set[str] = set()
    raw = pred.primary_diagnosis
    p = parent_code(raw)
    if p and p not in seen:
        codes.append(p)
        seen.add(p)
    for c in pred.comorbid_diagnoses:
        p = parent_code(c)
        if p and p not in seen:
            codes.append(p)
            seen.add(p)
        if len(codes) >= 3:
            break
    return codes[:3]


def top3_correct(pred: Prediction | None, gold_labels: list[str]) -> bool:
    codes = top3_codes(pred)
    gp = gold_primary(gold_labels)
    if gp is None:
        return False
    if gp in F32_MATCH_PARENTS:
        return bool(set(codes) & F32_MATCH_PARENTS)
    return gp in codes


# -- Loader --------------------------------------------------------------------

def load_sweep(dataset_name: str, sweep_dir: Path) -> SweepData:
    case_list = load_json(sweep_dir / "case_list.json")
    cases = case_list["cases"]
    case_ids = [str(c["case_id"]) for c in cases]
    gold_map = {
        str(c["case_id"]): [str(lb) for lb in c.get("diagnoses", [])]
        for c in cases
    }
    mode_preds: dict[str, dict[str, Prediction]] = {}
    for child in sorted(sweep_dir.iterdir()):
        if not child.is_dir() or not child.name.endswith("_no_evidence"):
            continue
        pred_path = child / "predictions.json"
        if not pred_path.is_file():
            continue
        raw = load_json(pred_path)
        mode = child.name.removesuffix("_no_evidence")
        mode_preds[mode] = {
            str(e["case_id"]): Prediction(
                case_id=str(e["case_id"]),
                primary_diagnosis=e.get("primary_diagnosis"),
                comorbid_diagnoses=e.get("comorbid_diagnoses", []),
                confidence=e.get("confidence"),
                decision=e.get("decision"),
            )
            for e in raw.get("predictions", [])
        }
    return SweepData(dataset_name, sweep_dir, case_ids, gold_map, mode_preds)


# -- Metric Computations -------------------------------------------------------

@dataclass
class ModeMetrics:
    mode: str
    dataset: str
    n: int
    top1: float
    top3: float
    macro_f1: float
    correct_flags: list[bool]
    # Per-disorder recall
    f32_recall: float | None
    f41_recall: float | None
    others_recall: float | None
    f32_support: int
    f41_support: int
    others_support: int
    # Error analysis
    f41_to_f32_count: int
    f41_total: int
    # Calibration
    ece: float | None
    mce: float | None
    mean_conf_correct: float | None
    mean_conf_wrong: float | None
    mean_conf_all: float | None
    # Per-case predictions for agreement
    case_parent_preds: dict[str, str | None] = field(default_factory=dict)


def compute_mode_metrics(
    sweep: SweepData,
    mode: str,
) -> ModeMetrics | None:
    if mode not in sweep.mode_preds:
        return None
    preds = sweep.mode_preds[mode]
    case_ids = sweep.case_ids
    n = len(case_ids)

    correct_flags: list[bool] = []
    top3_flags: list[bool] = []
    pred_labels: list[str] = []
    gold_labels_flat: list[str] = []

    f32_support = f41_support = others_support = 0
    f32_hits = f41_hits = others_hits = 0
    f41_total = f41_to_f32 = 0

    confs_correct: list[float] = []
    confs_wrong: list[float] = []
    confs_all: list[float] = []
    cal_confs: list[float] = []
    cal_correct: list[bool] = []

    case_parent_preds: dict[str, str | None] = {}

    for cid in case_ids:
        gold = sweep.gold_map[cid]
        pred = preds.get(cid)
        pp = pred_parent(pred)
        gp = gold_primary(gold)

        case_parent_preds[cid] = pp

        c1 = top1_correct(pred, gold)
        c3 = top3_correct(pred, gold)
        correct_flags.append(c1)
        top3_flags.append(c3)

        # For macro F1: use parent-normalised labels
        pred_labels.append(pp or "ABSTAIN")
        gold_labels_flat.append(gp or "UNK")

        # Per-disorder recall
        if gp in F32_MATCH_PARENTS:
            f32_support += 1
            if pp in F32_MATCH_PARENTS:
                f32_hits += 1
        elif gp == "F41":
            f41_support += 1
            f41_total += 1
            if pp == "F41":
                f41_hits += 1
            if pp in F32_MATCH_PARENTS:
                f41_to_f32 += 1
        else:
            others_support += 1
            if pp is not None and pp not in F32_MATCH_PARENTS and pp != "F41":
                others_hits += 1

        # Confidence
        if not is_abstention(pred) and pred.confidence is not None:
            conf = float(pred.confidence)
            confs_all.append(conf)
            cal_confs.append(conf)
            cal_correct.append(c1)
            if c1:
                confs_correct.append(conf)
            else:
                confs_wrong.append(conf)

    top1 = sum(correct_flags) / n if n else 0.0
    top3 = sum(top3_flags) / n if n else 0.0

    # Macro F1 via sklearn
    from sklearn.metrics import f1_score
    mf1 = float(f1_score(gold_labels_flat, pred_labels, average="macro", zero_division=0))

    f32_recall = (f32_hits / f32_support) if f32_support else None
    f41_recall = (f41_hits / f41_support) if f41_support else None
    others_recall = (others_hits / others_support) if others_support else None

    # Calibration
    ece = mce = None
    if cal_confs:
        cal_result = compute_calibration(cal_confs, cal_correct, mode=mode)
        ece = cal_result.ece
        mce = cal_result.mce

    mean_conf_correct = (sum(confs_correct) / len(confs_correct)) if confs_correct else None
    mean_conf_wrong = (sum(confs_wrong) / len(confs_wrong)) if confs_wrong else None
    mean_conf_all = (sum(confs_all) / len(confs_all)) if confs_all else None

    return ModeMetrics(
        mode=mode,
        dataset=sweep.dataset_name,
        n=n,
        top1=top1,
        top3=top3,
        macro_f1=mf1,
        correct_flags=correct_flags,
        f32_recall=f32_recall,
        f41_recall=f41_recall,
        others_recall=others_recall,
        f32_support=f32_support,
        f41_support=f41_support,
        others_support=others_support,
        f41_to_f32_count=f41_to_f32,
        f41_total=f41_total,
        ece=ece,
        mce=mce,
        mean_conf_correct=mean_conf_correct,
        mean_conf_wrong=mean_conf_wrong,
        mean_conf_all=mean_conf_all,
        case_parent_preds=case_parent_preds,
    )


# -- Formatters ----------------------------------------------------------------

def pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.1f}"


def pct_sign(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:+.1f}"


def flt(v: float | None, d: int = 3) -> str:
    return "—" if v is None else f"{v:.{d}f}"


def p_str(p: float) -> str:
    if p < 0.001:
        return "<.001"
    if p < 0.01:
        return f"{p:.3f}"
    return f"{p:.2f}"


def md_table(headers: list[str], rows: list[list[str]], align: list[str] | None = None) -> str:
    """Build a markdown table string."""
    if align is None:
        align = ["l"] * len(headers)
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    seps = []
    for a in align:
        if a == "r":
            seps.append("---:")
        elif a == "c":
            seps.append(":---:")
        else:
            seps.append(":---")
    lines.append("| " + " | ".join(seps) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


# -- Main ----------------------------------------------------------------------

def main() -> int:
    # Load all sweeps
    sweeps: dict[str, SweepData] = {}
    for ds_name in DATASET_ORDER:
        bdir = SWEEP_DIRS[ds_name]["baseline"]
        if bdir and bdir.is_dir():
            sweeps[ds_name] = load_sweep(ds_name, bdir)

    v10_sweeps: dict[str, SweepData] = {}
    for ds_name in DATASET_ORDER:
        vdir = SWEEP_DIRS[ds_name].get("v10")
        if vdir and vdir.is_dir():
            v10_sweeps[ds_name] = load_sweep(ds_name, vdir)

    # Compute all metrics
    all_metrics: dict[str, dict[str, ModeMetrics]] = {}  # dataset -> mode -> metrics
    for ds_name, sweep in sweeps.items():
        all_metrics[ds_name] = {}
        for mode in MODE_ORDER:
            m = compute_mode_metrics(sweep, mode)
            if m is not None:
                all_metrics[ds_name][mode] = m

    v10_metrics: dict[str, dict[str, ModeMetrics]] = {}
    for ds_name, sweep in v10_sweeps.items():
        v10_metrics[ds_name] = {}
        for mode in MODE_ORDER:
            m = compute_mode_metrics(sweep, mode)
            if m is not None:
                v10_metrics[ds_name][mode] = m

    # == TABLE 1: Main Results ==================================================
    print("=" * 80)
    print("TABLE 1: Main Results (N=200 per dataset, parent-code matching)")
    print("=" * 80)
    print()

    headers = ["Dataset", "Mode", "Top-1 (%)", "Top-3 (%)", "Macro F1",
               "McNemar p (vs Single)"]
    aligns = ["l", "l", "r", "r", "r", "r"]
    rows: list[list[str]] = []
    for ds_name in DATASET_ORDER:
        ds_modes = all_metrics.get(ds_name, {})
        if not ds_modes:
            continue
        single_flags = ds_modes.get("single", None)
        for mode in MODE_ORDER:
            m = ds_modes.get(mode)
            if m is None:
                continue
            # McNemar vs Single
            p_val = "—"
            if mode != "single" and single_flags is not None:
                result = mcnemar_test(m.correct_flags, single_flags.correct_flags)
                p_val = p_str(result["p_value"])
            elif mode == "single":
                p_val = "ref"
            rows.append([
                ds_name,
                MODE_LABELS.get(mode, mode),
                pct(m.top1),
                pct(m.top3),
                flt(m.macro_f1),
                p_val,
            ])

    print(md_table(headers, rows, aligns))
    print()

    # == TABLE 2: Per-Disorder Recall ==========================================
    print("=" * 80)
    print("TABLE 2: Per-Disorder Recall (%, parent-code matching)")
    print("=" * 80)
    print()

    headers2 = ["Dataset", "Mode",
                 "F32 Recall", "F32 n",
                 "F41 Recall", "F41 n",
                 "Others Recall", "Others n"]
    aligns2 = ["l", "l", "r", "r", "r", "r", "r", "r"]
    rows2: list[list[str]] = []
    for ds_name in DATASET_ORDER:
        ds_modes = all_metrics.get(ds_name, {})
        for mode in MODE_ORDER:
            m = ds_modes.get(mode)
            if m is None:
                continue
            rows2.append([
                ds_name,
                MODE_LABELS.get(mode, mode),
                pct(m.f32_recall),
                str(m.f32_support),
                pct(m.f41_recall),
                str(m.f41_support),
                pct(m.others_recall),
                str(m.others_support),
            ])

    print(md_table(headers2, rows2, aligns2))
    print()

    # == TABLE 3: F41->F32 Error Analysis ======================================
    print("=" * 80)
    print("TABLE 3: F41 -> F32 Misclassification (parent-code matching)")
    print("=" * 80)
    print()

    headers3 = ["Dataset", "Mode", "True F41 (n)", "Pred F32 (count)", "Error Rate (%)"]
    aligns3 = ["l", "l", "r", "r", "r"]
    rows3: list[list[str]] = []
    for ds_name in DATASET_ORDER:
        ds_modes = all_metrics.get(ds_name, {})
        for mode in MODE_ORDER:
            m = ds_modes.get(mode)
            if m is None:
                continue
            rate = (m.f41_to_f32_count / m.f41_total * 100) if m.f41_total else 0
            rows3.append([
                ds_name,
                MODE_LABELS.get(mode, mode),
                str(m.f41_total),
                str(m.f41_to_f32_count),
                f"{rate:.1f}",
            ])

    print(md_table(headers3, rows3, aligns3))
    print()

    # == TABLE 4: Confidence Calibration =======================================
    print("=" * 80)
    print("TABLE 4: Confidence Calibration (non-abstaining predictions)")
    print("=" * 80)
    print()

    headers4 = ["Dataset", "Mode", "ECE", "MCE",
                 "Mean Conf (correct)", "Mean Conf (wrong)", "Mean Conf (all)"]
    aligns4 = ["l", "l", "r", "r", "r", "r", "r"]
    rows4: list[list[str]] = []
    for ds_name in DATASET_ORDER:
        ds_modes = all_metrics.get(ds_name, {})
        for mode in MODE_ORDER:
            m = ds_modes.get(mode)
            if m is None:
                continue
            rows4.append([
                ds_name,
                MODE_LABELS.get(mode, mode),
                flt(m.ece),
                flt(m.mce),
                flt(m.mean_conf_correct),
                flt(m.mean_conf_wrong),
                flt(m.mean_conf_all),
            ])

    print(md_table(headers4, rows4, aligns4))
    print()

    # == TABLE 5: V10 Ablation =================================================
    print("=" * 80)
    print("TABLE 5: V10 Ablation -- LingxiDiag (Baseline vs V10)")
    print("=" * 80)
    print()

    ds_for_v10 = "LingxiDiag"
    base_modes = all_metrics.get(ds_for_v10, {})
    v10_modes = v10_metrics.get(ds_for_v10, {})

    if base_modes and v10_modes:
        headers5 = [
            "Mode", "Version",
            "Top-1 (%)", "Top-3 (%)", "Macro F1",
            "F41 Recall (%)", "F41->F32 Rate (%)", "ECE",
            "McNemar p",
        ]
        aligns5 = ["l", "l", "r", "r", "r", "r", "r", "r", "r"]
        rows5: list[list[str]] = []
        for mode in MODE_ORDER:
            bm = base_modes.get(mode)
            vm = v10_modes.get(mode)
            if bm is None:
                continue
            # Baseline row
            rows5.append([
                MODE_LABELS.get(mode, mode),
                "Baseline",
                pct(bm.top1),
                pct(bm.top3),
                flt(bm.macro_f1),
                pct(bm.f41_recall),
                f"{bm.f41_to_f32_count / bm.f41_total * 100:.1f}" if bm.f41_total else "—",
                flt(bm.ece),
                "—",
            ])
            if vm is not None:
                # McNemar test
                mcn = mcnemar_test(bm.correct_flags, vm.correct_flags)
                rows5.append([
                    MODE_LABELS.get(mode, mode),
                    "V10",
                    pct(vm.top1),
                    pct(vm.top3),
                    flt(vm.macro_f1),
                    pct(vm.f41_recall),
                    f"{vm.f41_to_f32_count / vm.f41_total * 100:.1f}" if vm.f41_total else "—",
                    flt(vm.ece),
                    p_str(mcn["p_value"]),
                ])
                # Delta row
                d_top1 = (vm.top1 - bm.top1) if vm.top1 is not None else None
                d_top3 = (vm.top3 - bm.top3) if vm.top3 is not None else None
                d_f1 = (vm.macro_f1 - bm.macro_f1)
                d_f41r = (vm.f41_recall - bm.f41_recall) if (
                    vm.f41_recall is not None and bm.f41_recall is not None
                ) else None
                d_f41f32 = None
                if bm.f41_total and vm.f41_total:
                    d_f41f32 = (
                        vm.f41_to_f32_count / vm.f41_total
                        - bm.f41_to_f32_count / bm.f41_total
                    )
                d_ece = (vm.ece - bm.ece) if (vm.ece is not None and bm.ece is not None) else None
                rows5.append([
                    "",
                    "**Delta**",
                    pct_sign(d_top1),
                    pct_sign(d_top3),
                    f"{d_f1:+.3f}",
                    pct_sign(d_f41r),
                    pct_sign(d_f41f32) if d_f41f32 is not None else "—",
                    f"{d_ece:+.3f}" if d_ece is not None else "—",
                    "",
                ])
            else:
                rows5.append([
                    MODE_LABELS.get(mode, mode),
                    "V10",
                    "—", "—", "—", "—", "—", "—",
                    "N/A (not run)",
                ])

        print(md_table(headers5, rows5, aligns5))
    else:
        print("(V10 data not available for LingxiDiag -- skipping)")

    # V10 MDD-5k placeholder
    print()
    print("Note: V10 MDD-5k results are not yet complete. Placeholder reserved.")
    print()

    # == TABLE 6: Cross-Mode Agreement (LingxiDiag) ============================
    print("=" * 80)
    print("TABLE 6: Cross-Mode Agreement -- LingxiDiag (N=200)")
    print("=" * 80)
    print()

    ds_agree = "LingxiDiag"
    ds_modes_agree = all_metrics.get(ds_agree, {})
    available_modes = [m for m in MODE_ORDER if m in ds_modes_agree]

    if len(available_modes) >= 2:
        sweep = sweeps[ds_agree]
        case_ids = sweep.case_ids

        # Pairwise agreement
        headers6a = ["Mode A", "Mode B", "Agreement (%)", "Both Correct (%)",
                      "Both Wrong (%)", "Disagree (%)"]
        aligns6a = ["l", "l", "r", "r", "r", "r"]
        rows6a: list[list[str]] = []
        for ma, mb in combinations(available_modes, 2):
            mm_a = ds_modes_agree[ma]
            mm_b = ds_modes_agree[mb]
            agree = 0
            both_correct = 0
            both_wrong = 0
            disagree = 0
            for cid in case_ids:
                pa = mm_a.case_parent_preds.get(cid)
                pb = mm_b.case_parent_preds.get(cid)
                if pa == pb:
                    agree += 1
                    gold = sweep.gold_map[cid]
                    gp = gold_primary(gold)
                    # Check if the agreed prediction is correct
                    if pa is not None and gp is not None:
                        if gp in F32_MATCH_PARENTS:
                            c = pa in F32_MATCH_PARENTS
                        else:
                            c = pa == gp
                        if c:
                            both_correct += 1
                        else:
                            both_wrong += 1
                    else:
                        both_wrong += 1  # both abstained or no gold
                else:
                    disagree += 1
            n = len(case_ids)
            rows6a.append([
                MODE_LABELS.get(ma, ma),
                MODE_LABELS.get(mb, mb),
                f"{agree / n * 100:.1f}",
                f"{both_correct / n * 100:.1f}",
                f"{both_wrong / n * 100:.1f}",
                f"{disagree / n * 100:.1f}",
            ])

        print("### Pairwise Agreement")
        print()
        print(md_table(headers6a, rows6a, aligns6a))
        print()

        # Majority vote and oracle accuracy
        if len(available_modes) >= 3:
            maj_correct = 0
            oracle_correct = 0
            n = len(case_ids)
            for cid in case_ids:
                gold = sweep.gold_map[cid]
                gp = gold_primary(gold)
                preds_for_case = []
                any_correct = False
                for mode in available_modes:
                    pp = ds_modes_agree[mode].case_parent_preds.get(cid)
                    preds_for_case.append(pp)
                    if pp is not None and gp is not None:
                        if gp in F32_MATCH_PARENTS:
                            c = pp in F32_MATCH_PARENTS
                        else:
                            c = pp == gp
                        if c:
                            any_correct = True

                # Majority vote
                vote_counts = Counter(p for p in preds_for_case if p is not None)
                if vote_counts:
                    majority_pred = vote_counts.most_common(1)[0][0]
                    if gp is not None:
                        if gp in F32_MATCH_PARENTS:
                            if majority_pred in F32_MATCH_PARENTS:
                                maj_correct += 1
                        elif majority_pred == gp:
                            maj_correct += 1

                if any_correct:
                    oracle_correct += 1

            print("### Ensemble Accuracy")
            print()
            headers6b = ["Method", "Top-1 Accuracy (%)"]
            aligns6b = ["l", "r"]
            rows6b: list[list[str]] = []
            for mode in available_modes:
                m = ds_modes_agree[mode]
                rows6b.append([MODE_LABELS.get(mode, mode), pct(m.top1)])
            rows6b.append(["**Majority Vote**", f"{maj_correct / n * 100:.1f}"])
            rows6b.append(["**Oracle (any-correct)**", f"{oracle_correct / n * 100:.1f}"])
            print(md_table(headers6b, rows6b, aligns6b))
            print()

    else:
        print("(Fewer than 2 modes available -- skipping agreement analysis)")

    # == Summary Statistics =====================================================
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    for ds_name in DATASET_ORDER:
        ds_modes = all_metrics.get(ds_name, {})
        if not ds_modes:
            continue
        print(f"  {ds_name}:")
        for mode in MODE_ORDER:
            m = ds_modes.get(mode)
            if m is None:
                continue
            print(
                f"    {MODE_LABELS.get(mode, mode):8s}: "
                f"Top-1={pct(m.top1)}%  Top-3={pct(m.top3)}%  "
                f"F1={flt(m.macro_f1)}  "
                f"F41->F32={m.f41_to_f32_count}/{m.f41_total}"
            )
    print()
    if v10_modes:
        print(f"  {ds_for_v10} V10:")
        for mode in MODE_ORDER:
            m = v10_modes.get(mode)
            if m is None:
                continue
            print(
                f"    {MODE_LABELS.get(mode, mode):8s}: "
                f"Top-1={pct(m.top1)}%  Top-3={pct(m.top3)}%  "
                f"F1={flt(m.macro_f1)}  "
                f"F41->F32={m.f41_to_f32_count}/{m.f41_total}"
            )
    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
