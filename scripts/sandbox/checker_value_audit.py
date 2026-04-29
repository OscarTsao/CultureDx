"""Audit checker's actual value across 5 dimensions:

1. Detection contribution (does it add Top-k coverage Diagnostician misses?)
2. Reranking contribution (already tested in L2-R1 — refuted)
3. Stacker feature contribution (is met_ratio actually used?)
4. Filter / safeguard contribution (does it reject impossible diagnoses?)
5. Audit / interpretability contribution (per-criterion evidence trail)
"""
import json, sys
sys.path.insert(0, 'src')
from culturedx.eval.lingxidiag_paper import to_paper_parent, PAPER_12_CLASSES
import numpy as np
from collections import defaultdict, Counter

cases = []
with open('results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl') as f:
    for line in f: cases.append(json.loads(line))

def _rco(c): return {it['disorder_code']: it for it in (c.get('decision_trace',{}).get('raw_checker_outputs',[]) or [])}
def met_ratio(c): return {k:v.get('met_ratio',0.0) for k,v in _rco(c).items()}
def confirmed_set(c): return set(c.get('decision_trace',{}).get('logic_engine_confirmed_codes',[]) or [])
def diag_ranked(c): return c.get('decision_trace',{}).get('diagnostician_ranked',[]) or []
def parent(x): return to_paper_parent(x)
def parent_set(L):
    out = set()
    for code in L:
        p = parent(code)
        if p != 'Others': out.add(p)
    return out

# ============================================================================
# DIM 1: Does checker add coverage that Diagnostician misses?
# ============================================================================
print("="*100)
print("DIMENSION 1 — Detection coverage: cases where gold is ONLY in checker, not in Diag")
print("="*100)

diag_only = checker_only = both = neither = 0
checker_only_cases = []

for c in cases:
    gold = parent_set(c.get('gold_diagnoses') or [])
    if not gold: gold = {'Others'}
    
    # Diagnostician top-5 parents
    diag_parents = set()
    for code in diag_ranked(c)[:5]:
        p = parent(code)
        if p != 'Others': diag_parents.add(p)
    
    # Checker: any disorder with met_ratio > 0
    checker_parents = set()
    for code, mr in met_ratio(c).items():
        if mr > 0:
            p = parent(code)
            if p != 'Others': checker_parents.add(p)
    
    in_diag = bool(gold & diag_parents)
    in_checker = bool(gold & checker_parents)
    
    if in_diag and in_checker: both += 1
    elif in_diag and not in_checker: diag_only += 1
    elif not in_diag and in_checker:
        checker_only += 1
        checker_only_cases.append({
            'case_id': c.get('case_id'),
            'gold': gold,
            'diag_top5': [parent(x) for x in diag_ranked(c)[:5]],
        })
    else: neither += 1

print(f"\n  Both Diag and Checker have gold in candidates: {both}/1000 ({both/10:.1f}%)")
print(f"  Only Diag has gold:                            {diag_only}/1000 ({diag_only/10:.1f}%)")
print(f"  Only Checker has gold (Diag missed):           {checker_only}/1000 ({checker_only/10:.1f}%)")
print(f"  Neither has gold:                              {neither}/1000 ({neither/10:.1f}%)")
print(f"\n  → Checker-unique coverage: {checker_only} cases. Diagnostician misses these but checker catches them.")
if checker_only_cases:
    print(f"  Sample 3 checker-only cases:")
    for ex in checker_only_cases[:3]:
        print(f"    case {ex['case_id']}: gold={ex['gold']}, diag_top5={ex['diag_top5']}")

# ============================================================================
# DIM 2: Stacker feature importance — is met_ratio actually used?
# ============================================================================
print("\n" + "="*100)
print("DIMENSION 2 — Stacker feature contribution: did training actually use checker met_ratios?")
print("="*100)

# Look up the canonical stacker feature importance
import subprocess
print("\nSearching repo for stacker feature importance reports...")
result = subprocess.run(['find', 'results/stacker', '-name', '*.json', '-o', '-name', '*importance*'],
                       capture_output=True, text=True)
files = [f for f in result.stdout.strip().split('\n') if f]
print(f"  Found {len(files)} candidate files in results/stacker/")

