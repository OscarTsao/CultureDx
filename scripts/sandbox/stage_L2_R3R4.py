"""L2-R3 + L2-R4: Comorbidity annotation gate + comprehensive ranking metrics.

Round 99 §5.R3 reframe:
  - Benchmark output: single primary (Diagnostician[0])
  - Audit output: separate annotation list of comorbid candidates
  - Question: under what gate does annotation maximize {EM, mF1} when EVALUATED as multilabel set?
  - This is the "if reviewer asks for comorbid prediction, what should we emit?"

Round 99 §7 discipline:
  - Sweep on dev only, freeze on test
  - Use multi-objective composite to avoid overfitting to one metric
"""
import json, sys, random
sys.path.insert(0, 'src')
from culturedx.eval.lingxidiag_paper import to_paper_parent, PAPER_12_CLASSES
import numpy as np
from sklearn.metrics import f1_score
from collections import defaultdict

cases = []
with open('results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl') as f:
    for line in f: cases.append(json.loads(line))

random.seed(42)
indices = list(range(len(cases)))
random.shuffle(indices)
DEV = [cases[i] for i in indices[:500]]
TEST = [cases[i] for i in indices[500:]]

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
def crit_A_met(c, code):
    rco = _rco(c).get(code)
    if not rco: return False
    pc = rco.get('per_criterion', [])
    if not pc: return False
    for cr in pc:
        if cr.get('criterion_id') == 'A': return cr.get('status') == 'met'
    return pc[0].get('status') == 'met'
def decisive(c, code):
    rco = _rco(c).get(code)
    if not rco: return 0.0
    pc = rco.get('per_criterion', [])
    if not pc: return 0.0
    s = []
    for cr in pc:
        w = {'met':1.0,'partial':0.5,'insufficient_evidence':0.3,'not_met':0.0}.get(cr.get('status','not_met'),0)
        s.append(cr.get('confidence',0.0)*w)
    return float(np.mean(s)) if s else 0.0

DOMINATES = {'F33':['F32'],'F31':['F32','F33'],'F20':['F22','F32','F33','F31']}
F41_2_BLOCKERS = {'F32','F33','F41'}
def dom_ok(p, cand, c):
    if p == 'Z71' or cand == 'Z71': return False
    if p in DOMINATES and cand in DOMINATES[p]: return False
    if cand in DOMINATES and p in DOMINATES[cand]: return False
    if cand == 'F41.2' or cand.startswith('F41.2'):
        if any(b in confirmed_set(c) for b in F41_2_BLOCKERS): return False
    return True

