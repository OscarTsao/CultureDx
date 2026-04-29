"""Stage L1 — Deterministic rule ablations (offline replay, no LLM rerun)

Per Round 96 §10.L1, test rules A-J:
  A. checker met_ratio top-1
  B. checker met_count top-1
  C. DtV top-1
  D. agreement-first
  E. DtV-rerank-by-checker
  F. checker-veto-DtV
  G. soft-score fusion
  H. no-comorbidity-gate (force single)
  I. comorbidity-annotate-only (= no-gate-on-primary)
  J. parent-first aggregation

Plus targeted L0-derived rules:
  K. NO override — always use diag_top1 as primary
  L. K + force single
  M. K + D13 strict comorbid gate
"""
import json, sys
sys.path.insert(0, 'src')
from culturedx.eval.lingxidiag_paper import to_paper_parent, PAPER_12_CLASSES
import numpy as np
from sklearn.metrics import f1_score
from collections import defaultdict

cases = []
with open('results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl') as f:
    for line in f: cases.append(json.loads(line))

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

def to_parent_unique(codes):
    seen, out = set(), []
    for c in codes:
        p = parent(c)
        if p not in seen and p != 'Others':
            seen.add(p); out.append(p)
    return out

# ======================================================================
# Rules: each returns (primary_code, [comorbid_codes]) given the case
# ======================================================================

def baseline(c):
    return c.get('primary_diagnosis'), c.get('comorbid_diagnoses') or []

# A. Use checker met_ratio top-1 as primary
def rule_A(c):
    mr = met_ratio(c)
    if not mr: return c.get('primary_diagnosis'), []
    primary = max(mr.keys(), key=lambda x: mr[x])
    return primary, []

# B. checker met_count top-1
def rule_B(c):
    mc = met_count(c)
    if not mc: return c.get('primary_diagnosis'), []
    return max(mc.keys(), key=lambda x: mc[x]), []

# C. DtV top-1 (no override — KEY FIX from L0)
def rule_C(c):
    diag = diag_ranked(c)
    if diag: return diag[0], []
    return c.get('primary_diagnosis'), []

# D. agreement-first: if checker met_ratio top1 == diag top1, use it; else fall back to diag
def rule_D(c):
    diag = diag_ranked(c)
    mr = met_ratio(c)
    if diag and mr:
        diag_top = diag[0]
        ck_top = max(mr.keys(), key=lambda x: mr[x])
        if parent(diag_top) == parent(ck_top):
            return diag_top, []
    if diag: return diag[0], []
    return c.get('primary_diagnosis'), []

# E. DtV candidates + checker rerank
def rule_E(c):
    diag = diag_ranked(c)
    mr = met_ratio(c)
    if not diag: return c.get('primary_diagnosis'), []
    # rerank diag candidates by met_ratio
    reranked = sorted(diag, key=lambda x: -mr.get(x, 0))
    return reranked[0], []

# F. Checker-veto-DtV (only veto if dominance violation)
def rule_F(c):
    diag = diag_ranked(c)
    if not diag: return c.get('primary_diagnosis'), []
    primary = diag[0]
    p = parent(primary)
    # Veto if a confirmed candidate dominates primary
    for code in confirmed(c):
        cp = parent(code)
        if cp in DOMINATES and p in DOMINATES[cp] and crit_A_met(c, code):
            return code, []
    return primary, []

# G. Soft-score fusion
def rule_G(c, w_mr=0.4, w_diag=0.5, w_conf=0.1):
    rco = _rco(c)
    if not rco: return c.get('primary_diagnosis'), []
    diag = diag_ranked(c)
    diag_pos = {code: i for i, code in enumerate(diag)}
    # Score each candidate
    scores = {}
    n_diag = max(len(diag), 1)
    for code in rco.keys():
        diag_score = (n_diag - diag_pos.get(code, n_diag)) / n_diag
        mr_score = met_ratio(c).get(code, 0)
        conf_score = mean_evid_conf(c, code)
        scores[code] = w_mr*mr_score + w_diag*diag_score + w_conf*conf_score
    primary = max(scores.keys(), key=lambda x: scores[x])
    return primary, []

# H. No comorbidity (force single)
def rule_H(c):
    return c.get('primary_diagnosis'), []

# I. Comorbidity annotate only (= use current primary, drop comorbid emission for EM)
# = same as H actually for EM purposes
def rule_I(c):
    return c.get('primary_diagnosis'), []

# J. Parent-first then subtype (parent-collapse early)
def rule_J(c):
    diag = diag_ranked(c)
    if not diag: return c.get('primary_diagnosis'), []
    return parent(diag[0]), []  # always emit parent code

# K. NO OVERRIDE rule (the L0-derived rule — most promising)
def rule_K(c):
    diag = diag_ranked(c)
    primary = diag[0] if diag else c.get('primary_diagnosis')
    return primary, []  # = same as C

