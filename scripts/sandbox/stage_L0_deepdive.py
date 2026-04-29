"""L0 deep-dive — investigate the largest failure categories."""
import json, sys
sys.path.insert(0, 'src')
from culturedx.eval.lingxidiag_paper import to_paper_parent
import numpy as np
from collections import defaultdict, Counter

cases = []
with open('results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl') as f:
    for line in f: cases.append(json.loads(line))

def _rco(c): return {it['disorder_code']: it for it in (c.get('decision_trace',{}).get('raw_checker_outputs',[]) or [])}
def met_ratio(c): return {k:v.get('met_ratio',0.0) for k,v in _rco(c).items()}
def confirmed(c): return list(c.get('decision_trace',{}).get('logic_engine_confirmed_codes',[]) or [])
def diag_ranked(c): return c.get('decision_trace',{}).get('diagnostician_ranked',[]) or []
def parent(x): return to_paper_parent(x)
def parent_set(L):
    out = set()
    for code in L:
        p = parent(code)
        if p != 'Others': out.add(p)
    return out
def to_parent_unique(codes):
    seen, out = set(), []
    for c in codes:
        p = parent(c)
        if p not in seen and p != 'Others':
            seen.add(p); out.append(p)
    return out

# ============================================================================
# Verification 1: Does diagnostician top-1 == primary_diagnosis?
# ============================================================================
print("="*100)
print("Verification 1: Is primary_diagnosis always == diagnostician top-1?")
print("="*100)
mismatches = 0
diag_top1_correct = 0
primary_correct = 0
for c in cases:
    gold = parent_set(c.get('gold_diagnoses') or [])
    if not gold: gold = {'Others'}
    diag = diag_ranked(c)
    primary = c.get('primary_diagnosis')
    if diag and parent(diag[0]) != parent(primary):
        mismatches += 1
    if diag and parent(diag[0]) in gold:
        diag_top1_correct += 1
    if parent(primary) in gold:
        primary_correct += 1
print(f"  primary_diagnosis ≠ diagnostician_top1: {mismatches}/{len(cases)}")
print(f"  diagnostician_top1 correct (parent):    {diag_top1_correct}/{len(cases)} = {diag_top1_correct/len(cases):.4f}")
print(f"  primary_diagnosis correct (parent):     {primary_correct}/{len(cases)} = {primary_correct/len(cases):.4f}")
print(f"  → These differ by {abs(diag_top1_correct - primary_correct)} cases.")
print(f"  → So primary IS sometimes overridden away from diagnostician top-1.")
print()

# Find the 17 cases where primary differs from diag top-1
print("Cases where primary != diag top-1:")
diff_cases = []
for c in cases:
    diag = diag_ranked(c)
    primary = c.get('primary_diagnosis')
    if diag and parent(diag[0]) != parent(primary):
        gold = parent_set(c.get('gold_diagnoses') or [])
        diff_cases.append({
            'case_id': c.get('case_id'),
            'gold': gold,
            'diag_top1': parent(diag[0]),
            'primary': parent(primary),
            'diag_top1_in_gold': parent(diag[0]) in gold,
            'primary_in_gold': parent(primary) in gold,
        })
print(f"  Total: {len(diff_cases)} cases")
print(f"  diag_top1 correct, primary wrong:  {sum(1 for d in diff_cases if d['diag_top1_in_gold'] and not d['primary_in_gold'])}")
print(f"  diag_top1 wrong, primary correct:  {sum(1 for d in diff_cases if not d['diag_top1_in_gold'] and d['primary_in_gold'])}")
print(f"  both correct:                       {sum(1 for d in diff_cases if d['diag_top1_in_gold'] and d['primary_in_gold'])}")
print(f"  both wrong:                         {sum(1 for d in diff_cases if not d['diag_top1_in_gold'] and not d['primary_in_gold'])}")

# ============================================================================
# Verification 2: Type F deep dive — does comorbid have higher signal than primary?
# ============================================================================
print("\n" + "="*100)
print("Type F deep-dive (137 cases): comorbid contains gold, primary doesn't")
print("="*100)

f_cases = []
for c in cases:
    gold = parent_set(c.get('gold_diagnoses') or [])
    if not gold: gold = {'Others'}
    primary_p = parent(c.get('primary_diagnosis'))
    comorbid_p = [parent(x) for x in (c.get('comorbid_diagnoses') or []) if x]
    if any(cp in gold for cp in comorbid_p) and primary_p not in gold:
        f_cases.append(c)

print(f"  Confirmed Type F count: {len(f_cases)}")