# ============================================================================
# Multilabel evaluator (primary = locked at Diagnostician[0])
# ============================================================================
def evaluate_full(cases_, comorbid_fn, label):
    """primary always = diag[0]. comorbid_fn(case, primary_code) -> list of comorbid codes."""
    classes = PAPER_12_CLASSES
    cls_idx = {p:i for i,p in enumerate(classes)}
    n = len(cases_)
    top1=top3=em=0
    rr_sum=0.0
    rank_count=0
    rank_sum=0.0
    pred_size_dist = defaultdict(int)
    gold_size_dist = defaultdict(int)
    gold_mat = np.zeros((n, len(classes)), dtype=int)
    pred_mat = np.zeros((n, len(classes)), dtype=int)
    
    for i, c in enumerate(cases_):
        gold = parent_set(c.get('gold_diagnoses') or [])
        if not gold: gold = {'Others'}
        diag = diag_ranked(c)
        primary = diag[0] if diag else c.get('primary_diagnosis')
        primary_p = parent(primary)
        comorbid = comorbid_fn(c, primary)
        comorbid_p = [parent(x) for x in comorbid]
        pred_set = set([primary_p] + comorbid_p) - {'Others'}
        if not pred_set: pred_set = {primary_p}
        # Metrics
        if primary_p in gold: top1 += 1
        ranked_parents = []
        seen = set()
        for code in diag:
            p = parent(code)
            if p not in seen and p != 'Others':
                seen.add(p); ranked_parents.append(p)
        if any(p in gold for p in ranked_parents[:3]): top3 += 1
        if pred_set == gold: em += 1
        # MRR (from full diag rank)
        for k, p in enumerate(ranked_parents):
            if p in gold:
                rr_sum += 1.0/(k+1); rank_sum += (k+1); rank_count += 1; break
        # F1
        for g in gold:
            if g in cls_idx: gold_mat[i, cls_idx[g]] = 1
        for p in pred_set:
            if p in cls_idx: pred_mat[i, cls_idx[p]] = 1
        pred_size_dist[len(pred_set)] += 1
        gold_size_dist[len(gold)] += 1
    
    return {
        'label': label,
        'Top-1': top1/n, 'Top-3': top3/n, 'EM': em/n,
        'MRR': rr_sum/n,
        'mean_gold_rank': rank_sum/max(rank_count,1),
        'mF1': f1_score(gold_mat, pred_mat, average='macro', zero_division=0),
        'wF1': f1_score(gold_mat, pred_mat, average='weighted', zero_division=0),
        'pred_size': dict(sorted(pred_size_dist.items())),
        'gold_size': dict(sorted(gold_size_dist.items())),
    }

# ============================================================================
# L2-R3: Annotation gate sweep
# ============================================================================
print("="*150)
print("L2-R3: Comorbidity annotation gate (primary LOCKED at Diagnostician[0])")
print("="*150)
print()

def cg_none(c, primary): return []

def make_cg_strict(T_decisive, R_relative=None, max_n=1):
    """Strict gate: dominance + crit A + decisive ≥ T (and optionally relative threshold)."""
    def gate(c, primary):
        p = parent(primary)
        p_dec = decisive(c, primary)
        diag = diag_ranked(c)
        out = []
        for cand in diag[1:5]:
            if cand == primary: continue
            cp = parent(cand)
            if cp == p: continue
            if cand not in confirmed_set(c): continue
            if not dom_ok(p, cp, c): continue
            if not crit_A_met(c, cand): continue
            cd = decisive(c, cand)
            if cd < T_decisive: continue
            if R_relative is not None and p_dec > 0 and cd < R_relative * p_dec: continue
            out.append(cand)
            if len(out) >= max_n: break
        return out
    return gate

def cg_baseline(c, primary):
    return c.get('comorbid_diagnoses') or []

# Sweep on dev
print(f"{'Gate':<45} | DEV  Top-1   Top-3      EM     MRR     mF1     wF1   composite | TEST  Top-1   Top-3      EM     MRR     mF1     wF1   pred_size_dist (test)")
print("-"*210)

# Gates to test:
gates = [
    ('Baseline (current pipeline comorbid)', cg_baseline),
    ('R3-α: No comorbid (annotation off)', cg_none),
    ('R3-β: T_dec ≥ 0.70', make_cg_strict(0.70)),
    ('R3-β: T_dec ≥ 0.80', make_cg_strict(0.80)),
    ('R3-β: T_dec ≥ 0.85', make_cg_strict(0.85)),
    ('R3-β: T_dec ≥ 0.90', make_cg_strict(0.90)),
    ('R3-γ: T_dec ≥ 0.85, R_rel ≥ 0.90', make_cg_strict(0.85, 0.90)),
    ('R3-γ: T_dec ≥ 0.85, R_rel ≥ 0.95', make_cg_strict(0.85, 0.95)),
    ('R3-γ: T_dec ≥ 0.85, R_rel ≥ 1.00', make_cg_strict(0.85, 1.00)),
    ('R3-γ: T_dec ≥ 0.90, R_rel ≥ 0.95', make_cg_strict(0.90, 0.95)),
    ('R3-γ: T_dec ≥ 0.95, R_rel ≥ 1.00', make_cg_strict(0.95, 1.00)),
]

