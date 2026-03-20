"""
V10 HiED LingxiDiag: Criterion-Level Analysis
Compares V10 vs baseline F41.1 (and F32) criterion-level results across:
  - 19 improved cases
  - 8 regressed cases
  - All 200 cases (aggregate)
"""

import json
from pathlib import Path
from collections import defaultdict

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────
ROOT = Path("/home/user/YuNing/CultureDx")
V10_PRED   = ROOT / "outputs/sweeps/v10_lingxidiag_20260320_222603/hied_no_evidence/predictions.json"
BASE_PRED  = ROOT / "outputs/sweeps/lingxidiag_3mode_crossval_20260320_195057/hied_no_evidence/predictions.json"
CASE_LIST  = ROOT / "outputs/sweeps/v10_lingxidiag_20260320_222603/case_list.json"

# ─────────────────────────────────────────────────────────────
# Case groups
# ─────────────────────────────────────────────────────────────
IMPROVED_F41 = [
    "305844910","311492359","322632615","323239137","336543853",
    "337199218","339926146","341022175","354444532","355957248",
    "367540683","372723926","387909562","391244639","394321045",
]
IMPROVED_NON_F41 = {
    "357977169": "F32",
    "374156384": "F32",
    "378910946": "F32,F41",
    "383483096": "F32",
}
IMPROVED_ALL = set(IMPROVED_F41) | set(IMPROVED_NON_F41.keys())

REGRESSED = {
    "302102824": "F32->F41.1",
    "321168499": "F32->ABSTAIN",
    "323134405": "F32->F43.1",
    "339584846": "F41->F32",
    "364898800": "F32->ABSTAIN",
    "366964913": "F32->F42",
    "390898865": "F32->ABSTAIN",
    "398059903": "F32,F41->ABSTAIN",
}

# ─────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────
def load_predictions(path: Path) -> dict:
    """Return {case_id -> prediction_dict}."""
    with open(path) as f:
        data = json.load(f)
    return {str(p["case_id"]): p for p in data["predictions"]}

def load_gold(path: Path) -> dict:
    """Return {case_id -> [diagnoses]}."""
    with open(path) as f:
        data = json.load(f)
    return {str(c["case_id"]): c["diagnoses"] for c in data["cases"]}

print("Loading data …")
v10   = load_predictions(V10_PRED)
base  = load_predictions(BASE_PRED)
gold  = load_gold(CASE_LIST)
print(f"  V10 cases: {len(v10)}   Baseline cases: {len(base)}   Gold cases: {len(gold)}")

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def get_disorder_block(pred: dict, disorder: str) -> dict | None:
    """Extract the criteria_results block for a given disorder code."""
    for block in pred.get("criteria_results", []):
        if block.get("disorder") == disorder:
            return block
    return None

def get_criteria_map(block: dict | None) -> dict:
    """Return {criterion_id -> status} from a disorder block."""
    if block is None:
        return {}
    return {c["criterion_id"]: c["status"] for c in block.get("criteria", [])}

def met_count(block: dict | None) -> int | str:
    if block is None:
        return "N/A (disorder not evaluated)"
    return block.get("criteria_met_count", 0)

def status_symbol(status: str) -> str:
    return {"met": "MET", "not_met": "NOT", "insufficient_evidence": "INS"}.get(status, status)

def diff_criteria(base_map: dict, v10_map: dict) -> list[str]:
    """Return lines describing criteria whose status changed."""
    all_ids = sorted(set(base_map) | set(v10_map))
    lines = []
    for cid in all_ids:
        b = base_map.get(cid, "absent")
        v = v10_map.get(cid, "absent")
        if b != v:
            lines.append(f"      Criterion {cid}: {status_symbol(b):3s} -> {status_symbol(v):3s}")
    return lines

# ─────────────────────────────────────────────────────────────
# ANALYSIS 1: Improved cases — F41.1 criterion comparison
# ─────────────────────────────────────────────────────────────
print()
print("=" * 72)
print("ANALYSIS 1: IMPROVED CASES — F41.1 CRITERION COMPARISON")
print("=" * 72)

