"""Stage L0 — Failure Taxonomy + Module Oracle Audit
Read-only. Uses existing predictions.jsonl. No GPU, no rerun, no commit.

Per Round 96 §1.1 + §1.2:
  Section 1: Module oracles (best-case Top-1/Top-3 per signal source)
  Section 2: Failure taxonomy A-H per case
  Section 3: Stepwise pipeline degradation
"""
import json, sys, re
from pathlib import Path
sys.path.insert(0, 'src')
from culturedx.eval.lingxidiag_paper import to_paper_parent, gold_to_parent_list, PAPER_12_CLASSES
import numpy as np
from collections import defaultdict, Counter

# ============================================================================
# Load
# ============================================================================
PRED = 'results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl'
cases = []
with open(PRED) as f:
    for line in f: cases.append(json.loads(line))
N = len(cases)
print(f"Stage L0 — Failure Taxonomy + Module Oracles")
print(f"Source: {PRED}  (N={N})\n")

# ============================================================================
# Helpers
# ============================================================================
def _rco(c): return {it['disorder_code']: it for it in (c.get('decision_trace',{}).get('raw_checker_outputs',[]) or [])}
def met_ratio(c): return {k:v.get('met_ratio',0.0) for k,v in _rco(c).items()}
def met_count(c): return {k:v.get('criteria_met_count',0) for k,v in _rco(c).items()}
def confirmed(c): return list(c.get('decision_trace',{}).get('logic_engine_confirmed_codes',[]) or [])
def diag_ranked(c): return c.get('decision_trace',{}).get('diagnostician_ranked',[]) or []

def parent(x): return to_paper_parent(x)
def parent_set(L):
    out = set()
    for code in L:
        p = parent(code)
        if p != 'Others': out.add(p)
    return out

def mean_criterion_conf(c, code):
    rco = _rco(c).get(code)
    if not rco: return 0.0
    pc = rco.get('per_criterion', [])
    if not pc: return 0.0
    return float(np.mean([cr.get('confidence',0.0) for cr in pc]))

# ============================================================================
# §1.2 — Module Oracles
# ============================================================================
print("="*100)
print("§1.2  MODULE ORACLES — best-case Top-1/Top-3 per signal source")
print("="*100)

def rank_by(case, scoring_fn):
    """Return list of disorder codes ranked by scoring_fn (descending)."""
    rco = _rco(case)
    scored = [(code, scoring_fn(case, code)) for code in rco.keys()]
    scored.sort(key=lambda x: -x[1])
    return [code for code, _ in scored]

def to_parent_unique(codes):
    seen, out = set(), []
    for c in codes:
        p = parent(c)
        if p not in seen and p != 'Others':
            seen.add(p); out.append(p)
    return out

def topk_acc(cases, ranking_fn, k=1):
    """For each case, get ranking, parent-collapse, check if gold within top-k."""
    correct = 0
    for c in cases:
        gold = parent_set(c.get('gold_diagnoses', []) or [])
        if not gold: gold = {'Others'}
        ranked = ranking_fn(c)
        parents = to_parent_unique(ranked)[:k]
        if any(p in gold for p in parents):
            correct += 1
    return correct / len(cases)

def union_topk_acc(cases, k=1):
    """Oracle: gold counted as Top-k if it's in any combined source's top-k after parent-collapse."""
    correct = 0
    for c in cases:
        gold = parent_set(c.get('gold_diagnoses', []) or [])
        if not gold: gold = {'Others'}
        # Gather candidates from multiple sources
        sources = []
        # diag ranked
        sources.extend(diag_ranked(c))
        # checker by met_ratio
        mr = met_ratio(c)
        sources.extend(sorted(mr.keys(), key=lambda x: -mr.get(x,0)))
        # confirmed codes
        sources.extend(confirmed(c))
        parents = to_parent_unique(sources)[:k]
        if any(p in gold for p in parents):
            correct += 1
    return correct / len(cases)

# Define ranking functions
def rank_diag(c): return diag_ranked(c)
def rank_met_ratio(c): return rank_by(c, lambda case, code: met_ratio(case).get(code, 0))
def rank_met_count(c): return rank_by(c, lambda case, code: met_count(case).get(code, 0))
def rank_mean_conf(c): return rank_by(c, lambda case, code: mean_criterion_conf(case, code))
def rank_logic_engine(c):
    """Logic engine confirmed_codes is unordered set; treat as fall-back rank by met_ratio."""
    conf = confirmed(c)
    mr = met_ratio(c)
    return sorted(conf, key=lambda x: -mr.get(x,0))

# Compute oracles
sources = [
    ('Final pipeline (current)', lambda c: ([c.get('primary_diagnosis')] +
                                              [x for x in c.get('comorbid_diagnoses',[]) if x] +
                                              [x for x in diag_ranked(c) if x not in [c.get('primary_diagnosis')] + (c.get('comorbid_diagnoses') or [])])),
    ('Diagnostician (DtV ranked)',     rank_diag),
    ('Checker met_ratio top',           rank_met_ratio),
    ('Checker met_count top',           rank_met_count),
    ('Checker mean criterion conf',     rank_mean_conf),
    ('Logic engine confirmed (mr-sort)',rank_logic_engine),
]