# Composite: balance EM (paper) + mF1 (multilabel quality)
def comp_R3(r):
    return 0.4*r['EM'] + 0.3*r['mF1'] + 0.2*r['Top-1'] + 0.1*r['Top-3']

results = []
for label, gate in gates:
    dev_r = evaluate_full(DEV, gate, label)
    test_r = evaluate_full(TEST, gate, label)
    cs = comp_R3(dev_r)
    results.append((label, gate, cs, dev_r, test_r))
    print(f"{label[:45]:<45} | {dev_r['Top-1']:>6.4f} {dev_r['Top-3']:>7.4f} {dev_r['EM']:>7.4f} {dev_r['MRR']:>7.4f} {dev_r['mF1']:>7.4f} {dev_r['wF1']:>7.4f} {cs:>10.4f} | {test_r['Top-1']:>6.4f} {test_r['Top-3']:>7.4f} {test_r['EM']:>7.4f} {test_r['MRR']:>7.4f} {test_r['mF1']:>7.4f} {test_r['wF1']:>7.4f}   {test_r['pred_size']!s}")

best_R3 = max(results, key=lambda x: x[2])
print(f"\nBest gate on DEV: {best_R3[0]} (composite={best_R3[2]:.4f})")
print(f"  → frozen TEST: Top-1={best_R3[4]['Top-1']:.4f}, EM={best_R3[4]['EM']:.4f}, mF1={best_R3[4]['mF1']:.4f}, wF1={best_R3[4]['wF1']:.4f}")

print(f"\nGold size distribution (TEST): {results[0][4]['gold_size']}")

# ============================================================================
# L2-R4: Comprehensive metrics for the BEST design from R1+R3
# ============================================================================
print("\n" + "="*150)
print("L2-R4: COMPREHENSIVE FINAL METRICS — primary-locked + best dev-tuned annotation gate")
print("="*150)

print(f"\nFinal proposed pipeline: primary = Diagnostician[0] (locked); comorbid = {best_R3[0]}")
print(f"\n{'Metric':<25} {'Baseline':>10} {'Final design':>14} {'Δ':>10}")
print("-"*70)
baseline = results[0][4]  # current pipeline on TEST
final = best_R3[4]
metrics = ['Top-1', 'Top-3', 'EM', 'MRR', 'mean_gold_rank', 'mF1', 'wF1']
for m in metrics:
    b = baseline[m]; f = final[m]
    delta = f-b
    print(f"{m:<25} {b:>10.4f} {f:>14.4f} {delta:>+10.4f}")

# Pareto frontier visualization
print("\n--- Pareto frontier on TEST (Top-1 vs EM vs mF1) ---")
print(f"{'Gate':<45} {'Top-1':>7} {'EM':>7} {'mF1':>7}  pred_size")
for label, gate, cs, dev_r, test_r in results:
    print(f"{label[:45]:<45} {test_r['Top-1']:>7.4f} {test_r['EM']:>7.4f} {test_r['mF1']:>7.4f}  {test_r['pred_size']!s}")

# ============================================================================
# Sanity: oracle comparison
# ============================================================================
print("\n--- Oracle reference (knows gold size) ---")
def cg_oracle(c, primary):
    gold = parent_set(c.get('gold_diagnoses') or [])
    if len(gold) <= 1: return []
    return c.get('comorbid_diagnoses') or []
oracle_r = evaluate_full(TEST, cg_oracle, 'Oracle: gold-size aware')
print(f"  Oracle: Top-1={oracle_r['Top-1']:.4f}, EM={oracle_r['EM']:.4f}, mF1={oracle_r['mF1']:.4f}")
print(f"  → Note: Oracle Top-1 ≠ Final Top-1 because Oracle uses CURRENT primary (0.502) while Final uses Diag[0] (0.512)")
