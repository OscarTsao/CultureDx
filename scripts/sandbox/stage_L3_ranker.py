"""Stage L3 — Learnable candidate-level ranker (CPU only).

Per Round 96 §9.1 + §10.L3:
  Per (case, candidate_disorder), build feature vector + binary label
  (is candidate's parent in gold_parents?).
  Train lightgbm/logistic on dev split, evaluate top-1 selection on test.

Goal: see if learnable rerank can push Top-1 above the diagnostician ceiling 0.524.
"""
import json, sys, random
sys.path.insert(0, 'src')
from culturedx.eval.lingxidiag_paper import to_paper_parent, PAPER_12_CLASSES
import numpy as np
from sklearn.metrics import f1_score
from sklearn.linear_model import LogisticRegression
from collections import defaultdict, Counter
import lightgbm as lgb

cases = []
with open('results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl') as f:
    for line in f: cases.append(json.loads(line))

random.seed(42)
indices = list(range(len(cases)))
random.shuffle(indices)
DEV_IDX = indices[:500]
TEST_IDX = indices[500:]
DEV = [cases[i] for i in DEV_IDX]
TEST = [cases[i] for i in TEST_IDX]
print(f"L3 setup: dev N={len(DEV)}, test N={len(TEST)}\n")

# === Helpers ===
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
    if not rco: return 0
    pc = rco.get('per_criterion', [])
    if not pc: return 0
    for cr in pc:
        if cr.get('criterion_id') == 'A': return int(cr.get('status') == 'met')
    return int(pc[0].get('status') == 'met')
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
def num_explicit_neg(c, code):
    rco = _rco(c).get(code)
    if not rco: return 0
    pc = rco.get('per_criterion', [])
    return sum(1 for cr in pc if cr.get('status') == 'not_met')
def num_unknown(c, code):
    rco = _rco(c).get(code)
    if not rco: return 0
    pc = rco.get('per_criterion', [])
    return sum(1 for cr in pc if cr.get('status') == 'insufficient_evidence')

DOMINATES = {'F33':['F32'],'F31':['F32','F33'],'F20':['F22','F32','F33','F31']}

# === Class prior from DEV
def compute_class_prior(cases_):
    cnt = Counter()
    total = 0
    for c in cases_:
        gold = parent_set(c.get('gold_diagnoses') or [])
        for g in gold:
            cnt[g] += 1
            total += 1
    return {k: v/total for k, v in cnt.items()}

class_prior = compute_class_prior(DEV)
parent_idx = {p: i for i, p in enumerate(PAPER_12_CLASSES)}

# === Build (case, candidate) feature matrix ===
def build_features(cases_, label_known=True):
    """For each case, generate one row per candidate disorder.
    Candidates = diag_ranked top-5 + confirmed_set + standalone met_ratio>=0.5 codes.
    """
    rows = []
    case_groups = []
    labels = []
    case_metas = []
    
    for case_idx, c in enumerate(cases_):
        rco = _rco(c)
        diag = diag_ranked(c)
        diag_rank_map = {code: i+1 for i, code in enumerate(diag)}
        confirmed = confirmed_set(c)
        gold = parent_set(c.get('gold_diagnoses') or [])
        
        # Candidate set: diag top-5 ∪ confirmed (full)
        cands = set(diag[:5]) | confirmed
        # Also include any disorder with met_ratio >= 0.99
        for code, item in rco.items():
            if item.get('met_ratio', 0) >= 0.99:
                cands.add(code)
        cands = list(cands)
        
        case_start = len(rows)
        for code in cands:
            rco_item = rco.get(code, {})
            mr = rco_item.get('met_ratio', 0.0)
            mc = rco_item.get('criteria_met_count', 0)
            ct = rco_item.get('criteria_total_count', 1)
            mean_conf = float(np.mean([cr.get('confidence',0) for cr in rco_item.get('per_criterion',[])])) if rco_item else 0
            
            feat = {
                'diag_rank': diag_rank_map.get(code, 6),  # 6 = not in top-5
                'diag_rank_inv': 6 - diag_rank_map.get(code, 6),
                'is_diag_top1': int(diag_rank_map.get(code, 6) == 1),
                'met_ratio': mr,
                'met_count': mc,
                'met_total': ct,
                'mean_criterion_conf': mean_conf,
                'decisive': decisive(c, code),
                'crit_A_met': crit_A_met(c, code),
                'in_confirmed': int(code in confirmed),
                'n_explicit_neg': num_explicit_neg(c, code),
                'n_unknown': num_unknown(c, code),
                'class_log_prior': np.log(class_prior.get(parent(code), 1e-3) + 1e-6),
                'n_confirmed_total': len(confirmed),
                'n_diag_total': len(diag),
            }
            # One-hot for parent
            for p in PAPER_12_CLASSES:
                feat[f'is_{p}'] = int(parent(code) == p)
            
            rows.append(feat)
            label = int(parent(code) in gold) if label_known else 0
            labels.append(label)
            case_metas.append({'case_idx': case_idx, 'code': code, 'parent': parent(code), 'gold': gold})
        
        case_groups.append((case_start, len(rows)))
    
    if not rows:
        return None, None, None, None
    feat_names = sorted(rows[0].keys())
    X = np.array([[r[k] for k in feat_names] for r in rows], dtype=float)
    y = np.array(labels)
    return X, y, case_groups, case_metas, feat_names