def report_case_f411(case_id: str, label: str = ""):
    b_pred = base.get(case_id)
    v_pred = v10.get(case_id)
    gold_dx = gold.get(case_id, ["?"])
    header_suffix = f"  [gold={','.join(gold_dx)}]" + (f"  [{label}]" if label else "")

    print()
    print(f"  Case {case_id}{header_suffix}")

    if b_pred is None or v_pred is None:
        print(f"    WARNING: missing data (base={b_pred is not None}, v10={v_pred is not None})")
        return

    b_block = get_disorder_block(b_pred, "F41.1")
    v_block = get_disorder_block(v_pred, "F41.1")

    b_count = met_count(b_block)
    v_count = met_count(v_block)
    b_map   = get_criteria_map(b_block)
    v_map   = get_criteria_map(v_block)

    b_A = status_symbol(b_map.get("A", "absent"))
    v_A = status_symbol(v_map.get("A", "absent"))
    a_changed = " <-- CHANGED" if b_A != v_A else ""

    print(f"    F41.1 criteria_met: baseline={b_count}  v10={v_count}")
    print(f"    Criterion A:        baseline={b_A}  v10={v_A}{a_changed}")

    changes = diff_criteria(b_map, v_map)
    if changes:
        print(f"    Status changes ({len(changes)} criteria):")
        for line in changes:
            print(line)
    else:
        print(f"    No criterion status changes for F41.1")

    # Show primary diagnosis changes
    b_dx = b_pred.get("primary_diagnosis") or "ABSTAIN"
    v_dx = v_pred.get("primary_diagnosis") or "ABSTAIN"
    if b_dx != v_dx:
        print(f"    Primary Dx:  baseline={b_dx}  ->  v10={v_dx}")
    else:
        print(f"    Primary Dx:  {b_dx} (unchanged)")

print()
print("  --- F41 / F41-related improved cases ---")
for cid in IMPROVED_F41:
    report_case_f411(cid)

print()
print("  --- Non-F41 improved cases (checking if F41.1 criteria also changed) ---")
for cid, lbl in IMPROVED_NON_F41.items():
    report_case_f411(cid, label=f"gold={lbl}")

# ─────────────────────────────────────────────────────────────
# ANALYSIS 2: Regressed cases — F32 and F41.1 criteria
# ─────────────────────────────────────────────────────────────
print()
print("=" * 72)
print("ANALYSIS 2: REGRESSED CASES — F32 AND F41.1 CRITERION COMPARISON")
print("=" * 72)

def report_case_regressed(case_id: str, transition: str):
    b_pred = base.get(case_id)
    v_pred = v10.get(case_id)
    gold_dx = gold.get(case_id, ["?"])

    print()
    print(f"  Case {case_id}  [gold={','.join(gold_dx)}]  [{transition}]")

    if b_pred is None or v_pred is None:
        print(f"    WARNING: missing data (base={b_pred is not None}, v10={v_pred is not None})")
        return

    b_primary = b_pred.get("primary_diagnosis", "?")
    v_primary = v_pred.get("primary_diagnosis", "?")
    print(f"    Primary Dx:  baseline={b_primary}  ->  v10={v_primary}")

    for disorder in ["F32", "F41.1"]:
        b_block = get_disorder_block(b_pred, disorder)
        v_block = get_disorder_block(v_pred, disorder)
        b_count = met_count(b_block)
        v_count = met_count(v_block)
        b_map   = get_criteria_map(b_block)
        v_map   = get_criteria_map(v_block)

        changes = diff_criteria(b_map, v_map)
        b_A = status_symbol(b_map.get("A", "absent"))
        v_A = status_symbol(v_map.get("A", "absent"))

        print(f"    [{disorder}] criteria_met: baseline={b_count}  v10={v_count}  |  CritA: {b_A}->{v_A}")
        if changes:
            for line in changes:
                print(line)
        else:
            print(f"      (no {disorder} criterion changes)")

for cid, transition in REGRESSED.items():
    report_case_regressed(cid, transition)

# ─────────────────────────────────────────────────────────────
# ANALYSIS 3: Aggregate F41.1 criterion statistics across 200 cases
# ─────────────────────────────────────────────────────────────
print()
print("=" * 72)
print("ANALYSIS 3: AGGREGATE F41.1 CRITERION STATISTICS — ALL 200 CASES")
print("=" * 72)

F411_CRITERIA = ["A", "B1", "B2", "B3", "B4"]

base_crit_counts = defaultdict(lambda: {"met": 0, "not_met": 0, "insufficient_evidence": 0, "absent": 0})
v10_crit_counts  = defaultdict(lambda: {"met": 0, "not_met": 0, "insufficient_evidence": 0, "absent": 0})
base_met_totals  = []
v10_met_totals   = []

all_case_ids = set(base.keys()) | set(v10.keys())
n_both = 0