# Of Type F cases: does the gold-comorbid have higher met_ratio than primary?
mr_higher = mr_lower = mr_equal = 0
mr_diffs = []
for c in f_cases:
    gold = parent_set(c.get('gold_diagnoses') or [])
    primary = c.get('primary_diagnosis')
    primary_mr = met_ratio(c).get(primary, 0)
    # Find the gold comorbid
    for code in (c.get('comorbid_diagnoses') or []):
        if parent(code) in gold:
            cm_mr = met_ratio(c).get(code, 0)
            d = cm_mr - primary_mr
            mr_diffs.append(d)
            if d > 0.01: mr_higher += 1
            elif d < -0.01: mr_lower += 1
            else: mr_equal += 1
            break
print(f"\n  Among Type F cases, comparing met_ratio of gold-comorbid vs primary:")
print(f"    gold-comorbid has HIGHER met_ratio: {mr_higher}")
print(f"    gold-comorbid has LOWER  met_ratio: {mr_lower}")
print(f"    equal:                              {mr_equal}")
print(f"    mean diff:                          {np.mean(mr_diffs):+.4f}")
print(f"    median diff:                        {np.median(mr_diffs):+.4f}")
print(f"  → If most are EQUAL (both 1.0), met_ratio can't tie-break them.")

# ============================================================================
# Verification 3: Type G — gold in confirmed_set but not primary
# ============================================================================
print("\n" + "="*100)
print("Type G deep-dive (131 cases): gold in logic_engine_confirmed but not picked as primary")
print("="*100)

g_cases = []
for c in cases:
    gold = parent_set(c.get('gold_diagnoses') or [])
    if not gold: gold = {'Others'}
    primary_p = parent(c.get('primary_diagnosis'))
    comorbid_p = [parent(x) for x in (c.get('comorbid_diagnoses') or []) if x]
    confirmed_parents = parent_set(confirmed(c))
    # Already filter out F (gold in comorbid), A/B (checker top-1/3 has gold)
    final_top3 = [primary_p] + [p for p in comorbid_p if p != primary_p]
    for p in to_parent_unique(diag_ranked(c)):
        if p not in final_top3:
            final_top3.append(p)
    final_top3 = final_top3[:3]
    
    if primary_p in gold: continue
    # F filter
    if any(cp in gold for cp in comorbid_p): continue
    # Type G strictly
    if any(p in gold for p in confirmed_parents):
        g_cases.append(c)

print(f"  Confirmed Type G count: {len(g_cases)}")

# Where in diagnostician's ranking is the gold?
diag_rank_pos = []
for c in g_cases:
    gold = parent_set(c.get('gold_diagnoses') or [])
    diag = to_parent_unique(diag_ranked(c))
    pos = -1
    for i, p in enumerate(diag):
        if p in gold:
            pos = i + 1; break
    diag_rank_pos.append(pos)

print(f"\n  In Type G cases, position of gold in diag_ranked (parent-collapsed):")
ctr = Counter(diag_rank_pos)
for pos in sorted(ctr.keys()):
    print(f"    rank {pos}: {ctr[pos]} cases" if pos > 0 else f"    not in diag top-5: {ctr[pos]} cases")
print(f"  → If gold is rank-2/3/4/5 in diag, switching to that rank could fix.")

# Check met_ratio of gold-in-confirmed vs primary in Type G
mr_diffs_g = []
for c in g_cases:
    gold = parent_set(c.get('gold_diagnoses') or [])
    primary = c.get('primary_diagnosis')
    primary_mr = met_ratio(c).get(primary, 0)
    # Find gold code in confirmed
    for code in confirmed(c):
        if parent(code) in gold:
            mr_diffs_g.append(met_ratio(c).get(code, 0) - primary_mr)
            break

print(f"\n  Type G: met_ratio of gold-confirmed vs primary:")
print(f"    mean diff:   {np.mean(mr_diffs_g):+.4f}")
print(f"    median diff: {np.median(mr_diffs_g):+.4f}")
print(f"    higher: {sum(1 for d in mr_diffs_g if d > 0.01)}")
print(f"    lower:  {sum(1 for d in mr_diffs_g if d < -0.01)}")
print(f"    equal:  {sum(1 for d in mr_diffs_g if abs(d) <= 0.01)}")

# ============================================================================
# Verification 4: How often does diag_top1 = primary EXACTLY?
# ============================================================================
print("\n" + "="*100)
print("Pipeline behavior check: where does primary come from?")
print("="*100)
matches = 0
for c in cases:
    diag = diag_ranked(c)
    primary = c.get('primary_diagnosis')
    if diag and diag[0] == primary:
        matches += 1
print(f"  primary_diagnosis == diagnostician_ranked[0] (exact match): {matches}/{len(cases)} = {matches/len(cases)*100:.1f}%")
print(f"  → so {len(cases)-matches} cases have primary != diag_top1 (raw code level)")