print("Building features...")
X_dev, y_dev, dev_groups, dev_meta, feat_names = build_features(DEV)
X_test, y_test, test_groups, test_meta, _ = build_features(TEST)
print(f"  dev:  X.shape={X_dev.shape}, positive rate={y_dev.mean():.4f}")
print(f"  test: X.shape={X_test.shape}, positive rate={y_test.mean():.4f}")
print(f"  features ({len(feat_names)}): {feat_names[:5]}...{feat_names[-5:]}")
print()

# ============================================================================
# Model 1: Logistic regression
# ============================================================================
print("="*100)
print("Model 1: Logistic regression (binary: is_gold_parent)")
print("="*100)
lr = LogisticRegression(max_iter=2000, C=1.0, class_weight='balanced')
lr.fit(X_dev, y_dev)
test_scores_lr = lr.predict_proba(X_test)[:, 1]

# Top-1 / Top-3 evaluation: for each case, pick top scored candidate
def evaluate_ranker(test_groups, test_meta, scores, label):
    n = len(test_groups)
    top1_correct = 0
    top3_correct = 0
    em_correct = 0
    pred_sizes = []
    
    pred_parents = []  # for F1
    gold_parents = []
    
    for ci, (start, end) in enumerate(test_groups):
        if start == end:
            pred_parents.append(set()); gold_parents.append(set()); continue
        case_scores = scores[start:end]
        case_meta = test_meta[start:end]
        order = np.argsort(-case_scores)
        ranked = [case_meta[i] for i in order]
        
        # parent-collapse top
        seen, top_parents = set(), []
        for m in ranked:
            if m['parent'] not in seen and m['parent'] != 'Others':
                seen.add(m['parent']); top_parents.append(m['parent'])
        gold = ranked[0]['gold']
        
        if top_parents and top_parents[0] in gold: top1_correct += 1
        if any(p in gold for p in top_parents[:3]): top3_correct += 1
        # Single-label EM (force single)
        if top_parents and {top_parents[0]} == gold: em_correct += 1
        
        pred_set = {top_parents[0]} if top_parents else set()
        pred_parents.append(pred_set)
        gold_parents.append(gold)
        pred_sizes.append(len(pred_set))
    
    # Build matrices for F1
    cls_idx = {p:i for i,p in enumerate(PAPER_12_CLASSES)}
    K = len(PAPER_12_CLASSES)
    pm = np.zeros((n, K), dtype=int)
    gm = np.zeros((n, K), dtype=int)
    for i, (ps, gs) in enumerate(zip(pred_parents, gold_parents)):
        for p in ps:
            if p in cls_idx: pm[i, cls_idx[p]] = 1
        for g in gs:
            if g in cls_idx: gm[i, cls_idx[g]] = 1
    
    return {
        'label': label,
        'Top-1': top1_correct/n,
        'Top-3': top3_correct/n,
        'EM(force_single)': em_correct/n,
        'mF1': f1_score(gm, pm, average='macro', zero_division=0),
        'wF1': f1_score(gm, pm, average='weighted', zero_division=0),
    }

r_lr = evaluate_ranker(test_groups, test_meta, test_scores_lr, "LogReg ranker")
print(f"  Top-1: {r_lr['Top-1']:.4f}  Top-3: {r_lr['Top-3']:.4f}  EM(force_single): {r_lr['EM(force_single)']:.4f}  mF1: {r_lr['mF1']:.4f}  wF1: {r_lr['wF1']:.4f}")

# Feature importance
coefs = lr.coef_[0]
print("\n  Feature importance (|coefficient|, top 12):")
order = np.argsort(-np.abs(coefs))
for i in order[:12]:
    print(f"    {feat_names[i]:<25}: {coefs[i]:+.4f}")
print()

# ============================================================================
# Model 2: LightGBM Ranker
# ============================================================================
print("="*100)
print("Model 2: LightGBM ranker (LambdaRank)")
print("="*100)

# group sizes
dev_group_sizes = [end-start for start, end in dev_groups]
test_group_sizes = [end-start for start, end in test_groups]

lgb_params = {
    'objective': 'lambdarank',
    'metric': 'ndcg',
    'ndcg_at': [1, 3],
    'learning_rate': 0.05,
    'num_leaves': 31,
    'min_child_samples': 5,
    'lambda_l2': 0.1,
    'verbosity': -1,
    'force_col_wise': True,
}
train_data = lgb.Dataset(X_dev, label=y_dev, group=dev_group_sizes)
ranker = lgb.train(lgb_params, train_data, num_boost_round=200)
test_scores_lgb = ranker.predict(X_test)