# L. K + D13 strict comorbid (dominance + crit A + decisive ≥ 0.85)
def rule_L(c):
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
        if decisive(c, cand) < 0.85: continue
        out.append(cand)
        break
    return primary, out

# M. K + only emit comorbid if multilabel signal strong
def rule_M(c):
    diag = diag_ranked(c)
    primary = diag[0] if diag else c.get('primary_diagnosis')
    p = parent(primary)
    p_dec = decisive(c, primary)
    out = []
    for cand in diag[1:5]:
        if cand == primary: continue
        cp = parent(cand)
        if cp == p: continue
        if cand not in confirmed(c): continue
        if not dom_ok(p, cp, c): continue
        if not crit_A_met(c, cand): continue
        if decisive(c, cand) < 0.9 * p_dec: continue
        out.append(cand)
        break
    return primary, out

# Oracle reference
def oracle_size_aware(c):
    """Knows gold size; emits primary + actual comorbid only if gold is multilabel."""
    primary = c.get('primary_diagnosis')
    gold = parent_set(c.get('gold_diagnoses') or [])
    if len(gold) <= 1: return primary, []
    return primary, c.get('comorbid_diagnoses') or []

def oracle_primary(c):
    """Knows gold; picks first code whose parent is in gold."""
    gold = parent_set(c.get('gold_diagnoses') or [])
    for code in diag_ranked(c):
        if parent(code) in gold: return code, []
    for code in confirmed(c):
        if parent(code) in gold: return code, []
    return c.get('primary_diagnosis'), []

# ======================================================================
# Eval
# ======================================================================
def evaluate(cases, fn, label):
    classes = PAPER_12_CLASSES
    cls_idx = {c:i for i,c in enumerate(classes)}
    n = len(cases)
    top1=top3=em=0
    gold_mat = np.zeros((n, len(classes)), dtype=int)
    pred_mat = np.zeros((n, len(classes)), dtype=int)
    sd = defaultdict(int)
    
    # F32/F41 asymmetry tracking: count cases predicted as F41 but gold is F32
    f32_to_f41 = 0  # gold F32, predicted F41
    f41_to_f32 = 0  # gold F41, predicted F32
    
    for i, c in enumerate(cases):
        gold_set = parent_set(c.get('gold_diagnoses') or [])
        if not gold_set: gold_set = {'Others'}
        primary, comorbid = fn(c)
        primary_p = parent(primary)
        comorbid_p = [parent(x) for x in comorbid]
        pred_set = set([primary_p] + comorbid_p) - {'Others'}
        if not pred_set: pred_set = {primary_p}
        
        if primary_p in gold_set: top1 += 1
        # Top-3 from diag_ranked
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
        
        # F32/F41 asymmetry
        if 'F32' in gold_set and primary_p == 'F41': f32_to_f41 += 1
        if 'F41' in gold_set and primary_p == 'F32': f41_to_f32 += 1
    
    return {
        'label':label, 'Top-1':top1/n, 'Top-3':top3/n, 'EM':em/n,
        'mF1':f1_score(gold_mat, pred_mat, average='macro', zero_division=0),
        'wF1':f1_score(gold_mat, pred_mat, average='weighted', zero_division=0),
        'size_dist':dict(sorted(sd.items())),
        'F32→F41':f32_to_f41,
        'F41→F32':f41_to_f32,
    }

print("="*145)
print("Stage L1 — Deterministic rule replay (Round 96 §10.L1)")
print("="*145)
print(f"\n{'Rule':<55} {'Top-1':>7} {'Top-3':>7} {'EM':>7} {'mF1':>7} {'wF1':>7}  {'F32→F41':>7} {'F41→F32':>7}  size_dist")
print("-"*145)

rules = [
    ('Baseline (current pipeline)',                    baseline),
    ('A. Checker met_ratio top-1',                    rule_A),
    ('B. Checker met_count top-1',                    rule_B),
    ('C. DtV top-1 only (no override)',               rule_C),
    ('D. Agreement-first (DtV∩Checker)',              rule_D),
    ('E. DtV candidates + checker rerank',            rule_E),
    ('F. Checker-veto-DtV (dominance only)',          rule_F),
    ('G. Soft-score fusion',                          rule_G),
    ('H. Force single (= Variant C, prev sandbox)',   rule_H),
    ('K. NO override (diag_top1 always primary)',     rule_K),
    ('L. K + strict D13 comorbid gate',               rule_L),
    ('M. K + calibrated comorbid (≥0.9*primary)',     rule_M),
    ('— Oracle: size-aware comorbid',                  oracle_size_aware),
    ('— Oracle: primary',                              oracle_primary),
]

for label, fn in rules:
    r = evaluate(cases, fn, label)
    print(f"{label:<55} {r['Top-1']:>7.4f} {r['Top-3']:>7.4f} {r['EM']:>7.4f} {r['mF1']:>7.4f} {r['wF1']:>7.4f}  {r['F32→F41']:>7} {r['F41→F32']:>7}  {r['size_dist']!s}")
