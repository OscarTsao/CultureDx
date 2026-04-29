"""Cross-dataset replay (Round 101 §「Cross-dataset replay」).

Policies (4 minimum set):
  current   : current pipeline (primary_diagnosis + comorbid_diagnoses)
  R3-alpha  : Diagnostician[0] only (no comorbid)
  R3-beta   : Diagnostician[0] + strict gate (T_dec ≥ 0.85, dominance, crit A, in-confirmed)
  oracle    : gold-size-aware (upper bound)

Datasets × Modes:
  LingxiDiag-16K × {ICD-10, DSM-5, Both}
  MDD-5k        × {ICD-10, DSM-5, Both}
  Total = 6 prediction files

Metrics per (mode, policy):
  Top-1, Top-3, EM, mF1, wF1, F32→F41, F41→F32, F42_recall,
  comorbid_emit_rate, mean_pred_size, gold_size_dist
"""
import json, sys
from pathlib import Path
sys.path.insert(0, 'src')
from culturedx.eval.lingxidiag_paper import to_paper_parent, PAPER_12_CLASSES
import numpy as np
from sklearn.metrics import f1_score
from collections import defaultdict
from datetime import datetime

PRED_FILES = [
    ('LingxiDiag-16K', 'ICD-10', 'results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl'),
    ('LingxiDiag-16K', 'DSM-5',  'results/dual_standard_full/lingxidiag16k/mode_dsm5/pilot_dsm5/predictions.jsonl'),
    ('LingxiDiag-16K', 'Both',   'results/dual_standard_full/lingxidiag16k/mode_both/pilot_both/predictions.jsonl'),
    ('MDD-5k',        'ICD-10', 'results/dual_standard_full/mdd5k/mode_icd10/pilot_icd10/predictions.jsonl'),
    ('MDD-5k',        'DSM-5',  'results/dual_standard_full/mdd5k/mode_dsm5/pilot_dsm5/predictions.jsonl'),
    ('MDD-5k',        'Both',   'results/dual_standard_full/mdd5k/mode_both/pilot_both/predictions.jsonl'),
]

# Helpers
def _rco(c): return {it['disorder_code']: it for it in (c.get('decision_trace',{}).get('raw_checker_outputs',[]) or [])}
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

# Policies — return (primary_code, [comorbid_codes])
def policy_current(c):
    return c.get('primary_diagnosis'), c.get('comorbid_diagnoses') or []

def policy_R3_alpha(c):
    diag = diag_ranked(c)
    primary = diag[0] if diag else c.get('primary_diagnosis')
    return primary, []

def policy_R3_beta(c):
    diag = diag_ranked(c)
    primary = diag[0] if diag else c.get('primary_diagnosis')
    p = parent(primary)
    out = []
    for cand in diag[1:5]:
        if cand == primary: continue
        cp = parent(cand)
        if cp == p: continue
        if cand not in confirmed_set(c): continue
        if not dom_ok(p, cp, c): continue
        if not crit_A_met(c, cand): continue
        if decisive(c, cand) < 0.85: continue
        out.append(cand)
        if len(out) >= 1: break
    return primary, out

def policy_oracle(c):
    """Oracle: knows gold size; uses Diagnostician[0] as primary, emit comorbid only if gold is multi-label."""
    diag = diag_ranked(c)
    primary = diag[0] if diag else c.get('primary_diagnosis')
    gold = parent_set(c.get('gold_diagnoses') or [])
    if len(gold) <= 1:
        return primary, []
    # Pick oracle's best comorbid: any code in diag[1:5] whose parent is in gold
    for cand in diag[1:5]:
        if cand == primary: continue
        if parent(cand) != parent(primary) and parent(cand) in gold:
            return primary, [cand]
    # Fallback: original comorbid
    return primary, c.get('comorbid_diagnoses') or []

POLICIES = [
    ('current',  policy_current),
    ('R3-alpha', policy_R3_alpha),
    ('R3-beta',  policy_R3_beta),
    ('oracle',   policy_oracle),
]