print(f"\n{'Source':<40} {'Top-1':>8} {'Top-3':>8} {'Top-5':>8}")
print("-"*70)
for label, fn in sources:
    t1 = topk_acc(cases, fn, 1)
    t3 = topk_acc(cases, fn, 3)
    t5 = topk_acc(cases, fn, 5)
    print(f"{label:<40} {t1:>8.4f} {t3:>8.4f} {t5:>8.4f}")

# Union oracle (best-case across all sources)
print(f"\n{'UNION ORACLE (any source contains gold)':<40} {union_topk_acc(cases,1):>8.4f} {union_topk_acc(cases,3):>8.4f} {union_topk_acc(cases,5):>8.4f}")

# ============================================================================
# §1.1 — Failure Taxonomy
# ============================================================================
print("\n" + "="*100)
print("§1.1  FAILURE TAXONOMY (A-H) — only on Top-1-WRONG cases")
print("="*100)

# Per-case classification (only for cases where final Top-1 is wrong)
taxonomy = defaultdict(int)
taxonomy_examples = defaultdict(list)

# Detailed counts
n_correct_final = 0
total_wrong = 0

for c in cases:
    gold_set = parent_set(c.get('gold_diagnoses', []) or [])
    if not gold_set: gold_set = {'Others'}
    
    primary = parent(c.get('primary_diagnosis'))
    comorbid_p = [parent(x) for x in (c.get('comorbid_diagnoses') or []) if x]
    final_top3 = [primary] + [p for p in comorbid_p if p != primary]
    # Extend with diagnostician ranked
    for p in to_parent_unique(diag_ranked(c)):
        if p not in final_top3 and p != 'Others':
            final_top3.append(p)
    final_top3 = final_top3[:3]
    
    if primary in gold_set:
        n_correct_final += 1
        continue
    total_wrong += 1
    
    # Compute per-source signals
    mr_rank = to_parent_unique(rank_met_ratio(c))
    mc_rank = to_parent_unique(rank_met_count(c))
    conf_rank = to_parent_unique(rank_mean_conf(c))
    diag_rank = to_parent_unique(diag_ranked(c))
    confirmed_parents = parent_set(confirmed(c))
    
    # H: malformed final output
    if primary == 'Others' or primary not in PAPER_12_CLASSES:
        taxonomy['H'] += 1
        if len(taxonomy_examples['H']) < 3:
            taxonomy_examples['H'].append(c.get('case_id'))
        continue
    
    # F: comorbidity gate emitted comorbid that includes gold (gate "removed" gold from primary slot)
    # Specifically: if a comorbid candidate is in gold_set but primary isn't
    if any(cp in gold_set for cp in comorbid_p) and primary not in gold_set:
        taxonomy['F'] += 1
        if len(taxonomy_examples['F']) < 3:
            taxonomy_examples['F'].append(c.get('case_id'))
        continue
    
    # A: checker top code (met_ratio) already correct, final output wrong
    if mr_rank and mr_rank[0] in gold_set:
        taxonomy['A'] += 1
        if len(taxonomy_examples['A']) < 3:
            taxonomy_examples['A'].append(c.get('case_id'))
        continue
    
    # B: checker top-3 contains gold, final top-3 excludes gold
    checker_top3 = mr_rank[:3]
    if any(p in gold_set for p in checker_top3) and not any(p in gold_set for p in final_top3):
        taxonomy['B'] += 1
        if len(taxonomy_examples['B']) < 3:
            taxonomy_examples['B'].append(c.get('case_id'))
        continue
    
    # C: DtV top-1 correct but checker top-1 wrong
    if diag_rank and diag_rank[0] in gold_set:
        # primary_diagnosis came from diag_ranked top-1 typically; if primary != diag_rank[0], something else
        # Actually if diag_rank[0] is correct and primary isn't, then pipeline overrode diag → that's the bug
        if primary != diag_rank[0]:
            taxonomy['C'] += 1
            if len(taxonomy_examples['C']) < 3:
                taxonomy_examples['C'].append(c.get('case_id'))
            continue
    
    # G: gold is in confirmed_set but pipeline didn't pick it as primary
    if any(p in gold_set for p in confirmed_parents):
        taxonomy['G'] += 1
        if len(taxonomy_examples['G']) < 3:
            taxonomy_examples['G'].append(c.get('case_id'))
        continue
    
    # D: checker has correct PARENT but wrong subcode (i.e., primary parent ≠ gold parent BUT raw checker output had subcode that maps to gold)
    rco_parents = set()
    for code in _rco(c).keys():
        rco_parents.add(parent(code))
    if any(p in gold_set for p in rco_parents) and not (mr_rank and mr_rank[0] in gold_set):
        # Actually D is more about subcode mapping — let's defer to a stricter test below
        pass
    
    # E: all sources wrong (no source has gold in any top-rank)
    all_top5_parents = set()
    all_top5_parents.update(to_parent_unique(rank_diag(c))[:5])
    all_top5_parents.update(to_parent_unique(rank_met_ratio(c))[:5])
    all_top5_parents.update(to_parent_unique(rank_logic_engine(c))[:5])
    if not (gold_set & all_top5_parents):
        taxonomy['E'] += 1
        if len(taxonomy_examples['E']) < 3:
            taxonomy_examples['E'].append(c.get('case_id'))
        continue
    
    # Default: type 'Other' / could be re-categorized
    taxonomy['OTHER'] += 1
    if len(taxonomy_examples['OTHER']) < 3:
        taxonomy_examples['OTHER'].append(c.get('case_id'))

