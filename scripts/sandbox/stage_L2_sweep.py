"""Stage L2 — Threshold/weight tuning on dev split only.

Per Round 96 §10.L2:
  "tune weights on dev split only, freeze, evaluate test_final"
  "不要在 test 上試來試去"

Methodology:
  - Random 50/50 split with fixed seed (deterministic, reproducible)
  - Sweep threshold parameters on dev only
  - Report dev-best + frozen test_final
  - Report on multiple metrics to expose Pareto trade-offs

Promising rules from L1 to tune:
  L1. K + decisive_threshold T (sweep T ∈ {0.5..0.95})
  L2. K + relative threshold R (sweep R = cand_decisive / primary_decisive)
  L3. K + soft-score weights (small grid)
  L4. K + parent-collapse comorbid (test rule J variant)
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

# Deterministic 50/50 split
random.seed(42)
indices = list(range(len(cases)))
random.shuffle(indices)
DEV_IDX = set(indices[:500])
TEST_IDX = set(indices[500:])
DEV = [cases[i] for i in indices[:500]]
TEST = [cases[i] for i in indices[500:]]
print(f"L2 setup: deterministic seed=42, dev N={len(DEV)}, test_final N={len(TEST)}\n")

# === Helpers ===
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
def mean_evid_conf(c, code):
    rco = _rco(c).get(code)
    if not rco: return 0.0
    pc = rco.get('per_criterion', [])
    if not pc: return 0.0
    return float(np.mean([cr.get('confidence',0.0) for cr in pc]))

DOMINATES = {'F33':['F32'],'F31':['F32','F33'],'F20':['F22','F32','F33','F31']}
F41_2_BLOCKERS = {'F32','F33','F41'}
def dom_ok(p, cand, c):
    if p == 'Z71' or cand == 'Z71': return False
    if p in DOMINATES and cand in DOMINATES[p]: return False
    if cand in DOMINATES and p in DOMINATES[cand]: return False
    if cand == 'F41.2' or cand.startswith('F41.2'):
        if any(b in confirmed(c) for b in F41_2_BLOCKERS): return False
    return True

def evaluate(cases, fn, label=""):
    classes = PAPER_12_CLASSES
    cls_idx = {c:i for i,c in enumerate(classes)}
    n = len(cases)
    top1=top3=em=0
    gold_mat = np.zeros((n, len(classes)), dtype=int)
    pred_mat = np.zeros((n, len(classes)), dtype=int)
    sd = defaultdict(int)
    
    for i, c in enumerate(cases):
        gold_set = parent_set(c.get('gold_diagnoses') or [])
        if not gold_set: gold_set = {'Others'}
        primary, comorbid = fn(c)
        primary_p = parent(primary)
        comorbid_p = [parent(x) for x in comorbid]
        pred_set = set([primary_p] + comorbid_p) - {'Others'}
        if not pred_set: pred_set = {primary_p}
        if primary_p in gold_set: top1 += 1
        rk = diag_ranked(c)
        rp = []
        for r in rk:
            pp = parent(r)
            if pp != 'Others' and pp not in rp: rp.append(pp)
        top3_set = ([primary_p] + [r for r in rp if r != primary_p])[:3]
        if any(t in gold_set for t in top3_set): top3 += 1
        if pred_set == gold_set: em += 1
        for g in gold_set:
            if g in cls_idx: gold_mat[i, cls_idx[g]] = 1
        for p in pred_set:
            if p in cls_idx: pred_mat[i, cls_idx[p]] = 1
        sd[len(pred_set)] += 1
    return {
        'label':label,
        'Top-1':top1/n,'Top-3':top3/n,'EM':em/n,
        'mF1':f1_score(gold_mat, pred_mat, average='macro', zero_division=0),
        'wF1':f1_score(gold_mat, pred_mat, average='weighted', zero_division=0),
        'size_dist':dict(sorted(sd.items())),
    }

# Composite scoring for dev selection — paper-aligned weights
# Top-1 is the published primary metric; mF1 expresses multilabel quality;
# EM measures exact set match. We weight Top-1 highest then mF1.
def composite(r, w_top1=0.5, w_mf1=0.25, w_em=0.15, w_top3=0.10):
    return w_top1*r['Top-1'] + w_mf1*r['mF1'] + w_em*r['EM'] + w_top3*r['Top-3']

# ============================================================================
# Sweep 1: Rule K + comorbid emission with absolute decisive threshold
# ============================================================================
def make_rule_K_decisive(T):
    def rule(c):
        diag = diag_ranked(c)
        primary = diag[0] if diag else c.get('primary_diagnosis')
        p = parent(primary)
        out = []
        for cand in diag[1:5]:
            if cand == primary: continue
            cp = parent(cand)
            if cp == p: continue
            if cand not in confirmed(c): continue
            if not dom_ok(p, cp, c): continue
            if not crit_A_met(c, cand): continue
            if decisive(c, cand) < T: continue
            out.append(cand); break
        return primary, out
    return rule

print("="*150)
print("Sweep 1: Rule K + comorbid emit if decisive ≥ T (absolute threshold)")
print("="*150)
print(f"{'T':>5} | {'DEV: Top-1':>10} {'Top-3':>7} {'EM':>7} {'mF1':>7} {'wF1':>7} {'composite':>10} | {'TEST: Top-1':>11} {'Top-3':>7} {'EM':>7} {'mF1':>7} {'wF1':>7}  size_dist (test)")
print("-"*150)
sweep1 = []
for T in [0.0, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0]:
    fn = make_rule_K_decisive(T)
    dev_r = evaluate(DEV, fn, f"K+T={T}")
    test_r = evaluate(TEST, fn, f"K+T={T}")
    cs = composite(dev_r)
    sweep1.append((T, cs, dev_r, test_r))
    print(f"{T:>5.2f} | {dev_r['Top-1']:>10.4f} {dev_r['Top-3']:>7.4f} {dev_r['EM']:>7.4f} {dev_r['mF1']:>7.4f} {dev_r['wF1']:>7.4f} {cs:>10.4f} | {test_r['Top-1']:>11.4f} {test_r['Top-3']:>7.4f} {test_r['EM']:>7.4f} {test_r['mF1']:>7.4f} {test_r['wF1']:>7.4f}  {test_r['size_dist']!s}")
best1 = max(sweep1, key=lambda x: x[1])
print(f"\n  → Best on DEV: T={best1[0]}  (composite={best1[1]:.4f})  → frozen TEST: Top-1={best1[3]['Top-1']:.4f} EM={best1[3]['EM']:.4f} mF1={best1[3]['mF1']:.4f}\n")

# ============================================================================
# Sweep 2: Rule K + relative threshold (cand_decisive / primary_decisive ≥ R)
# ============================================================================
def make_rule_K_relative(R):
    def rule(c):
        diag = diag_ranked(c)
        primary = diag[0] if diag else c.get('primary_diagnosis')
        p = parent(primary)
        p_dec = decisive(c, primary)
        if p_dec <= 0:
            return primary, []
        out = []
        for cand in diag[1:5]:
            if cand == primary: continue
            cp = parent(cand)
            if cp == p: continue
            if cand not in confirmed(c): continue
            if not dom_ok(p, cp, c): continue
            if not crit_A_met(c, cand): continue
            if decisive(c, cand) < R * p_dec: continue
            out.append(cand); break
        return primary, out
    return rule

print("="*150)
print("Sweep 2: Rule K + comorbid emit if cand_decisive ≥ R × primary_decisive (relative)")
print("="*150)
print(f"{'R':>5} | {'DEV: Top-1':>10} {'Top-3':>7} {'EM':>7} {'mF1':>7} {'wF1':>7} {'composite':>10} | {'TEST: Top-1':>11} {'Top-3':>7} {'EM':>7} {'mF1':>7} {'wF1':>7}  size_dist (test)")
print("-"*150)
sweep2 = []
for R in [0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10]:
    fn = make_rule_K_relative(R)
    dev_r = evaluate(DEV, fn)
    test_r = evaluate(TEST, fn)
    cs = composite(dev_r)
    sweep2.append((R, cs, dev_r, test_r))
    print(f"{R:>5.2f} | {dev_r['Top-1']:>10.4f} {dev_r['Top-3']:>7.4f} {dev_r['EM']:>7.4f} {dev_r['mF1']:>7.4f} {dev_r['wF1']:>7.4f} {cs:>10.4f} | {test_r['Top-1']:>11.4f} {test_r['Top-3']:>7.4f} {test_r['EM']:>7.4f} {test_r['mF1']:>7.4f} {test_r['wF1']:>7.4f}  {test_r['size_dist']!s}")
best2 = max(sweep2, key=lambda x: x[1])
print(f"\n  → Best on DEV: R={best2[0]}  (composite={best2[1]:.4f})  → frozen TEST: Top-1={best2[3]['Top-1']:.4f} EM={best2[3]['EM']:.4f} mF1={best2[3]['mF1']:.4f}\n")

# ============================================================================
# Sweep 3: Rule K + ABS T + REL R (joint)
# ============================================================================
def make_rule_K_joint(T, R):
    def rule(c):
        diag = diag_ranked(c)
        primary = diag[0] if diag else c.get('primary_diagnosis')
        p = parent(primary)
        p_dec = decisive(c, primary)
        if p_dec <= 0: return primary, []
        out = []
        for cand in diag[1:5]:
            if cand == primary: continue
            cp = parent(cand)
            if cp == p: continue
            if cand not in confirmed(c): continue
            if not dom_ok(p, cp, c): continue
            if not crit_A_met(c, cand): continue
            cd = decisive(c, cand)
            if cd < T: continue
            if cd < R * p_dec: continue
            out.append(cand); break
        return primary, out
    return rule

print("="*150)
print("Sweep 3: Rule K + joint absolute T + relative R")
print("="*150)
print(f"{'T':>5} {'R':>5} | {'DEV: Top-1':>10} {'EM':>7} {'mF1':>7} {'composite':>10} | {'TEST: Top-1':>11} {'EM':>7} {'mF1':>7}  size_dist (test)")
print("-"*150)
sweep3 = []
for T in [0.5, 0.7, 0.8, 0.85]:
    for R in [0.7, 0.85, 0.95, 1.0]:
        fn = make_rule_K_joint(T, R)
        dev_r = evaluate(DEV, fn)
        test_r = evaluate(TEST, fn)
        cs = composite(dev_r)
        sweep3.append((T, R, cs, dev_r, test_r))
        print(f"{T:>5.2f} {R:>5.2f} | {dev_r['Top-1']:>10.4f} {dev_r['EM']:>7.4f} {dev_r['mF1']:>7.4f} {cs:>10.4f} | {test_r['Top-1']:>11.4f} {test_r['EM']:>7.4f} {test_r['mF1']:>7.4f}  {test_r['size_dist']!s}")
best3 = max(sweep3, key=lambda x: x[2])
print(f"\n  → Best on DEV: T={best3[0]}, R={best3[1]} (composite={best3[2]:.4f})  → frozen TEST: Top-1={best3[4]['Top-1']:.4f} EM={best3[4]['EM']:.4f} mF1={best3[4]['mF1']:.4f}\n")

# ============================================================================
# Sweep 4: Soft-score primary + best comorbid threshold from sweep 2
# ============================================================================
def make_softscore(w_mr, w_diag, w_conf):
    def rule(c):
        rco = _rco(c)
        if not rco: return c.get('primary_diagnosis'), []
        diag = diag_ranked(c)
        diag_pos = {code: i for i, code in enumerate(diag)}
        n_diag = max(len(diag), 1)
        scores = {}
        for code in rco.keys():
            d_score = (n_diag - diag_pos.get(code, n_diag)) / n_diag
            mr_score = met_ratio(c).get(code, 0)
            cf_score = mean_evid_conf(c, code)
            scores[code] = w_mr*mr_score + w_diag*d_score + w_conf*cf_score
        primary = max(scores.keys(), key=lambda x: scores[x])
        return primary, []
    return rule

print("="*150)
print("Sweep 4: Soft-score primary (no comorbid) — sanity check on G")
print("="*150)
print(f"{'w_mr':>5} {'w_diag':>7} {'w_conf':>7} | {'DEV: Top-1':>10} {'EM':>7} {'mF1':>7} {'composite':>10} | {'TEST: Top-1':>11} {'EM':>7} {'mF1':>7}")
print("-"*150)
sweep4 = []
for w_diag in [0.3, 0.5, 0.7, 0.9]:
    for w_mr in [0.0, 0.2, 0.4, 0.6]:
        w_conf = max(0.0, 1.0 - w_diag - w_mr)
        if w_conf > 0.5: continue  # skip degenerate
        fn = make_softscore(w_mr, w_diag, w_conf)
        dev_r = evaluate(DEV, fn)
        test_r = evaluate(TEST, fn)
        cs = composite(dev_r)
        sweep4.append((w_mr, w_diag, w_conf, cs, dev_r, test_r))
        print(f"{w_mr:>5.2f} {w_diag:>7.2f} {w_conf:>7.2f} | {dev_r['Top-1']:>10.4f} {dev_r['EM']:>7.4f} {dev_r['mF1']:>7.4f} {cs:>10.4f} | {test_r['Top-1']:>11.4f} {test_r['EM']:>7.4f} {test_r['mF1']:>7.4f}")
best4 = max(sweep4, key=lambda x: x[3])
print(f"\n  → Best on DEV: w_mr={best4[0]}, w_diag={best4[1]}, w_conf={best4[2]} (composite={best4[3]:.4f})  → frozen TEST: Top-1={best4[5]['Top-1']:.4f}\n")

# ============================================================================
# Final summary
# ============================================================================
print("="*150)
print("L2 SUMMARY — best dev-tuned rules + frozen test_final results")
print("="*150)

# L1 baselines on the same TEST split
def baseline(c): return c.get('primary_diagnosis'), c.get('comorbid_diagnoses') or []
def rule_K(c):
    diag = diag_ranked(c)
    return (diag[0] if diag else c.get('primary_diagnosis')), []

ref_baseline = evaluate(TEST, baseline)
ref_K = evaluate(TEST, rule_K)
ref_H = evaluate(TEST, lambda c: (c.get('primary_diagnosis'), []))

print(f"\nReference (L1, evaluated on same TEST split):")
print(f"  {'Baseline (current pipeline)':<45}: Top-1={ref_baseline['Top-1']:.4f} Top-3={ref_baseline['Top-3']:.4f} EM={ref_baseline['EM']:.4f} mF1={ref_baseline['mF1']:.4f} wF1={ref_baseline['wF1']:.4f}")
print(f"  {'Rule H (force single, current primary)':<45}: Top-1={ref_H['Top-1']:.4f} Top-3={ref_H['Top-3']:.4f} EM={ref_H['EM']:.4f} mF1={ref_H['mF1']:.4f} wF1={ref_H['wF1']:.4f}")
print(f"  {'Rule K (no override, force single)':<45}: Top-1={ref_K['Top-1']:.4f} Top-3={ref_K['Top-3']:.4f} EM={ref_K['EM']:.4f} mF1={ref_K['mF1']:.4f} wF1={ref_K['wF1']:.4f}")

print(f"\nL2 best per sweep (dev-tuned, evaluated on frozen TEST):")
print(f"  Sweep 1 best: K+T={best1[0]:<5}                            : Top-1={best1[3]['Top-1']:.4f} Top-3={best1[3]['Top-3']:.4f} EM={best1[3]['EM']:.4f} mF1={best1[3]['mF1']:.4f} wF1={best1[3]['wF1']:.4f}")
print(f"  Sweep 2 best: K+R={best2[0]:<5}                            : Top-1={best2[3]['Top-1']:.4f} Top-3={best2[3]['Top-3']:.4f} EM={best2[3]['EM']:.4f} mF1={best2[3]['mF1']:.4f} wF1={best2[3]['wF1']:.4f}")
print(f"  Sweep 3 best: K+T={best3[0]:.2f}+R={best3[1]:.2f}                       : Top-1={best3[4]['Top-1']:.4f} Top-3={best3[4]['Top-3']:.4f} EM={best3[4]['EM']:.4f} mF1={best3[4]['mF1']:.4f} wF1={best3[4]['wF1']:.4f}")
print(f"  Sweep 4 best: SoftScore w={best4[0],best4[1],best4[2]}: Top-1={best4[5]['Top-1']:.4f} Top-3={best4[5]['Top-3']:.4f} EM={best4[5]['EM']:.4f} mF1={best4[5]['mF1']:.4f} wF1={best4[5]['wF1']:.4f}")
