"""Pairwise McNemar exact tests for CultureDx final sweep results.

Computes McNemar's exact test on 6 pre-defined condition pairs per dataset,
with Bonferroni correction for multiple comparisons.

Usage:
    uv run python scripts/mcnemar_final.py
    uv run python scripts/mcnemar_final.py --alpha 0.01
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scipy.stats import binomtest

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mcnemar_final")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

SWEEP_DIRS: dict[str, Path] = {
    "LingxiDiag": (
        ROOT / "outputs" / "sweeps"
        / "final_lingxidiag_20260323_131847"
    ),
    "MDD-5k": (
        ROOT / "outputs" / "sweeps"
        / "final_mdd5k_20260324_120113"
    ),
}

# 6 pairwise comparisons (condition_A, condition_B, label)
PAIRS: list[tuple[str, str, str]] = [
    (
        "hied_bge-m3_evidence",
        "hied_no_evidence",
        "Evidence effect",
    ),
    (
        "hied_bge-m3_evidence",
        "hied_bge-m3_no_somatization",
        "Somatization effect",
    ),
    (
        "hied_no_evidence",
        "single_no_evidence",
        "MAS vs Single",
    ),
    (
        "hied_no_evidence",
        "psycot_no_evidence",
        "HiED vs PsyCoT",
    ),
    (
        "hied_bge-m3_evidence",
        "single_bge-m3_evidence",
        "MAS+ev vs Single+ev",
    ),
    (
        "hied_bge-m3_evidence",
        "psycot_bge-m3_evidence",
        "HiED+ev vs PsyCoT+ev",
    ),
]

# Parent-code groupings for matching:
#   Gold F32.x -> predicted F32 or F33 counts as correct.
#   Gold F41.x -> predicted F41 or F41.1 counts as correct.
F32_GROUP: set[str] = {"F32", "F33"}
F41_GROUP: set[str] = {"F41"}

OUTPUT_MD = ROOT / "outputs" / "mcnemar_final.md"
OUTPUT_JSON = ROOT / "outputs" / "mcnemar_final.json"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict[str, Any] | list[Any]:
    """Load JSON file with explicit UTF-8 encoding."""
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def parent_code(code: str | None) -> str | None:
    """Extract ICD-10 parent code: F32.1 -> F32, F41 -> F41, None -> None."""
    return code.split(".", 1)[0] if code else None


@dataclass
class Case:
    """A single gold-standard case."""
    case_id: str
    gold_labels: list[str]
    gold_primary_parent: str | None


@dataclass
class PredEntry:
    """A single prediction entry."""
    case_id: str
    pred_parent: str | None
    decision: str


def load_cases(sweep_dir: Path) -> dict[str, Case]:
    """Load case_list.json and return case_id -> Case mapping."""
    raw = load_json(sweep_dir / "case_list.json")
    cases: dict[str, Case] = {}
    for c in raw["cases"]:
        cid = str(c["case_id"])
        labels = [str(lb) for lb in c.get("diagnoses", [])]
        gp = parent_code(labels[0]) if labels else None
        cases[cid] = Case(
            case_id=cid,
            gold_labels=labels,
            gold_primary_parent=gp,
        )
    return cases


def load_predictions(pred_path: Path) -> dict[str, PredEntry]:
    """Load predictions.json and return case_id -> PredEntry mapping."""
    raw = load_json(pred_path)
    entries: dict[str, PredEntry] = {}
    for e in raw.get("predictions", []):
        cid = str(e["case_id"])
        decision = e.get("decision", "diagnosis")
        primary = e.get("primary_diagnosis")
        if decision == "abstain" or primary is None:
            pred_par = None
        else:
            pred_par = parent_code(primary)
        entries[cid] = PredEntry(
            case_id=cid,
            pred_parent=pred_par,
            decision=decision,
        )
    return entries


def is_correct_top1(pred: PredEntry | None, case: Case) -> bool:
    """Parent-code match with F32/F33 grouping.

    Gold F32.x -> predicted F32 or F33 = correct.
    Gold F41.x -> predicted F41 = correct.
    Otherwise exact parent-code match required.
    Abstain / None = incorrect.
    """
    if pred is None or pred.pred_parent is None:
        return False
    gp = case.gold_primary_parent
    if gp is None:
        return False
    if gp in F32_GROUP:
        return pred.pred_parent in F32_GROUP
    if gp in F41_GROUP:
        return pred.pred_parent in F41_GROUP
    return pred.pred_parent == gp


# ---------------------------------------------------------------------------
# McNemar test
# ---------------------------------------------------------------------------

@dataclass
class McNemarResult:
    """Result of a single pairwise McNemar test."""
    dataset: str
    comparison: str
    cond_a: str
    cond_b: str
    n: int
    a_top1: float
    b_top1: float
    b_disc: int        # A correct, B wrong
    c_disc: int        # A wrong,  B correct
    chi2: float
    p_value: float
    bonf_sig: bool


def mcnemar_exact(
    dataset_label: str,
    comparison_label: str,
    cond_a_name: str,
    cond_b_name: str,
    cases: dict[str, Case],
    preds_a: dict[str, PredEntry],
    preds_b: dict[str, PredEntry],
    case_ids: list[str],
    alpha_corrected: float,
) -> McNemarResult:
    """Run McNemar exact test on a single pair of conditions."""
    n = len(case_ids)
    a_correct_count = 0
    b_correct_count = 0
    b_disc = 0  # A correct, B wrong
    c_disc = 0  # A wrong,  B correct

    for cid in case_ids:
        case = cases[cid]
        pred_a = preds_a.get(cid)
        pred_b = preds_b.get(cid)
        a_ok = is_correct_top1(pred_a, case)
        b_ok = is_correct_top1(pred_b, case)
        if a_ok:
            a_correct_count += 1
        if b_ok:
            b_correct_count += 1
        if a_ok and not b_ok:
            b_disc += 1
        elif not a_ok and b_ok:
            c_disc += 1

    a_top1 = a_correct_count / n if n > 0 else 0.0
    b_top1 = b_correct_count / n if n > 0 else 0.0

    # McNemar chi-squared statistic (with continuity correction)
    total_disc = b_disc + c_disc
    if total_disc > 0:
        chi2_val = (abs(b_disc - c_disc) - 1) ** 2 / total_disc
    else:
        chi2_val = 0.0

    # Exact p-value via binomial test on discordant pairs
    if total_disc > 0:
        p_val = binomtest(b_disc, n=total_disc, p=0.5).pvalue
    else:
        p_val = 1.0

    sig = p_val < alpha_corrected

    return McNemarResult(
        dataset=dataset_label,
        comparison=comparison_label,
        cond_a=cond_a_name,
        cond_b=cond_b_name,
        n=n,
        a_top1=a_top1,
        b_top1=b_top1,
        b_disc=b_disc,
        c_disc=c_disc,
        chi2=chi2_val,
        p_value=p_val,
        bonf_sig=sig,
    )


# ---------------------------------------------------------------------------
# Markdown table helper
# ---------------------------------------------------------------------------

def md_table(
    headers: list[str],
    rows: list[list[str]],
    aligns: list[str] | None = None,
) -> str:
    """Build a Markdown table string."""
    if aligns is None:
        aligns = ["l"] * len(headers)
    sep_map = {"l": ":---", "r": "---:", "c": ":---:"}
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append(
        "| " + " | ".join(sep_map.get(a, ":---") for a in aligns) + " |"
    )
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Pairwise McNemar exact tests for CultureDx final sweep.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Family-wise alpha before Bonferroni correction (default: 0.05).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    n_comparisons = len(PAIRS)
    alpha_corrected = args.alpha / n_comparisons

    logger.info(
        "McNemar exact test: alpha=%.3f, n_comparisons=%d, "
        "alpha_corrected=%.4f",
        args.alpha, n_comparisons, alpha_corrected,
    )

    all_results: list[McNemarResult] = []

    for ds_label, sweep_dir in SWEEP_DIRS.items():
        logger.info("Loading dataset: %s from %s", ds_label, sweep_dir)

        if not sweep_dir.is_dir():
            logger.warning("Sweep directory not found: %s", sweep_dir)
            continue

        cases = load_cases(sweep_dir)
        case_ids = [
            str(c["case_id"])
            for c in load_json(sweep_dir / "case_list.json")["cases"]
        ]
        logger.info("  %d cases loaded", len(case_ids))

        # Pre-load all needed conditions
        conditions: dict[str, dict[str, PredEntry]] = {}
        needed_conds: set[str] = set()
        for cond_a, cond_b, _ in PAIRS:
            needed_conds.add(cond_a)
            needed_conds.add(cond_b)

        for cond in sorted(needed_conds):
            pred_path = sweep_dir / cond / "predictions.json"
            if not pred_path.is_file():
                logger.warning("  Missing: %s", pred_path)
                continue
            conditions[cond] = load_predictions(pred_path)
            logger.info("  Loaded condition: %s (%d predictions)",
                        cond, len(conditions[cond]))

        # Run pairwise tests
        for cond_a, cond_b, label in PAIRS:
            if cond_a not in conditions or cond_b not in conditions:
                logger.warning(
                    "  Skipping %s: missing condition(s)", label,
                )
                continue

            result = mcnemar_exact(
                dataset_label=ds_label,
                comparison_label=label,
                cond_a_name=cond_a,
                cond_b_name=cond_b,
                cases=cases,
                preds_a=conditions[cond_a],
                preds_b=conditions[cond_b],
                case_ids=case_ids,
                alpha_corrected=alpha_corrected,
            )
            all_results.append(result)

            sig_str = "YES" if result.bonf_sig else "no"
            logger.info(
                "  %s | %s: b=%d c=%d chi2=%.2f p=%.4f sig=%s",
                ds_label, label,
                result.b_disc, result.c_disc,
                result.chi2, result.p_value, sig_str,
            )

    # ------------------------------------------------------------------
    # Build output tables
    # ------------------------------------------------------------------

    headers = [
        "Dataset", "Comparison",
        "A_top1", "B_top1",
        "b (A\u2713B\u2717)", "c (A\u2717B\u2713)",
        "\u03c7\u00b2", "p-value", "Bonf. sig",
    ]
    aligns = ["l", "l", "r", "r", "r", "r", "r", "r", "c"]

    rows: list[list[str]] = []
    json_records: list[dict[str, Any]] = []

    for r in all_results:
        sig_mark = "\u2714" if r.bonf_sig else ""
        rows.append([
            r.dataset,
            r.comparison,
            f"{r.a_top1:.1%}",
            f"{r.b_top1:.1%}",
            str(r.b_disc),
            str(r.c_disc),
            f"{r.chi2:.2f}",
            f"{r.p_value:.4f}" if r.p_value >= 0.0001 else f"{r.p_value:.2e}",
            sig_mark,
        ])
        json_records.append({
            "dataset": r.dataset,
            "comparison": r.comparison,
            "cond_a": r.cond_a,
            "cond_b": r.cond_b,
            "n": r.n,
            "a_top1": round(r.a_top1, 4),
            "b_top1": round(r.b_top1, 4),
            "b_disc": r.b_disc,
            "c_disc": r.c_disc,
            "chi2": round(r.chi2, 4),
            "p_value": r.p_value,
            "bonferroni_significant": bool(r.bonf_sig),
        })

    table_str = md_table(headers, rows, aligns)

    # ------------------------------------------------------------------
    # Write markdown
    # ------------------------------------------------------------------

    md_lines = [
        "# McNemar Exact Test Results (Final Sweep)",
        "",
        f"**Family-wise alpha:** {args.alpha}  ",
        f"**Bonferroni-corrected alpha:** {alpha_corrected:.4f} "
        f"({n_comparisons} comparisons)  ",
        "**Parent-code matching:** Gold F32.x matched by F32/F33; "
        "Gold F41.x matched by F41. Abstain = incorrect.",
        "",
        table_str,
        "",
        "## Notes",
        "",
        "- **b (A\u2713B\u2717):** Cases where condition A is correct "
        "and condition B is wrong (discordant favoring A).",
        "- **c (A\u2717B\u2713):** Cases where condition A is wrong "
        "and condition B is correct (discordant favoring B).",
        "- **\u03c7\u00b2:** McNemar chi-squared statistic with "
        "continuity correction: (|b-c|-1)^2 / (b+c).",
        "- **p-value:** Exact two-sided p-value from binomial test "
        "on discordant pairs (H0: b = c).",
        "- **Bonf. sig:** \u2714 if p < alpha_corrected.",
        "",
    ]

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("\n".join(md_lines), encoding="utf-8")
    logger.info("Markdown written to %s", OUTPUT_MD)

    # ------------------------------------------------------------------
    # Write JSON
    # ------------------------------------------------------------------

    json_output = {
        "alpha": args.alpha,
        "alpha_corrected": alpha_corrected,
        "n_comparisons": n_comparisons,
        "results": json_records,
    }
    OUTPUT_JSON.write_text(
        json.dumps(json_output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("JSON written to %s", OUTPUT_JSON)

    # ------------------------------------------------------------------
    # Print table to stdout
    # ------------------------------------------------------------------

    print()
    print("=" * 72)
    print("McNemar Exact Test Results (Final Sweep)")
    print(f"  alpha={args.alpha}, corrected={alpha_corrected:.4f}")
    print("=" * 72)
    print()
    print(table_str)
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
