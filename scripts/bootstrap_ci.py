"""Bootstrap 95% confidence intervals for all CultureDx main results.

Computes CI for:
  - Top-1 accuracy
  - F41 recall
  - F32 recall
  - Macro F1
  - ECE
  - HiED-Primary ensemble (HiED with Single fallback on abstain) accuracy
  - V10 vs baseline delta (paired, per-case)

Usage:
    uv run python scripts/bootstrap_ci.py

Outputs a formatted markdown table to stdout and writes
  outputs/bootstrap_ci_results.md
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
from sklearn.metrics import f1_score

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SEED = 42
B = 10_000          # bootstrap replicates
CI_LEVEL = 0.95     # percentile CI
ALPHA = 1 - CI_LEVEL

ROOT = Path(__file__).resolve().parents[1]
SWEEPS = ROOT / "outputs" / "sweeps"

SWEEP_DIRS = {
    "LingxiDiag_baseline": SWEEPS / "lingxidiag_3mode_crossval_20260320_195057",
    "LingxiDiag_v10":      SWEEPS / "v10_lingxidiag_20260320_222603",
    "MDD5k_baseline":      SWEEPS / "n200_3mode_20260320_131920",
}

MODE_ORDER = ["hied", "psycot", "single"]
MODE_LABELS = {"hied": "HiED", "psycot": "PsyCoT", "single": "Single"}

# F32/F33 are treated as the same parent group for accuracy purposes.
# Gold F32 -> predicted F32 or F33 counts as correct.
F32_GROUP = {"F32", "F33"}

N_BINS_ECE = 10  # calibration bins

OUTPUT_PATH = ROOT / "outputs" / "bootstrap_ci_results.md"

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict | list:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def parent_code(code: str | None) -> str | None:
    """F32.1 -> F32, F41 -> F41, None -> None."""
    return code.split(".", 1)[0] if code else None


@dataclass
class Case:
    case_id: str
    gold_labels: list[str]           # raw gold codes
    gold_primary_parent: str | None  # parent code of first gold label


@dataclass
class PredEntry:
    case_id: str
    pred_parent: str | None     # parent code of primary_diagnosis (None = abstain)
    confidence: float | None    # None for abstentions
    decision: str               # 'diagnosis' or 'abstain'


def load_cases(sweep_dir: Path) -> dict[str, Case]:
    """Return case_id -> Case mapping."""
    raw = load_json(sweep_dir / "case_list.json")
    cases: dict[str, Case] = {}
    for c in raw["cases"]:
        cid = str(c["case_id"])
        labels = [str(lb) for lb in c.get("diagnoses", [])]
        gp = parent_code(labels[0]) if labels else None
        cases[cid] = Case(case_id=cid, gold_labels=labels, gold_primary_parent=gp)
    return cases


def load_predictions(pred_path: Path) -> dict[str, PredEntry]:
    """Return case_id -> PredEntry mapping."""
    raw = load_json(pred_path)
    entries: dict[str, PredEntry] = {}
    for e in raw.get("predictions", []):
        cid = str(e["case_id"])
        decision = e.get("decision", "diagnosis")
        primary = e.get("primary_diagnosis")
        conf = e.get("confidence")
        if decision == "abstain" or primary is None:
            pred_par = None
            conf_val = None
        else:
            pred_par = parent_code(primary)
            conf_val = float(conf) if conf is not None else None
        entries[cid] = PredEntry(
            case_id=cid,
            pred_parent=pred_par,
            confidence=conf_val,
            decision=decision,
        )
    return entries


def load_sweep_modes(
    sweep_dir: Path,
    modes: list[str],
) -> tuple[dict[str, Case], dict[str, dict[str, PredEntry]]]:
    """Load cases + predictions for all requested modes in a sweep dir.

    Returns:
        cases: case_id -> Case
        mode_preds: mode_name -> (case_id -> PredEntry)
    """
    cases = load_cases(sweep_dir)
    mode_preds: dict[str, dict[str, PredEntry]] = {}
    for mode in modes:
        mode_dir = sweep_dir / f"{mode}_no_evidence"
        pred_path = mode_dir / "predictions.json"
        if not pred_path.is_file():
            print(f"  [WARN] Missing: {pred_path}", file=sys.stderr)
            continue
        mode_preds[mode] = load_predictions(pred_path)
    return cases, mode_preds


# ---------------------------------------------------------------------------
# Per-case metric helpers
# ---------------------------------------------------------------------------

def is_correct_top1(pred: PredEntry | None, case: Case) -> bool:
    """Parent-code match with F32/F33 grouping."""
    if pred is None or pred.pred_parent is None:
        return False
    gp = case.gold_primary_parent
    if gp is None:
        return False
    if gp in F32_GROUP:
        return pred.pred_parent in F32_GROUP
    return pred.pred_parent == gp


def is_f41_case(case: Case) -> bool:
    return case.gold_primary_parent == "F41"


def is_f32_case(case: Case) -> bool:
    return case.gold_primary_parent in F32_GROUP


def is_f41_correct(pred: PredEntry | None, case: Case) -> bool:
    return is_correct_top1(pred, case) if is_f41_case(case) else False


def is_f32_correct(pred: PredEntry | None, case: Case) -> bool:
    return is_correct_top1(pred, case) if is_f32_case(case) else False


# ---------------------------------------------------------------------------
# Bootstrap infrastructure
# ---------------------------------------------------------------------------

rng = np.random.default_rng(SEED)


def bootstrap_ci(
    data: np.ndarray,
    stat_fn: Callable[[np.ndarray], float],
    B: int = B,
    alpha: float = ALPHA,
) -> tuple[float, float, float]:
    """Percentile bootstrap CI.

    Returns:
        (point_estimate, lower_ci, upper_ci)
    """
    n = len(data)
    point = stat_fn(data)
    boot_stats = np.empty(B)
    for i in range(B):
        idx = rng.integers(0, n, size=n)
        boot_stats[i] = stat_fn(data[idx])
    lo = np.percentile(boot_stats, 100 * alpha / 2)
    hi = np.percentile(boot_stats, 100 * (1 - alpha / 2))
    return float(point), float(lo), float(hi)


def bootstrap_paired_delta(
    flags_a: np.ndarray,
    flags_b: np.ndarray,
    B: int = B,
    alpha: float = ALPHA,
) -> tuple[float, float, float]:
    """Bootstrap CI for mean(a - b) on paired per-case binary data."""
    assert len(flags_a) == len(flags_b)
    delta = flags_a.astype(float) - flags_b.astype(float)
    return bootstrap_ci(delta, np.mean, B=B, alpha=alpha)


# ---------------------------------------------------------------------------
# Metric stat functions (operate on subsets of a data matrix)
# ---------------------------------------------------------------------------

def accuracy_stat(correct_flags: np.ndarray) -> float:
    return float(correct_flags.mean())


def recall_stat(hits: np.ndarray, support_mask: np.ndarray | None = None) -> float:
    """hits is a 0/1 array where 1 = hit for a POSITIVE case.

    For recall we only consider rows where support_mask == 1.
    We bundle the mask in via a 2-column matrix: col0=hit, col1=support.
    """
    if support_mask is None:
        n = len(hits)
        return float(hits.sum() / n) if n > 0 else float("nan")
    # hits is only passed for positive cases; support_mask is always 1 here
    return float(hits.mean()) if len(hits) > 0 else float("nan")


def macro_f1_stat(pred_labels: np.ndarray, gold_labels: np.ndarray) -> float:
    return float(f1_score(gold_labels, pred_labels, average="macro", zero_division=0))


def ece_stat(confs: np.ndarray, corrects: np.ndarray, n_bins: int = N_BINS_ECE) -> float:
    """Expected Calibration Error (ECE) using equal-width bins."""
    n = len(confs)
    if n == 0:
        return float("nan")
    bin_width = 1.0 / n_bins
    weighted_error = 0.0
    for i in range(n_bins):
        lo = i * bin_width
        hi = (i + 1) * bin_width
        if i < n_bins - 1:
            mask = (confs >= lo) & (confs < hi)
        else:
            mask = (confs >= lo) & (confs <= hi)
        if mask.sum() == 0:
            continue
        avg_conf = confs[mask].mean()
        avg_acc = corrects[mask].mean()
        weighted_error += mask.sum() * abs(avg_acc - avg_conf)
    return float(weighted_error / n)


# ---------------------------------------------------------------------------
# Per-mode CI computation
# ---------------------------------------------------------------------------

@dataclass
class ModeCI:
    dataset: str
    mode: str
    n: int
    # Top-1 accuracy
    top1_pt: float
    top1_lo: float
    top1_hi: float
    # F41 recall
    f41_recall_pt: float
    f41_recall_lo: float
    f41_recall_hi: float
    f41_n: int
    # F32 recall
    f32_recall_pt: float
    f32_recall_lo: float
    f32_recall_hi: float
    f32_n: int
    # Macro F1
    macro_f1_pt: float
    macro_f1_lo: float
    macro_f1_hi: float
    # ECE
    ece_pt: float
    ece_lo: float
    ece_hi: float
    # Correctness per case (for delta computation)
    correct_flags: np.ndarray
    # Case ordering
    case_ids: list[str]


def compute_mode_ci(
    dataset_label: str,
    mode: str,
    cases: dict[str, Case],
    preds: dict[str, PredEntry],
    case_id_order: list[str],
) -> ModeCI:
    """Compute all bootstrap CIs for a single mode x dataset."""
    n = len(case_id_order)

    # --- Build per-case arrays -------------------------------------------
    correct = np.zeros(n, dtype=float)
    pred_labels = []
    gold_labels = []
    f41_hits = []
    f32_hits = []
    # For ECE: only non-abstaining predictions
    ece_confs = []
    ece_corrects = []

    for i, cid in enumerate(case_id_order):
        case = cases[cid]
        pred = preds.get(cid)
        gp = case.gold_primary_parent

        c1 = is_correct_top1(pred, case)
        correct[i] = float(c1)

        pp = pred.pred_parent if pred is not None else None
        pred_labels.append(pp if pp is not None else "ABSTAIN")
        gold_labels.append(gp if gp is not None else "UNK")

        if gp in F32_GROUP:
            f32_hits.append(float(c1))
        if gp == "F41":
            f41_hits.append(float(c1))

        # ECE: skip abstentions and missing confidence
        if pred is not None and pred.pred_parent is not None and pred.confidence is not None:
            ece_confs.append(pred.confidence)
            ece_corrects.append(float(c1))

    f41_hits_arr = np.array(f41_hits, dtype=float)
    f32_hits_arr = np.array(f32_hits, dtype=float)
    ece_confs_arr = np.array(ece_confs, dtype=float)
    ece_corrects_arr = np.array(ece_corrects, dtype=float)
    pred_arr = np.array(pred_labels)
    gold_arr = np.array(gold_labels)

    # --- Top-1 accuracy bootstrap ----------------------------------------
    top1_pt, top1_lo, top1_hi = bootstrap_ci(correct, accuracy_stat)

    # --- F41 recall bootstrap --------------------------------------------
    if len(f41_hits_arr) > 0:
        f41_pt, f41_lo, f41_hi = bootstrap_ci(f41_hits_arr, accuracy_stat)
    else:
        f41_pt = f41_lo = f41_hi = float("nan")

    # --- F32 recall bootstrap --------------------------------------------
    if len(f32_hits_arr) > 0:
        f32_pt, f32_lo, f32_hi = bootstrap_ci(f32_hits_arr, accuracy_stat)
    else:
        f32_pt = f32_lo = f32_hi = float("nan")

    # --- Macro F1 bootstrap -----------------------------------------------
    # Bootstrap must resample jointly over (pred_labels, gold_labels)
    combined = np.stack([pred_arr, gold_arr], axis=1)  # shape (n, 2) of object

    def macro_f1_from_combined(mat: np.ndarray) -> float:
        return macro_f1_stat(mat[:, 0], mat[:, 1])

    macro_pt, macro_lo, macro_hi = bootstrap_ci(combined, macro_f1_from_combined)

    # --- ECE bootstrap ---------------------------------------------------
    if len(ece_confs_arr) > 1:
        ece_combined = np.stack([ece_confs_arr, ece_corrects_arr], axis=1)

        def ece_from_combined(mat: np.ndarray) -> float:
            return ece_stat(mat[:, 0], mat[:, 1])

        ece_pt, ece_lo, ece_hi = bootstrap_ci(ece_combined, ece_from_combined)
    else:
        ece_pt = ece_lo = ece_hi = float("nan")

    return ModeCI(
        dataset=dataset_label,
        mode=mode,
        n=n,
        top1_pt=top1_pt, top1_lo=top1_lo, top1_hi=top1_hi,
        f41_recall_pt=f41_pt, f41_recall_lo=f41_lo, f41_recall_hi=f41_hi,
        f41_n=len(f41_hits_arr),
        f32_recall_pt=f32_pt, f32_recall_lo=f32_lo, f32_recall_hi=f32_hi,
        f32_n=len(f32_hits_arr),
        macro_f1_pt=macro_pt, macro_f1_lo=macro_lo, macro_f1_hi=macro_hi,
        ece_pt=ece_pt, ece_lo=ece_lo, ece_hi=ece_hi,
        correct_flags=correct,
        case_ids=case_id_order,
    )


# ---------------------------------------------------------------------------
# HiED-Primary Ensemble (HiED + Single fallback on abstain)
# ---------------------------------------------------------------------------

def compute_ensemble_ci(
    cases: dict[str, Case],
    hied_preds: dict[str, PredEntry],
    single_preds: dict[str, PredEntry],
    case_id_order: list[str],
    dataset_label: str,
) -> ModeCI:
    """HiED primary, Single fallback when HiED abstains."""
    n = len(case_id_order)
    correct = np.zeros(n, dtype=float)
    pred_labels = []
    gold_labels = []
    f41_hits = []
    f32_hits = []
    ece_confs = []
    ece_corrects = []

    for i, cid in enumerate(case_id_order):
        case = cases[cid]
        gp = case.gold_primary_parent
        hied = hied_preds.get(cid)
        single = single_preds.get(cid)

        # Ensemble: prefer HiED if it didn't abstain, else use Single
        if hied is not None and hied.pred_parent is not None:
            pred = hied
        else:
            pred = single

        c1 = is_correct_top1(pred, case)
        correct[i] = float(c1)
        pp = pred.pred_parent if pred is not None else None
        pred_labels.append(pp if pp is not None else "ABSTAIN")
        gold_labels.append(gp if gp is not None else "UNK")

        if gp in F32_GROUP:
            f32_hits.append(float(c1))
        if gp == "F41":
            f41_hits.append(float(c1))

        # Confidence from the chosen predictor
        if pred is not None and pred.pred_parent is not None and pred.confidence is not None:
            ece_confs.append(pred.confidence)
            ece_corrects.append(float(c1))

    f41_hits_arr = np.array(f41_hits, dtype=float)
    f32_hits_arr = np.array(f32_hits, dtype=float)
    ece_confs_arr = np.array(ece_confs, dtype=float)
    ece_corrects_arr = np.array(ece_corrects, dtype=float)
    pred_arr = np.array(pred_labels)
    gold_arr = np.array(gold_labels)

    top1_pt, top1_lo, top1_hi = bootstrap_ci(correct, accuracy_stat)

    f41_pt, f41_lo, f41_hi = (
        bootstrap_ci(f41_hits_arr, accuracy_stat) if len(f41_hits_arr) > 0
        else (float("nan"),) * 3
    )
    f32_pt, f32_lo, f32_hi = (
        bootstrap_ci(f32_hits_arr, accuracy_stat) if len(f32_hits_arr) > 0
        else (float("nan"),) * 3
    )

    combined = np.stack([pred_arr, gold_arr], axis=1)

    def macro_f1_from_combined(mat: np.ndarray) -> float:
        return macro_f1_stat(mat[:, 0], mat[:, 1])

    macro_pt, macro_lo, macro_hi = bootstrap_ci(combined, macro_f1_from_combined)

    if len(ece_confs_arr) > 1:
        ece_combined = np.stack([ece_confs_arr, ece_corrects_arr], axis=1)

        def ece_from_combined(mat: np.ndarray) -> float:
            return ece_stat(mat[:, 0], mat[:, 1])

        ece_pt, ece_lo, ece_hi = bootstrap_ci(ece_combined, ece_from_combined)
    else:
        ece_pt = ece_lo = ece_hi = float("nan")

    return ModeCI(
        dataset=dataset_label,
        mode="hied_ensemble",
        n=n,
        top1_pt=top1_pt, top1_lo=top1_lo, top1_hi=top1_hi,
        f41_recall_pt=f41_pt, f41_recall_lo=f41_lo, f41_recall_hi=f41_hi,
        f41_n=len(f41_hits_arr),
        f32_recall_pt=f32_pt, f32_recall_lo=f32_lo, f32_recall_hi=f32_hi,
        f32_n=len(f32_hits_arr),
        macro_f1_pt=macro_pt, macro_f1_lo=macro_lo, macro_f1_hi=macro_hi,
        ece_pt=ece_pt, ece_lo=ece_lo, ece_hi=ece_hi,
        correct_flags=correct,
        case_ids=case_id_order,
    )


# ---------------------------------------------------------------------------
# Delta CI (V10 vs baseline, paired)
# ---------------------------------------------------------------------------

@dataclass
class DeltaCI:
    dataset: str
    mode: str
    delta_pt: float
    delta_lo: float
    delta_hi: float
    n_baseline: int
    n_v10: int


def compute_delta_ci(
    baseline_ci: ModeCI,
    v10_ci: ModeCI,
) -> DeltaCI:
    """Paired per-case delta = V10_correct - baseline_correct."""
    assert baseline_ci.case_ids == v10_ci.case_ids, (
        f"Case ID mismatch: {baseline_ci.dataset}/{baseline_ci.mode}"
    )
    delta_pt, delta_lo, delta_hi = bootstrap_paired_delta(
        v10_ci.correct_flags, baseline_ci.correct_flags
    )
    return DeltaCI(
        dataset=baseline_ci.dataset,
        mode=baseline_ci.mode,
        delta_pt=delta_pt,
        delta_lo=delta_lo,
        delta_hi=delta_hi,
        n_baseline=baseline_ci.n,
        n_v10=v10_ci.n,
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_pct(v: float) -> str:
    if np.isnan(v):
        return "—"
    return f"{v * 100:.1f}%"


def fmt_ci_pct(pt: float, lo: float, hi: float) -> str:
    if np.isnan(pt):
        return "—"
    return f"{pt * 100:.1f}% [{lo * 100:.1f}%, {hi * 100:.1f}%]"


def fmt_ci_delta_pct(pt: float, lo: float, hi: float) -> str:
    if np.isnan(pt):
        return "—"
    sign = "+" if pt >= 0 else ""
    return f"{sign}{pt * 100:.1f}% [{sign}{lo * 100:.1f}%, {'+' if hi >= 0 else ''}{hi * 100:.1f}%]"


def fmt_ci_f1(pt: float, lo: float, hi: float) -> str:
    if np.isnan(pt):
        return "—"
    return f"{pt:.3f} [{lo:.3f}, {hi:.3f}]"


def fmt_ci_ece(pt: float, lo: float, hi: float) -> str:
    if np.isnan(pt):
        return "—"
    return f"{pt:.3f} [{lo:.3f}, {hi:.3f}]"


def md_table(headers: list[str], rows: list[list[str]], aligns: list[str] | None = None) -> str:
    if aligns is None:
        aligns = ["l"] * len(headers)
    sep_map = {"l": ":---", "r": "---:", "c": ":---:"}
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(sep_map.get(a, ":---") for a in aligns) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 72)
    print("CultureDx Bootstrap CI Computation")
    print(f"  B={B} replicates, seed={SEED}, {int(CI_LEVEL*100)}% CI (percentile method)")
    print("=" * 72)

    output_lines: list[str] = [
        "# CultureDx Bootstrap Confidence Intervals",
        "",
        f"**Bootstrap parameters:** B={B} replicates, seed={SEED}, "
        f"{int(CI_LEVEL*100)}% CI (percentile method)",
        f"**Parent-code matching:** F32 gold matched by F32/F33 predictions.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Load all data
    # -----------------------------------------------------------------------

    print("\n[1/5] Loading data...")

    lingxi_base_dir = SWEEP_DIRS["LingxiDiag_baseline"]
    lingxi_v10_dir  = SWEEP_DIRS["LingxiDiag_v10"]
    mdd5k_base_dir  = SWEEP_DIRS["MDD5k_baseline"]

    # LingxiDiag baseline (3 modes)
    lingxi_base_cases, lingxi_base_modes = load_sweep_modes(
        lingxi_base_dir, ["hied", "psycot", "single"]
    )
    lingxi_base_ids = [c["case_id"] for c in load_json(lingxi_base_dir / "case_list.json")["cases"]]

    # LingxiDiag V10 (2 modes)
    lingxi_v10_cases, lingxi_v10_modes = load_sweep_modes(
        lingxi_v10_dir, ["hied", "psycot"]
    )
    lingxi_v10_ids = [c["case_id"] for c in load_json(lingxi_v10_dir / "case_list.json")["cases"]]

    # MDD-5k baseline (3 modes)
    mdd5k_cases, mdd5k_modes = load_sweep_modes(
        mdd5k_base_dir, ["hied", "psycot", "single"]
    )
    mdd5k_ids = [c["case_id"] for c in load_json(mdd5k_base_dir / "case_list.json")["cases"]]

    print(f"  LingxiDiag baseline: {len(lingxi_base_ids)} cases, "
          f"modes: {list(lingxi_base_modes.keys())}")
    print(f"  LingxiDiag V10:      {len(lingxi_v10_ids)} cases, "
          f"modes: {list(lingxi_v10_modes.keys())}")
    print(f"  MDD-5k baseline:     {len(mdd5k_ids)} cases, "
          f"modes: {list(mdd5k_modes.keys())}")

    # -----------------------------------------------------------------------
    # Compute CIs for all modes
    # -----------------------------------------------------------------------

    print("\n[2/5] Computing bootstrap CIs for baseline modes...")

    all_cis: dict[str, dict[str, ModeCI]] = {
        "LingxiDiag_baseline": {},
        "LingxiDiag_v10":      {},
        "MDD5k_baseline":      {},
    }

    for mode in ["hied", "psycot", "single"]:
        if mode in lingxi_base_modes:
            print(f"  LingxiDiag baseline / {mode}...")
            all_cis["LingxiDiag_baseline"][mode] = compute_mode_ci(
                "LingxiDiag (baseline)", mode,
                lingxi_base_cases, lingxi_base_modes[mode], lingxi_base_ids
            )

    print("\n[3/5] Computing bootstrap CIs for V10 modes...")
    for mode in ["hied", "psycot"]:
        if mode in lingxi_v10_modes:
            print(f"  LingxiDiag V10 / {mode}...")
            all_cis["LingxiDiag_v10"][mode] = compute_mode_ci(
                "LingxiDiag (V10)", mode,
                lingxi_v10_cases, lingxi_v10_modes[mode], lingxi_v10_ids
            )

    for mode in ["hied", "psycot", "single"]:
        if mode in mdd5k_modes:
            print(f"  MDD-5k baseline / {mode}...")
            all_cis["MDD5k_baseline"][mode] = compute_mode_ci(
                "MDD-5k (baseline)", mode,
                mdd5k_cases, mdd5k_modes[mode], mdd5k_ids
            )

    # -----------------------------------------------------------------------
    # HiED-Primary Ensemble (HiED + Single fallback on abstain)
    # -----------------------------------------------------------------------

    print("\n[4/5] Computing HiED-Primary Ensemble CIs...")

    ensemble_cis: dict[str, ModeCI] = {}

    # LingxiDiag baseline ensemble
    if "hied" in lingxi_base_modes and "single" in lingxi_base_modes:
        print("  LingxiDiag baseline ensemble...")
        ensemble_cis["LingxiDiag_baseline"] = compute_ensemble_ci(
            lingxi_base_cases,
            lingxi_base_modes["hied"],
            lingxi_base_modes["single"],
            lingxi_base_ids,
            "LingxiDiag (baseline)",
        )

    # MDD-5k baseline ensemble
    if "hied" in mdd5k_modes and "single" in mdd5k_modes:
        print("  MDD-5k baseline ensemble...")
        ensemble_cis["MDD5k_baseline"] = compute_ensemble_ci(
            mdd5k_cases,
            mdd5k_modes["hied"],
            mdd5k_modes["single"],
            mdd5k_ids,
            "MDD-5k (baseline)",
        )

    # -----------------------------------------------------------------------
    # Delta CIs (V10 vs baseline)
    # -----------------------------------------------------------------------

    print("\n[5/5] Computing paired delta CIs (V10 vs baseline)...")
    delta_cis: list[DeltaCI] = []

    for mode in ["hied", "psycot"]:
        base_ci = all_cis["LingxiDiag_baseline"].get(mode)
        v10_ci  = all_cis["LingxiDiag_v10"].get(mode)
        if base_ci and v10_ci:
            print(f"  LingxiDiag {mode}: V10 vs baseline delta...")
            delta_cis.append(compute_delta_ci(base_ci, v10_ci))

    # -----------------------------------------------------------------------
    # Build output tables
    # -----------------------------------------------------------------------

    print("\n" + "=" * 72)
    print("RESULTS")
    print("=" * 72)

    # === TABLE 1: Main Results (point estimates + CI) ========================

    table1_headers = [
        "Dataset", "Mode", "N",
        "Top-1 Acc [95% CI]",
        "F41 Recall [95% CI]", "F41 n",
        "F32 Recall [95% CI]", "F32 n",
        "Macro F1 [95% CI]",
        "ECE [95% CI]",
    ]
    table1_aligns = ["l", "l", "r", "r", "r", "r", "r", "r", "r", "r"]
    table1_rows = []

    section_order = [
        ("LingxiDiag_baseline", "LingxiDiag (Baseline)", ["hied", "psycot", "single"]),
        ("LingxiDiag_v10",      "LingxiDiag (V10)",      ["hied", "psycot"]),
        ("MDD5k_baseline",      "MDD-5k (Baseline)",     ["hied", "psycot", "single"]),
    ]

    mode_display = {
        "hied":   "HiED",
        "psycot": "PsyCoT",
        "single": "Single",
    }

    for section_key, section_label, modes in section_order:
        for mode in modes:
            ci = all_cis[section_key].get(mode)
            if ci is None:
                continue
            table1_rows.append([
                section_label,
                mode_display.get(mode, mode),
                str(ci.n),
                fmt_ci_pct(ci.top1_pt, ci.top1_lo, ci.top1_hi),
                fmt_ci_pct(ci.f41_recall_pt, ci.f41_recall_lo, ci.f41_recall_hi),
                str(ci.f41_n),
                fmt_ci_pct(ci.f32_recall_pt, ci.f32_recall_lo, ci.f32_recall_hi),
                str(ci.f32_n),
                fmt_ci_f1(ci.macro_f1_pt, ci.macro_f1_lo, ci.macro_f1_hi),
                fmt_ci_ece(ci.ece_pt, ci.ece_lo, ci.ece_hi),
            ])

    # Add ensemble rows
    for ds_key, ds_label in [("LingxiDiag_baseline", "LingxiDiag (Baseline)"),
                              ("MDD5k_baseline", "MDD-5k (Baseline)")]:
        ens = ensemble_cis.get(ds_key)
        if ens:
            table1_rows.append([
                ds_label,
                "HiED+Single (Ensemble)",
                str(ens.n),
                fmt_ci_pct(ens.top1_pt, ens.top1_lo, ens.top1_hi),
                fmt_ci_pct(ens.f41_recall_pt, ens.f41_recall_lo, ens.f41_recall_hi),
                str(ens.f41_n),
                fmt_ci_pct(ens.f32_recall_pt, ens.f32_recall_lo, ens.f32_recall_hi),
                str(ens.f32_n),
                fmt_ci_f1(ens.macro_f1_pt, ens.macro_f1_lo, ens.macro_f1_hi),
                fmt_ci_ece(ens.ece_pt, ens.ece_lo, ens.ece_hi),
            ])

    t1 = md_table(table1_headers, table1_rows, table1_aligns)

    # === TABLE 2: Delta CIs (V10 vs Baseline) ================================

    table2_headers = [
        "Dataset", "Mode",
        "Baseline Top-1", "V10 Top-1",
        "Delta Top-1 [95% CI]",
        "Interpretation",
    ]
    table2_aligns = ["l", "l", "r", "r", "r", "l"]
    table2_rows = []

    for dc in delta_cis:
        base_ci = all_cis["LingxiDiag_baseline"].get(dc.mode)
        v10_ci  = all_cis["LingxiDiag_v10"].get(dc.mode)
        if base_ci is None or v10_ci is None:
            continue
        # Significance: CI excludes 0?
        sig = "Sig." if (dc.delta_lo > 0 or dc.delta_hi < 0) else "n.s."
        direction = "improvement" if dc.delta_pt > 0 else "decline"
        table2_rows.append([
            "LingxiDiag",
            mode_display.get(dc.mode, dc.mode),
            fmt_pct(base_ci.top1_pt),
            fmt_pct(v10_ci.top1_pt),
            fmt_ci_delta_pct(dc.delta_pt, dc.delta_lo, dc.delta_hi),
            f"{sig} ({direction})" if sig == "Sig." else sig,
        ])

    t2 = md_table(table2_headers, table2_rows, table2_aligns)

    # === TABLE 3: ECE Summary ================================================

    table3_headers = [
        "Dataset", "Mode", "N (non-abstain)", "ECE [95% CI]",
    ]
    table3_aligns = ["l", "l", "r", "r"]
    table3_rows = []

    for section_key, section_label, modes in section_order:
        for mode in modes:
            ci = all_cis[section_key].get(mode)
            if ci is None:
                continue
            table3_rows.append([
                section_label,
                mode_display.get(mode, mode),
                "—",  # we'll note it's from non-abstaining preds
                fmt_ci_ece(ci.ece_pt, ci.ece_lo, ci.ece_hi),
            ])
    for ds_key, ds_label in [("LingxiDiag_baseline", "LingxiDiag (Baseline)"),
                              ("MDD5k_baseline", "MDD-5k (Baseline)")]:
        ens = ensemble_cis.get(ds_key)
        if ens:
            table3_rows.append([
                ds_label,
                "HiED+Single (Ensemble)",
                "—",
                fmt_ci_ece(ens.ece_pt, ens.ece_lo, ens.ece_hi),
            ])

    t3 = md_table(table3_headers, table3_rows, table3_aligns)

    # -----------------------------------------------------------------------
    # Print to stdout
    # -----------------------------------------------------------------------

    banner = "=" * 72

    print(f"\n{banner}")
    print("TABLE 1: Main Results with 95% Bootstrap CIs")
    print(f"{banner}\n")
    print(t1)

    print(f"\n{banner}")
    print("TABLE 2: V10 vs Baseline Delta with 95% Bootstrap CIs (LingxiDiag)")
    print(f"{banner}\n")
    print(t2)

    print(f"\n{banner}")
    print("TABLE 3: ECE with 95% Bootstrap CIs")
    print(f"{banner}\n")
    print(t3)

    # -----------------------------------------------------------------------
    # Print verbose summary
    # -----------------------------------------------------------------------

    print(f"\n{banner}")
    print("VERBOSE SUMMARY (point estimates + 95% CI)")
    print(banner)

    def print_ci_row(label: str, pt: float, lo: float, hi: float, pct: bool = True) -> None:
        if np.isnan(pt):
            print(f"  {label}: —")
            return
        if pct:
            print(f"  {label}: {pt*100:.1f}% [95% CI: {lo*100:.1f}%, {hi*100:.1f}%]")
        else:
            print(f"  {label}: {pt:.4f} [95% CI: {lo:.4f}, {hi:.4f}]")

    for section_key, section_label, modes in section_order:
        print(f"\n--- {section_label} ---")
        for mode in modes:
            ci = all_cis[section_key].get(mode)
            if ci is None:
                continue
            print(f"\n  Mode: {mode_display.get(mode, mode)} (N={ci.n})")
            print_ci_row("Top-1 Accuracy", ci.top1_pt, ci.top1_lo, ci.top1_hi)
            print_ci_row(f"F41 Recall (n={ci.f41_n})", ci.f41_recall_pt, ci.f41_recall_lo, ci.f41_recall_hi)
            print_ci_row(f"F32 Recall (n={ci.f32_n})", ci.f32_recall_pt, ci.f32_recall_lo, ci.f32_recall_hi)
            print_ci_row("Macro F1", ci.macro_f1_pt, ci.macro_f1_lo, ci.macro_f1_hi, pct=False)
            print_ci_row("ECE", ci.ece_pt, ci.ece_lo, ci.ece_hi, pct=False)

        ens = ensemble_cis.get(section_key)
        if ens:
            print(f"\n  Mode: HiED+Single Ensemble (N={ens.n})")
            print_ci_row("Top-1 Accuracy", ens.top1_pt, ens.top1_lo, ens.top1_hi)
            print_ci_row(f"F41 Recall (n={ens.f41_n})", ens.f41_recall_pt, ens.f41_recall_lo, ens.f41_recall_hi)
            print_ci_row(f"F32 Recall (n={ens.f32_n})", ens.f32_recall_pt, ens.f32_recall_lo, ens.f32_recall_hi)
            print_ci_row("Macro F1", ens.macro_f1_pt, ens.macro_f1_lo, ens.macro_f1_hi, pct=False)
            print_ci_row("ECE", ens.ece_pt, ens.ece_lo, ens.ece_hi, pct=False)

    print(f"\n--- V10 vs Baseline Deltas (LingxiDiag) ---")
    for dc in delta_cis:
        print(f"\n  Mode: {mode_display.get(dc.mode, dc.mode)}")
        sign = "+" if dc.delta_pt >= 0 else ""
        sig_str = "SIGNIFICANT" if (dc.delta_lo > 0 or dc.delta_hi < 0) else "not significant"
        print(f"  Delta Top-1: {sign}{dc.delta_pt*100:.1f}% "
              f"[95% CI: {'+' if dc.delta_lo >= 0 else ''}{dc.delta_lo*100:.1f}%, "
              f"{'+' if dc.delta_hi >= 0 else ''}{dc.delta_hi*100:.1f}%] — {sig_str}")

    # -----------------------------------------------------------------------
    # Write markdown output file
    # -----------------------------------------------------------------------

    output_lines += [
        "## Table 1: Main Results with 95% Bootstrap CIs",
        "",
        "> Metrics computed on N=200 per dataset. Parent-code matching: "
        "F32 gold is satisfied by F32/F33 predictions. "
        "All CIs use B=10,000 bootstrap replicates, percentile method, seed=42.",
        "",
        t1,
        "",
        "## Table 2: V10 vs Baseline Delta with 95% Bootstrap CIs",
        "",
        "> Delta = V10 top-1 correct rate minus baseline top-1 correct rate, "
        "computed per case (paired bootstrap). Sig. = 95% CI excludes 0.",
        "",
        t2,
        "",
        "## Table 3: ECE with 95% Bootstrap CIs",
        "",
        "> ECE computed on non-abstaining predictions only. "
        "Bootstrap resamples confidence/correctness pairs jointly.",
        "",
        t3,
        "",
        "## Notes",
        "",
        "- **HiED+Single (Ensemble):** HiED primary prediction used; "
        "Single mode prediction substituted when HiED abstains.",
        "- **F32/F33 grouping:** Gold F32 is matched by predicted F32 or F33 "
        "(these are clinically equivalent at the parent-code level in ICD-10-CM).",
        "- **Abstentions:** Treated as incorrect for accuracy; excluded from ECE.",
        "- **Macro F1:** Labels include 'ABSTAIN' for abstaining predictions; "
        "class-averaged including rare labels.",
        "",
    ]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(output_lines), encoding="utf-8")

    print(f"\n{banner}")
    print(f"Output written to: {OUTPUT_PATH}")
    print(banner)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