def evaluate(cases, policy_fn):
    classes = PAPER_12_CLASSES
    cls_idx = {p:i for i,p in enumerate(classes)}
    n = len(cases)
    top1 = top3 = em = 0
    rr_sum = 0.0
    f32_to_f41 = 0
    f41_to_f32 = 0
    f42_in_gold = 0
    f42_recovered = 0
    pred_size_dist = defaultdict(int)
    gold_size_dist = defaultdict(int)
    multilabel_emits = 0
    gold_mat = np.zeros((n, len(classes)), dtype=int)
    pred_mat = np.zeros((n, len(classes)), dtype=int)
    
    for i, c in enumerate(cases):
        gold = parent_set(c.get('gold_diagnoses') or [])
        if not gold: gold = {'Others'}
        primary, comorbid = policy_fn(c)
        primary_p = parent(primary)
        comorbid_p = [parent(x) for x in comorbid]
        pred_set = set([primary_p] + comorbid_p) - {'Others'}
        if not pred_set: pred_set = {primary_p}
        
        if primary_p in gold: top1 += 1
        rk = diag_ranked(c)
        rp = []
        for r in rk:
            pp = parent(r)
            if pp != 'Others' and pp not in rp: rp.append(pp)
        top3_set = ([primary_p] + [r for r in rp if r != primary_p])[:3]
        if any(t in gold for t in top3_set): top3 += 1
        # MRR (full diag rank)
        for k, p in enumerate(rp):
            if p in gold: rr_sum += 1.0/(k+1); break
        if pred_set == gold: em += 1
        if 'F32' in gold and primary_p == 'F41': f32_to_f41 += 1
        if 'F41' in gold and primary_p == 'F32': f41_to_f32 += 1
        if 'F42' in gold:
            f42_in_gold += 1
            if 'F42' in pred_set: f42_recovered += 1
        for g in gold:
            if g in cls_idx: gold_mat[i, cls_idx[g]] = 1
        for p in pred_set:
            if p in cls_idx: pred_mat[i, cls_idx[p]] = 1
        pred_size_dist[len(pred_set)] += 1
        gold_size_dist[len(gold)] += 1
        if len(pred_set) >= 2: multilabel_emits += 1
    
    f42_recall = (f42_recovered / f42_in_gold) if f42_in_gold else float('nan')
    return {
        'N': n,
        'Top-1': top1/n,
        'Top-3': top3/n,
        'EM': em/n,
        'MRR': rr_sum/n,
        'mF1': float(f1_score(gold_mat, pred_mat, average='macro', zero_division=0)),
        'wF1': float(f1_score(gold_mat, pred_mat, average='weighted', zero_division=0)),
        'F32_to_F41': f32_to_f41,
        'F41_to_F32': f41_to_f32,
        'F42_in_gold': f42_in_gold,
        'F42_recovered': f42_recovered,
        'F42_recall': f42_recall,
        'multilabel_emit_rate': multilabel_emits/n,
        'gold_size_dist': dict(sorted(gold_size_dist.items())),
        'pred_size_dist': dict(sorted(pred_size_dist.items())),
    }

# Run replay
all_results = {}
for dataset, mode, path in PRED_FILES:
    if not Path(path).exists():
        print(f"MISSING: {dataset} {mode} {path}")
        continue
    cases = []
    with open(path) as f:
        for line in f: cases.append(json.loads(line))
    
    key = f"{dataset}_{mode}"
    all_results[key] = {'dataset': dataset, 'mode': mode, 'path': path, 'N': len(cases), 'policies': {}}
    for pol_name, pol_fn in POLICIES:
        r = evaluate(cases, pol_fn)
        all_results[key]['policies'][pol_name] = r

# Save raw JSON
out_dir = Path('results/sandbox')
out_dir.mkdir(parents=True, exist_ok=True)
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
out_json = out_dir / f'cross_dataset_replay_{ts}.json'
with open(out_json, 'w') as f:
    json.dump(all_results, f, indent=2, default=str)
print(f"Saved raw replay JSON: {out_json}\n")

# Print formatted tables
print("="*180)
print("CROSS-DATASET REPLAY — 6 mode/dataset × 4 policies")
print("="*180)

for key, data in all_results.items():
    print(f"\n--- {data['dataset']} × {data['mode']} (N={data['N']}) ---")
    print(f"  Source: {data['path']}")
    gold_dist = list(data['policies']['current']['gold_size_dist'].items())
    print(f"  Gold size dist: {gold_dist}")
    print()
    print(f"  {'Policy':<10} | {'Top-1':>7} {'Top-3':>7} {'EM':>7} {'MRR':>7} {'mF1':>7} {'wF1':>7} | {'F32→F41':>8} {'F41→F32':>8} {'F42_recall':>11} {'multi_emit':>11} | pred_size_dist")
    print(f"  {'-'*10}-+-{'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7}-+-{'-'*8} {'-'*8} {'-'*11} {'-'*11}-+-{'-'*30}")
    for pol_name in ['current', 'R3-alpha', 'R3-beta', 'oracle']:
        r = data['policies'][pol_name]
        f42_str = f"{r['F42_recall']:.4f}" if r['F42_in_gold'] > 0 else "n/a"
        print(f"  {pol_name:<10} | {r['Top-1']:>7.4f} {r['Top-3']:>7.4f} {r['EM']:>7.4f} {r['MRR']:>7.4f} {r['mF1']:>7.4f} {r['wF1']:>7.4f} | {r['F32_to_F41']:>8} {r['F41_to_F32']:>8} {f42_str:>11} {r['multilabel_emit_rate']:>11.4f} | {r['pred_size_dist']!s}")