print(f"\nTotal cases:              {N}")
print(f"Top-1 correct:            {n_correct_final}  ({n_correct_final/N*100:.1f}%)")
print(f"Top-1 wrong (analyzed):   {total_wrong}  ({total_wrong/N*100:.1f}%)")
print(f"\n{'Type':<6} {'Count':>6} {'% of wrong':>12} {'% of all':>10}  Description")
print("-"*100)
descriptions = {
    'A': 'checker met_ratio top-1 correct, final wrong → logic/calibrator/gate broken',
    'B': 'checker top-3 has gold but final top-3 lost it → reranking/gating issue',
    'C': 'DtV top-1 correct but pipeline overrode it → primary re-selection broke it',
    'D': 'checker correct parent, wrong subcode → mapping issue',
    'E': 'all modules wrong (gold not in any top-5) → upstream prompt/understanding',
    'F': 'gold appears as comorbid (gate moved gold out of primary slot)',
    'G': 'gold in confirmed_set but not picked as primary → primary selection bug',
    'H': 'malformed/non-paper label final output',
    'OTHER': 'other',
}
for tcode in 'ABCDEFGH':
    n = taxonomy.get(tcode, 0)
    print(f"  {tcode:<4} {n:>6} {n/max(total_wrong,1)*100:>11.1f}% {n/N*100:>9.1f}%  {descriptions[tcode]}")
n_other = taxonomy.get('OTHER',0)
print(f"  {'OTHER':<4} {n_other:>6} {n_other/max(total_wrong,1)*100:>11.1f}% {n_other/N*100:>9.1f}%  {descriptions['OTHER']}")

# Examples
print("\n--- Sample case_ids per type (for spot-check) ---")
for k in 'ABCDEFGH':
    if taxonomy_examples.get(k):
        print(f"  Type {k}: {taxonomy_examples[k]}")

# ============================================================================
# §10.4 — Stepwise pipeline degradation: where does signal die?
# ============================================================================
print("\n" + "="*100)
print("§10.4  STEPWISE DEGRADATION — module-by-module Top-1/Top-3 (parent-level)")
print("="*100)

def stepwise_acc(cases, get_codes_fn, k_values=(1,3,5)):
    out = {}
    for k in k_values:
        correct = 0
        for c in cases:
            gold = parent_set(c.get('gold_diagnoses') or [])
            if not gold: gold = {'Others'}
            codes = get_codes_fn(c)
            parents = to_parent_unique(codes)[:k]
            if any(p in gold for p in parents):
                correct += 1
        out[k] = correct / len(cases)
    return out

stages = [
    ('Stage 1: Diagnostician raw ranked',     lambda c: diag_ranked(c)),
    ('Stage 2: Checker met_ratio sorted',      lambda c: rank_met_ratio(c)),
    ('Stage 3: Logic engine confirmed (mr-sorted)', lambda c: rank_logic_engine(c)),
    ('Stage 4: Pipeline final (primary + comorbid + remaining diag)',
     lambda c: ([c.get('primary_diagnosis')] +
                [x for x in (c.get('comorbid_diagnoses') or []) if x] +
                [x for x in diag_ranked(c) if x and x != c.get('primary_diagnosis') and x not in (c.get('comorbid_diagnoses') or [])])),
]

print(f"\n{'Stage':<58} {'Top-1':>8} {'Top-3':>8} {'Top-5':>8}")
print("-"*90)
for label, fn in stages:
    accs = stepwise_acc(cases, fn)
    print(f"{label:<58} {accs[1]:>8.4f} {accs[3]:>8.4f} {accs[5]:>8.4f}")

# Save raw counts
import json as J
from pathlib import Path
_out = Path('results/sandbox/stage_L0_results.json')
_out.parent.mkdir(parents=True, exist_ok=True)
with open(_out, 'w') as f:
    J.dump({
        'taxonomy': dict(taxonomy),
        'taxonomy_examples': {k:list(v) for k,v in taxonomy_examples.items()},
        'n_correct_final': n_correct_final,
        'total_wrong': total_wrong,
        'N': N,
    }, f, indent=2, default=str)
