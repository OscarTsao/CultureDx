"""Stage L2 (Round 99 redesign) — primary-locked checker-audited ranking.

L2-R1: Top-1 locked = Diagnostician[0]; checker reranks rank 2-5
L2-R2: Checker as conservative veto (high-confidence contradiction only)
L2-R3: Comorbidity annotation gate (separate from benchmark prediction)
L2-R4: Ranking metrics (MRR, mean gold rank, nDCG@5, Gold@k)

Methodology (Round 99 §7):
  - dev split for threshold selection
  - frozen test_final for final reporting
  - deterministic seed=42 50/50 split
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
print(f"L2-redesign setup: dev N={len(DEV)}, test N={len(TEST)}\n")

# === Helpers ===
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
        if any(b in confirmed_set(c) for b in F41_2_BLOCKERS): return False
    return True

def to_parent_unique(codes):
    seen, out = set(), []
    for c in codes:
        p = parent(c)
        if p not in seen and p != 'Others':
            seen.add(p); out.append(p)
    return out

# ============================================================================
# Round 99 §5 L2-R4: Ranking metrics
# ============================================================================
def evaluate_ranking(cases_, ranker_fn, label):
    """ranker_fn(case) returns ordered list of paper-parent codes (Top-1 first)."""
    n = len(cases_)
    top1 = top3 = top5 = top10 = 0
    rr_sum = 0.0
    rank_sum = 0.0
    rank_count = 0
    rank_dist = defaultdict(int)
    f32_to_f41 = 0  # gold F32 but predicted F41 as Top-1
    f41_to_f32 = 0
    
    # also EM (force-single primary) and mF1 from Top-1
    em = 0
    classes = PAPER_12_CLASSES
    cls_idx = {p:i for i,p in enumerate(classes)}
    gm = np.zeros((n, len(classes)), dtype=int)
    pm = np.zeros((n, len(classes)), dtype=int)
    
    for i, c in enumerate(cases_):
        gold = parent_set(c.get('gold_diagnoses') or [])
        if not gold: gold = {'Others'}
        ranked_parents = ranker_fn(c)
        # Find first gold position
        gold_pos = -1
        for k, p in enumerate(ranked_parents):
            if p in gold:
                gold_pos = k + 1
                break
        if gold_pos > 0:
            rank_sum += gold_pos
            rank_count += 1
            rr_sum += 1.0 / gold_pos
            rank_dist[gold_pos] += 1
        else:
            rank_dist['out'] += 1
            # MRR contribution = 0
        if ranked_parents:
            primary = ranked_parents[0]
            if primary in gold: top1 += 1
            if 'F32' in gold and primary == 'F41': f32_to_f41 += 1
            if 'F41' in gold and primary == 'F32': f41_to_f32 += 1
            
            # EM/F1 (force-single)
            pred_set = {primary}
            if pred_set == gold: em += 1
            for g in gold:
                if g in cls_idx: gm[i, cls_idx[g]] = 1
            for p in pred_set:
                if p in cls_idx: pm[i, cls_idx[p]] = 1
        if any(p in gold for p in ranked_parents[:3]): top3 += 1
        if any(p in gold for p in ranked_parents[:5]): top5 += 1
        if any(p in gold for p in ranked_parents[:10]): top10 += 1
    
    return {
        'label': label,
        'Top-1': top1/n, 'Top-3': top3/n, 'Top-5': top5/n, 'Top-10': top10/n,
        'MRR': rr_sum/n,
        'mean_gold_rank': (rank_sum/rank_count) if rank_count else float('nan'),
        'EM(force_single)': em/n,
        'mF1': f1_score(gm, pm, average='macro', zero_division=0),
        'wF1': f1_score(gm, pm, average='weighted', zero_division=0),
        'F32→F41': f32_to_f41,
        'F41→F32': f41_to_f32,
    }

def fmt_row(r, fields):
    return " ".join(f"{r[f]:>{w}.4f}" if isinstance(r[f], float) and not (r[f]!=r[f]) else f"{str(r[f]):>{w}}" for f,w in fields)

# ============================================================================
# L2-R1: Top-1 LOCKED, checker reranks rank 2-5
# ============================================================================
print("="*150)
print("L2-R1: Top-1 = Diagnostician[0] LOCKED. Reorder ranks 2-5 with various checker-aware strategies.")
print("="*150)

def make_ranker_locked_rerank(rerank_strategy):
    """Returns ranker function: case -> ranked parent list."""
    def ranker(c):
        diag = diag_ranked(c)
        if not diag: 
            primary = c.get('primary_diagnosis')
            return [parent(primary)]
        primary_code = diag[0]
        primary_p = parent(primary_code)
        rest = diag[1:]
        # Apply rerank strategy to rest
        if rerank_strategy == 'identity':
            reranked = rest
        elif rerank_strategy == 'met_ratio':
            mr = met_ratio(c)
            reranked = sorted(rest, key=lambda x: -mr.get(x, 0))
        elif rerank_strategy == 'decisive':
            reranked = sorted(rest, key=lambda x: -decisive(c, x))
        elif rerank_strategy == 'mean_evid_conf':
            reranked = sorted(rest, key=lambda x: -mean_evid_conf(c, x))
        elif rerank_strategy == 'composite':
            # 0.4 * met_ratio + 0.5 * decisive + 0.1 * mean_evid_conf
            mr = met_ratio(c)
            reranked = sorted(rest, key=lambda x: -(0.4*mr.get(x,0) + 0.5*decisive(c,x) + 0.1*mean_evid_conf(c,x)))
        elif rerank_strategy == 'confirmed_priority':
            # Items in confirmed_set come first, then by met_ratio
            conf = confirmed_set(c)
            mr = met_ratio(c)
            reranked = sorted(rest, key=lambda x: (-int(x in conf), -mr.get(x,0)))
        elif rerank_strategy == 'confirmed_priority_with_critA':
            # Items in confirmed_set + crit_A_met come first
            conf = confirmed_set(c)
            mr = met_ratio(c)
            reranked = sorted(rest, key=lambda x: (-(int(x in conf) + int(crit_A_met(c, x))), -mr.get(x,0)))
        else:
            reranked = rest
        # Build parent-collapsed ranked list (preserve primary first)
        all_codes = [primary_code] + reranked
        return to_parent_unique(all_codes)
    return ranker

strategies = [
    'identity (= Rule K, baseline)',
    'met_ratio',
    'decisive',
    'mean_evid_conf',
    'composite',
    'confirmed_priority',
    'confirmed_priority_with_critA',
]

# Compact column spec for printing
header = ['label', 'Top-1', 'Top-3', 'Top-5', 'Top-10', 'MRR', 'mean_gold_rank', 'F32→F41', 'F41→F32']
widths = [40, 7, 7, 7, 7, 7, 7, 8, 8]

print(f"\nDEV results (use to select best strategy):")
print(" ".join(f"{h:>{w}}" for h,w in zip(header,widths)))
print("-"*sum(widths)*2)
dev_results = {}
for s in strategies:
    key = s.split(' ')[0].replace(',','')
    fn = make_ranker_locked_rerank(key)
    r = evaluate_ranking(DEV, fn, s)
    dev_results[key] = r
    row = [r['label'][:40]] + [f"{r[k]:.4f}" if isinstance(r[k], float) else str(r[k]) for k in header[1:]]
    print(" ".join(f"{v:>{w}}" for v,w in zip(row,widths)))

# Composite scoring (Round 99 §5: focus on MRR + Top-3, since Top-1 locked)
def comp_R1(r):
    return 0.4*r['Top-3'] + 0.4*r['MRR'] + 0.2*r['Top-5']

best_R1 = max(dev_results.items(), key=lambda kv: comp_R1(kv[1]))
print(f"\nBest on DEV (composite=0.4*Top-3 + 0.4*MRR + 0.2*Top-5): {best_R1[0]} (composite={comp_R1(best_R1[1]):.4f})")

print(f"\nFROZEN TEST results:")
print(" ".join(f"{h:>{w}}" for h,w in zip(header,widths)))
print("-"*sum(widths)*2)
for s in strategies:
    key = s.split(' ')[0].replace(',','')
    fn = make_ranker_locked_rerank(key)
    r = evaluate_ranking(TEST, fn, s + (" ← BEST" if key == best_R1[0] else ""))
    row = [r['label'][:40]] + [f"{r[k]:.4f}" if isinstance(r[k], float) else str(r[k]) for k in header[1:]]
    print(" ".join(f"{v:>{w}}" for v,w in zip(row,widths)))

# ============================================================================
# L2-R2: Conservative veto sweep
# ============================================================================
print("\n" + "="*150)
print("L2-R2: Conservative veto. Override Diagnostician[0] only under very strict conditions.")
print("="*150)
print("\nVeto fires when ALL: (a) primary's met_ratio < margin_p; (b) alternative ∈ diag top-3;")
print("                     (c) alternative met_ratio = 1.0; (d) alternative crit_A met;")
print("                     (e) alternative decisive ≥ T_alt; (f) ICD-10 dominance OK.\n")

def make_ranker_veto(margin_p, T_alt, allow_dominance_only=False):
    def ranker(c):
        diag = diag_ranked(c)
        if not diag:
            primary = c.get('primary_diagnosis')
            return [parent(primary)]
        primary_code = diag[0]
        p_mr = met_ratio(c).get(primary_code, 0)
        primary_p = parent(primary_code)
        # Check veto conditions
        veto_target = None
        if p_mr < margin_p:
            for cand in diag[1:3]:  # only diag top-2/3 considered
                if cand == primary_code: continue
                cand_p = parent(cand)
                if cand_p == primary_p: continue
                if met_ratio(c).get(cand, 0) < 0.99: continue
                if not crit_A_met(c, cand): continue
                if decisive(c, cand) < T_alt: continue
                if not dom_ok(primary_p, cand_p, c): continue
                if allow_dominance_only:
                    # Only allow if cand strictly dominates primary
                    if not (cand_p in DOMINATES and primary_p in DOMINATES[cand_p]):
                        continue
                veto_target = cand
                break
        # Build final ranked list
        if veto_target is not None:
            ranked_codes = [veto_target] + [d for d in diag if d != veto_target]
        else:
            ranked_codes = list(diag)
        return to_parent_unique(ranked_codes)
    return ranker

# Sweep margin_p and T_alt
sweep_R2 = []
print(f"{'margin_p':>9} {'T_alt':>6} {'dom_only':>9} | {'DEV: Top-1':>10} {'Top-3':>7} {'MRR':>7} {'composite':>10} | {'TEST: Top-1':>11} {'Top-3':>7} {'MRR':>7} {'F32→F41':>8} {'F41→F32':>8}")
print("-"*150)
for margin_p in [0.3, 0.5, 0.7, 0.9, 1.1]:  # 1.1 = always trigger if other conditions met
    for T_alt in [0.7, 0.85, 0.95]:
        for dom_only in [False, True]:
            fn = make_ranker_veto(margin_p, T_alt, dom_only)
            dev_r = evaluate_ranking(DEV, fn, f"v(mp={margin_p},T={T_alt},dom={dom_only})")
            test_r = evaluate_ranking(TEST, fn, "")
            cs = 0.5*dev_r['Top-1'] + 0.3*dev_r['Top-3'] + 0.2*dev_r['MRR']
            sweep_R2.append((margin_p, T_alt, dom_only, cs, dev_r, test_r))
            print(f"{margin_p:>9.2f} {T_alt:>6.2f} {str(dom_only):>9} | {dev_r['Top-1']:>10.4f} {dev_r['Top-3']:>7.4f} {dev_r['MRR']:>7.4f} {cs:>10.4f} | {test_r['Top-1']:>11.4f} {test_r['Top-3']:>7.4f} {test_r['MRR']:>7.4f} {test_r['F32→F41']:>8} {test_r['F41→F32']:>8}")
best_R2 = max(sweep_R2, key=lambda x: x[3])
print(f"\nBest on DEV: margin_p={best_R2[0]}, T_alt={best_R2[1]}, dom_only={best_R2[2]} (composite={best_R2[3]:.4f})")
print(f"  → frozen TEST: Top-1={best_R2[5]['Top-1']:.4f}, Top-3={best_R2[5]['Top-3']:.4f}, MRR={best_R2[5]['MRR']:.4f}")

# Compare to no-veto reference
ref_no_veto = evaluate_ranking(TEST, make_ranker_locked_rerank('identity'), 'no veto = Rule K')
print(f"\nReference (no veto, Rule K identity rerank) on TEST:")
print(f"  Top-1={ref_no_veto['Top-1']:.4f}, Top-3={ref_no_veto['Top-3']:.4f}, MRR={ref_no_veto['MRR']:.4f}, F32→F41={ref_no_veto['F32→F41']}, F41→F32={ref_no_veto['F41→F32']}")