# Summary table — Δ vs current per (mode, policy) for key metrics
print()
print("="*180)
print("DELTA SUMMARY — (R3-alpha vs current) per dataset/mode")
print("="*180)
print(f"\n{'Dataset':<15} {'Mode':<7} {'N':>4} | {'ΔTop-1':>8} {'ΔTop-3':>8} {'ΔEM':>8} {'ΔmF1':>8} {'ΔwF1':>8} | {'ΔF32→F41':>10} {'ΔF41→F32':>10} {'ΔF42_rec':>10}")
print("-"*180)
for key, data in all_results.items():
    cur = data['policies']['current']
    alpha = data['policies']['R3-alpha']
    f42_d = (alpha['F42_recall'] - cur['F42_recall']) if cur['F42_in_gold']>0 else float('nan')
    print(f"{data['dataset']:<15} {data['mode']:<7} {data['N']:>4} | "
          f"{alpha['Top-1']-cur['Top-1']:>+8.4f} {alpha['Top-3']-cur['Top-3']:>+8.4f} {alpha['EM']-cur['EM']:>+8.4f} "
          f"{alpha['mF1']-cur['mF1']:>+8.4f} {alpha['wF1']-cur['wF1']:>+8.4f} | "
          f"{alpha['F32_to_F41']-cur['F32_to_F41']:>+10} {alpha['F41_to_F32']-cur['F41_to_F32']:>+10} "
          f"{f42_d:>+10.4f}")

print()
print("="*180)
print("DELTA SUMMARY — (R3-beta vs current) per dataset/mode")
print("="*180)
print(f"\n{'Dataset':<15} {'Mode':<7} {'N':>4} | {'ΔTop-1':>8} {'ΔTop-3':>8} {'ΔEM':>8} {'ΔmF1':>8} {'ΔwF1':>8} | {'ΔF32→F41':>10} {'ΔF41→F32':>10}")
print("-"*180)
for key, data in all_results.items():
    cur = data['policies']['current']
    beta = data['policies']['R3-beta']
    print(f"{data['dataset']:<15} {data['mode']:<7} {data['N']:>4} | "
          f"{beta['Top-1']-cur['Top-1']:>+8.4f} {beta['Top-3']-cur['Top-3']:>+8.4f} {beta['EM']-cur['EM']:>+8.4f} "
          f"{beta['mF1']-cur['mF1']:>+8.4f} {beta['wF1']-cur['wF1']:>+8.4f} | "
          f"{beta['F32_to_F41']-cur['F32_to_F41']:>+10} {beta['F41_to_F32']-cur['F41_to_F32']:>+10}")

# Save markdown summary
md_path = out_dir / f'cross_dataset_replay_{ts}.md'
with open(md_path, 'w') as f:
    f.write(f"# Cross-Dataset Replay — {ts}\n\n")
    f.write("## 6-mode/dataset × 4-policy results\n\n")
    for key, data in all_results.items():
        f.write(f"### {data['dataset']} × {data['mode']} (N={data['N']})\n\n")
        f.write(f"Source: `{data['path']}`\n\n")
        f.write(f"Gold size dist: `{data['policies']['current']['gold_size_dist']}`\n\n")
        f.write("| Policy | Top-1 | Top-3 | EM | MRR | mF1 | wF1 | F32→F41 | F41→F32 | F42 recall | multi-emit |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for pol_name in ['current', 'R3-alpha', 'R3-beta', 'oracle']:
            r = data['policies'][pol_name]
            f42_str = f"{r['F42_recall']:.4f}" if r['F42_in_gold']>0 else "n/a"
            f.write(f"| {pol_name} | {r['Top-1']:.4f} | {r['Top-3']:.4f} | {r['EM']:.4f} | "
                    f"{r['MRR']:.4f} | {r['mF1']:.4f} | {r['wF1']:.4f} | "
                    f"{r['F32_to_F41']} | {r['F41_to_F32']} | {f42_str} | {r['multilabel_emit_rate']:.4f} |\n")
        f.write("\n")
print(f"\nSaved markdown summary: {md_path}")