# Try to find feature importance
for f in files[:20]:
    try:
        with open(f) as fp:
            data = json.load(fp)
            if 'feature_importance' in data or 'feature_importances' in data:
                fi = data.get('feature_importance') or data.get('feature_importances')
                print(f"  Found in {f}:")
                if isinstance(fi, dict):
                    sorted_fi = sorted(fi.items(), key=lambda x: -float(x[1]) if isinstance(x[1], (int, float)) else 0)
                    for k, v in sorted_fi[:15]:
                        print(f"    {k:<35} {v}")
                elif isinstance(fi, list):
                    for item in fi[:15]: print(f"    {item}")
                break
    except: pass

# ============================================================================
# DIM 3: Logic engine confirmed_set — does it filter wrong predictions?
# ============================================================================
print("\n" + "="*100)
print("DIMENSION 3 — Logic engine as filter: how often does it correctly EXCLUDE Diag's top-1?")
print("="*100)

diag_top1_in_confirmed = 0
diag_top1_in_confirmed_AND_correct = 0
diag_top1_in_confirmed_AND_wrong = 0
diag_top1_NOT_in_confirmed = 0
diag_top1_NOT_confirmed_AND_correct = 0  # logic engine wrongly excluded a correct diag
diag_top1_NOT_confirmed_AND_wrong = 0    # logic engine correctly excluded wrong diag

for c in cases:
    gold = parent_set(c.get('gold_diagnoses') or [])
    if not gold: gold = {'Others'}
    diag = diag_ranked(c)
    if not diag: continue
    diag_top1 = diag[0]
    is_correct = parent(diag_top1) in gold
    in_conf = diag_top1 in confirmed_set(c)
    
    if in_conf:
        diag_top1_in_confirmed += 1
        if is_correct: diag_top1_in_confirmed_AND_correct += 1
        else: diag_top1_in_confirmed_AND_wrong += 1
    else:
        diag_top1_NOT_in_confirmed += 1
        if is_correct: diag_top1_NOT_confirmed_AND_correct += 1  # FALSE EXCLUSION
        else: diag_top1_NOT_confirmed_AND_wrong += 1            # CORRECT EXCLUSION

print(f"\n  Diag top-1 IN confirmed_set:     {diag_top1_in_confirmed}/1000 ({diag_top1_in_confirmed/10:.1f}%)")
print(f"    of which correct:              {diag_top1_in_confirmed_AND_correct} (= confirmed + right)")
print(f"    of which wrong:                {diag_top1_in_confirmed_AND_wrong} (= confirmed + wrong, FALSE CONFIRM)")
print(f"\n  Diag top-1 NOT in confirmed:    {diag_top1_NOT_in_confirmed}/1000 ({diag_top1_NOT_in_confirmed/10:.1f}%)")
print(f"    of which correct:              {diag_top1_NOT_confirmed_AND_correct} (= excluded + actually right, FALSE EXCLUDE)")
print(f"    of which wrong:                {diag_top1_NOT_confirmed_AND_wrong} (= excluded + actually wrong, CORRECT EXCLUDE)")

# Confusion matrix view
print(f"\n  Logic engine 'should I confirm Diag-top1?' confusion matrix:")
print(f"                          Diag right     Diag wrong")
print(f"   Confirmed:             {diag_top1_in_confirmed_AND_correct:>6}         {diag_top1_in_confirmed_AND_wrong:>6}")
print(f"   Not confirmed:         {diag_top1_NOT_confirmed_AND_correct:>6}         {diag_top1_NOT_confirmed_AND_wrong:>6}")

# Compute precision/recall as a "filter"
total = diag_top1_in_confirmed_AND_correct + diag_top1_in_confirmed_AND_wrong
if total > 0:
    confirm_precision = diag_top1_in_confirmed_AND_correct / total
    print(f"\n  If we trust 'confirmed' as 'correct', precision = {confirm_precision:.4f}")
recall_actually_correct = diag_top1_in_confirmed_AND_correct / max(diag_top1_in_confirmed_AND_correct + diag_top1_NOT_confirmed_AND_correct, 1)
print(f"  Of all actually-correct Diag-top1, fraction confirmed = {recall_actually_correct:.4f}")

# ============================================================================
# DIM 4: Cases where logic engine REMOVES Diag-top1 wrongly (cost of safeguard)
# ============================================================================
print("\n" + "="*100)
print("DIMENSION 4 — Safeguard cost: how often does pipeline override Diag-top1, and at what cost?")
print("="*100)

# This is the L0 finding restated
override_diag_right_pipeline_wrong = 0
override_diag_wrong_pipeline_right = 0
override_both_right = 0
override_both_wrong = 0
no_override = 0