r_lgb = evaluate_ranker(test_groups, test_meta, test_scores_lgb, "LGBM Ranker")
print(f"  Top-1: {r_lgb['Top-1']:.4f}  Top-3: {r_lgb['Top-3']:.4f}  EM(force_single): {r_lgb['EM(force_single)']:.4f}  mF1: {r_lgb['mF1']:.4f}  wF1: {r_lgb['wF1']:.4f}")

# Feature importance
imp_split = ranker.feature_importance(importance_type='split')
imp_gain = ranker.feature_importance(importance_type='gain')
print("\n  Feature importance (gain, top 12):")
order = np.argsort(-imp_gain)
for i in order[:12]:
    print(f"    {feat_names[i]:<25}: gain={imp_gain[i]:>10.2f}  splits={imp_split[i]:>3}")
print()

# ============================================================================
# Model 3: LightGBM binary classifier (alternative formulation)
# ============================================================================
print("="*100)
print("Model 3: LightGBM binary classifier (treat as binary, not lambda-rank)")
print("="*100)
binary_params = {
    'objective': 'binary',
    'metric': 'binary_logloss',
    'learning_rate': 0.05,
    'num_leaves': 31,
    'min_child_samples': 5,
    'lambda_l2': 0.1,
    'verbosity': -1,
    'is_unbalance': True,
    'force_col_wise': True,
}
train_data2 = lgb.Dataset(X_dev, label=y_dev)
binary_clf = lgb.train(binary_params, train_data2, num_boost_round=200)
test_scores_bin = binary_clf.predict(X_test)
r_bin = evaluate_ranker(test_groups, test_meta, test_scores_bin, "LGBM Binary")
print(f"  Top-1: {r_bin['Top-1']:.4f}  Top-3: {r_bin['Top-3']:.4f}  EM(force_single): {r_bin['EM(force_single)']:.4f}  mF1: {r_bin['mF1']:.4f}  wF1: {r_bin['wF1']:.4f}")

# ============================================================================
# Reference baselines on the same TEST split
# ============================================================================
print("\n" + "="*100)
print("REFERENCE BASELINES (same TEST split, parent-level)")
print("="*100)

def evaluate_baseline_on_test(fn, label):
    n = len(TEST)
    classes = PAPER_12_CLASSES
    cls_idx = {c:i for i,c in enumerate(classes)}
    top1=top3=em=0
    gm = np.zeros((n, len(classes)), dtype=int)
    pm = np.zeros((n, len(classes)), dtype=int)
    
    for i, c in enumerate(TEST):
        gold = parent_set(c.get('gold_diagnoses') or [])
        if not gold: gold = {'Others'}
        primary, comorbid = fn(c)
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
        if pred_set == gold: em += 1
        for g in gold:
            if g in cls_idx: gm[i, cls_idx[g]] = 1
        for p in pred_set:
            if p in cls_idx: pm[i, cls_idx[p]] = 1
    return {
        'label': label,
        'Top-1': top1/n, 'Top-3': top3/n, 'EM': em/n,
        'mF1': f1_score(gm, pm, average='macro', zero_division=0),
        'wF1': f1_score(gm, pm, average='weighted', zero_division=0),
    }

bs_baseline = evaluate_baseline_on_test(lambda c: (c.get('primary_diagnosis'), c.get('comorbid_diagnoses') or []), 'Current pipeline')
bs_K = evaluate_baseline_on_test(lambda c: ((diag_ranked(c)[0] if diag_ranked(c) else c.get('primary_diagnosis')), []), 'Rule K (force single)')
print(f"  {bs_baseline['label']:<35}: Top-1={bs_baseline['Top-1']:.4f}  Top-3={bs_baseline['Top-3']:.4f}  EM={bs_baseline['EM']:.4f}  mF1={bs_baseline['mF1']:.4f}  wF1={bs_baseline['wF1']:.4f}")
print(f"  {bs_K['label']:<35}: Top-1={bs_K['Top-1']:.4f}  Top-3={bs_K['Top-3']:.4f}  EM={bs_K['EM']:.4f}  mF1={bs_K['mF1']:.4f}  wF1={bs_K['wF1']:.4f}")
print(f"  {'LR Ranker (L3)':<35}: Top-1={r_lr['Top-1']:.4f}  Top-3={r_lr['Top-3']:.4f}  EM={r_lr['EM(force_single)']:.4f}  mF1={r_lr['mF1']:.4f}  wF1={r_lr['wF1']:.4f}")
print(f"  {'LGBM Ranker (L3)':<35}: Top-1={r_lgb['Top-1']:.4f}  Top-3={r_lgb['Top-3']:.4f}  EM={r_lgb['EM(force_single)']:.4f}  mF1={r_lgb['mF1']:.4f}  wF1={r_lgb['wF1']:.4f}")
print(f"  {'LGBM Binary (L3)':<35}: Top-1={r_bin['Top-1']:.4f}  Top-3={r_bin['Top-3']:.4f}  EM={r_bin['EM(force_single)']:.4f}  mF1={r_bin['mF1']:.4f}  wF1={r_bin['wF1']:.4f}")