for cid in all_case_ids:
    b_pred = base.get(cid)
    v_pred = v10.get(cid)
    if b_pred is None or v_pred is None:
        continue
    n_both += 1

    b_block = get_disorder_block(b_pred, "F41.1")
    v_block = get_disorder_block(v_pred, "F41.1")

    # Met counts
    if b_block is not None:
        base_met_totals.append(b_block.get("criteria_met_count", 0))
    if v_block is not None:
        v10_met_totals.append(v_block.get("criteria_met_count", 0))

    b_map = get_criteria_map(b_block)
    v_map = get_criteria_map(v_block)

    for crit in F411_CRITERIA:
        base_crit_counts[crit][b_map.get(crit, "absent")] += 1
        v10_crit_counts[crit][v_map.get(crit, "absent")]  += 1

print(f"\n  Cases with data in both runs: {n_both}")
print(f"\n  Mean F41.1 criteria_met_count:")
print(f"    Baseline: {sum(base_met_totals)/len(base_met_totals):.3f}  (n={len(base_met_totals)})")
print(f"    V10:      {sum(v10_met_totals)/len(v10_met_totals):.3f}  (n={len(v10_met_totals)})")

print()
print(f"  {'Criterion':<12} {'':>2}  {'Baseline MET':>12}  {'V10 MET':>7}  {'Delta':>6}  "
      f"{'Base NOT':>8}  {'V10 NOT':>7}  {'Base INS':>8}  {'V10 INS':>7}")
print(f"  {'-'*85}")

for crit in F411_CRITERIA:
    b = base_crit_counts[crit]
    v = v10_crit_counts[crit]
    delta = v["met"] - b["met"]
    delta_str = f"+{delta}" if delta > 0 else str(delta)
    print(f"  {crit:<12}  {'':>2}  {b['met']:>12}  {v['met']:>7}  {delta_str:>6}  "
          f"{b['not_met']:>8}  {v['not_met']:>7}  {b['insufficient_evidence']:>8}  {v['insufficient_evidence']:>7}")

# Detailed breakdown: how many cases flipped A: not_met->met vs met->not_met
print()
print("  F41.1 Criterion A transition breakdown (across all 200 cases):")
a_transitions = defaultdict(int)
for cid in all_case_ids:
    b_pred = base.get(cid)
    v_pred = v10.get(cid)
    if b_pred is None or v_pred is None:
        continue
    b_block = get_disorder_block(b_pred, "F41.1")
    v_block = get_disorder_block(v_pred, "F41.1")
    b_map = get_criteria_map(b_block)
    v_map = get_criteria_map(v_block)
    b_A = b_map.get("A", "absent")
    v_A = v_map.get("A", "absent")
    a_transitions[(b_A, v_A)] += 1

for (b_A, v_A), count in sorted(a_transitions.items(), key=lambda x: -x[1]):
    arrow = " <-- IMPROVED" if b_A != "met" and v_A == "met" else \
            " <-- REGRESSED" if b_A == "met" and v_A != "met" else ""
    print(f"    {status_symbol(b_A):3s} -> {status_symbol(v_A):3s} : {count:4d} cases{arrow}")

# ─────────────────────────────────────────────────────────────
# BONUS: Summary table for improved cases — did A criterion drive the improvement?
# ─────────────────────────────────────────────────────────────
print()
print("=" * 72)
print("BONUS: IMPROVED F41 CASES — CRITERION A SUMMARY TABLE")
print("=" * 72)
print()
print(f"  {'Case ID':<14} {'Gold':<12} {'Base A':>6}  {'V10 A':>5}  {'Base Met':>8}  {'V10 Met':>7}  {'Base PrimaryDx':<15}  V10 PrimaryDx")
print(f"  {'-'*90}")
for cid in IMPROVED_F41:
    b_pred = base.get(cid)
    v_pred = v10.get(cid)
    if b_pred is None or v_pred is None:
        print(f"  {cid:<14}  MISSING")
        continue
    gold_dx = ",".join(gold.get(cid, ["?"]))
    b_block = get_disorder_block(b_pred, "F41.1")
    v_block = get_disorder_block(v_pred, "F41.1")
    b_map = get_criteria_map(b_block)
    v_map = get_criteria_map(v_block)
    b_A = status_symbol(b_map.get("A", "absent"))
    v_A = status_symbol(v_map.get("A", "absent"))
    b_cnt = met_count(b_block)
    v_cnt = met_count(v_block)
    b_dx = b_pred.get("primary_diagnosis") or "ABSTAIN"
    v_dx = v_pred.get("primary_diagnosis") or "ABSTAIN"
    flag = " **" if b_A != "met" and v_A == "met" else ""
    print(f"  {cid:<14} {gold_dx:<12} {b_A:>6}  {v_A:>5}  {str(b_cnt):>8}  {str(v_cnt):>7}  {b_dx:<15}  {v_dx}{flag}")

print()
print("  ** = Criterion A newly MET in V10")

print()
print("=" * 72)
print("ANALYSIS COMPLETE")
print("=" * 72)