for c in cases:
    gold = parent_set(c.get('gold_diagnoses') or [])
    if not gold: gold = {'Others'}
    diag = diag_ranked(c)
    if not diag: continue
    primary = c.get('primary_diagnosis')
    
    if parent(diag[0]) == parent(primary):
        no_override += 1
        continue
    
    diag_right = parent(diag[0]) in gold
    primary_right = parent(primary) in gold
    
    if diag_right and not primary_right: override_diag_right_pipeline_wrong += 1
    elif not diag_right and primary_right: override_diag_wrong_pipeline_right += 1
    elif diag_right and primary_right: override_both_right += 1
    else: override_both_wrong += 1

total_override = override_diag_right_pipeline_wrong + override_diag_wrong_pipeline_right + override_both_right + override_both_wrong
print(f"\n  No override (primary == diag_top1 at parent level): {no_override}")
print(f"  Override happened:                                 {total_override}")
print(f"    Diag was right, pipeline overrode to wrong:      {override_diag_right_pipeline_wrong}  ← cost of safeguard")
print(f"    Diag was wrong, pipeline overrode to right:      {override_diag_wrong_pipeline_right}  ← benefit of safeguard")
print(f"    Both right (parent level):                       {override_both_right}")
print(f"    Both wrong:                                      {override_both_wrong}")
print(f"\n  Net effect of safeguard on Top-1:                  {override_diag_wrong_pipeline_right - override_diag_right_pipeline_wrong}  (negative = safeguard hurts)")

# ============================================================================
# DIM 5: Audit value — per-criterion evidence trail richness
# ============================================================================
print("\n" + "="*100)
print("DIMENSION 5 — Audit/interpretability: per-criterion evidence richness")
print("="*100)

total_criteria = 0
criteria_with_evidence_text = 0
criteria_with_status = 0
criteria_per_disorder = []
unique_evidence_phrases = 0

for c in cases:
    rco = _rco(c)
    for code, item in rco.items():
        pc = item.get('per_criterion', [])
        criteria_per_disorder.append(len(pc))
        for cr in pc:
            total_criteria += 1
            if cr.get('evidence', '').strip(): criteria_with_evidence_text += 1
            if cr.get('status') in ('met', 'not_met', 'partial', 'insufficient_evidence'): criteria_with_status += 1

print(f"\n  Total checker criterion-evaluations: {total_criteria}")
print(f"  With evidence text:                  {criteria_with_evidence_text}/{total_criteria} ({criteria_with_evidence_text/total_criteria*100:.1f}%)")
print(f"  With explicit status:                {criteria_with_status}/{total_criteria} ({criteria_with_status/total_criteria*100:.1f}%)")
print(f"  Avg criteria per (case, disorder):   {np.mean(criteria_per_disorder):.2f}")

# Sample: show one rich audit trail
print(f"\n  Sample audit trail (case 0, disorder F32):")
sample_rco = _rco(cases[0]).get('F32', {})
if sample_rco:
    print(f"    met_ratio: {sample_rco.get('met_ratio')}")
    for cr in sample_rco.get('per_criterion', [])[:4]:
        ev = cr.get('evidence','')[:60]
        print(f"    crit {cr.get('criterion_id')}: status={cr.get('status'):<22} conf={cr.get('confidence'):.2f}  evidence={ev!r}")

# ============================================================================
# Final synthesis
# ============================================================================
print("\n" + "="*100)
print("SYNTHESIS — Checker's actual contributions")
print("="*100)
print(f"""
  Dim 1 (detection coverage):   Checker-unique gold = {checker_only}/1000 ({checker_only/10:.1f}%)
                                 → marginal additive detection signal
  Dim 2 (stacker features):     12 met_ratio features ARE in stacker (per Round 99 §0)
                                 → indirect contribution via stacker
  Dim 3 (filter precision):     P(correct | confirmed) = {confirm_precision:.4f}
                                 → confirmed_set is too permissive (lower than Diag's 0.524 baseline)
  Dim 4 (safeguard net effect): {override_diag_wrong_pipeline_right - override_diag_right_pipeline_wrong} (NEGATIVE on Top-1)
                                 → pipeline override is currently harmful
  Dim 5 (audit value):          {criteria_with_evidence_text/total_criteria*100:.1f}% criterion-level evidence text
                                 → highly interpretable per-criterion trail
""")
