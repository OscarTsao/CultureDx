# Round 150 Server-Side Prompts for Claude Code

These items cannot be tested in the chat sandbox. Run on user's RTX 5090 environment via Claude Code.

All prompts are READ-ONLY / SANDBOX in spirit. They produce evidence files. None modify production code, manuscript, or move tags. None merge or push by default.

---

## Prompt 2A — LLM re-prompt on ambiguous cases (~30 min GPU)

```
Round 150 — Tier 2A sandbox: LLM re-prompt at emission step on ambiguous cases.

GOAL: Test whether asking the LLM directly "is this case primary-only or primary+comorbid?" 
on ambiguous cases (where met_ratio gap < 0.05) outperforms hand-crafted heuristics.

This is a READ-ONLY policy probe. NO production code changes. NO new commit, NO push, NO tag.
Output: a single uncommitted markdown audit at 
  docs/paper/integration/GAP_E_TIER2A_REPROMPT_AUDIT.md

PRECONDITIONS
- Branch: feature/gap-e-beta2-implementation
- HEAD: 2c82f42
- vLLM running with Qwen3-32B-AWQ

STEP 1 — Identify ambiguous cases (CPU-only)
  Load existing predictions:
    results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl
    results/dual_standard_full/lingxidiag16k/mode_dsm5/pilot_dsm5/predictions.jsonl
    results/dual_standard_full/mdd5k/mode_icd10/pilot_icd10/predictions.jsonl
    results/dual_standard_full/mdd5k/mode_dsm5/pilot_dsm5/predictions.jsonl
  
  For each record, classify as ambiguous if:
    abs(met_ratio[primary] - met_ratio[rank2]) < 0.05
    AND rank2 in DOMAIN_PAIRS[primary]  (where DOMAIN_PAIRS includes F32:[F41], F41:[F32,F42], F42:[F41], F33:[F41], F51:[F32,F41], F98:[F41])
    AND rank2 in logic_engine_confirmed_codes
  
  Expected ambiguous count: ~50-150 cases per mode.

STEP 2 — Re-prompt LLM with 2-class classifier prompt
  For each ambiguous case, retrieve original case text from 
    LingxiDiag-16K dataset (id from case_id)
  
  Send vLLM prompt:
    """
    Given the following clinical case description, decide:
    
    CASE: {case_text}
    
    Is the most appropriate diagnosis:
    A) Primary only: {primary_code}
    B) Primary + comorbid: {primary_code} + {rank2_code}
    
    Respond with exactly "A" or "B", followed by a one-sentence justification.
    """
  
  Use --temperature 0 for determinism. Use the same vLLM server that ran round 114.
  Time budget: ~5-10 sec per case × ~600 ambiguous cases ≈ 30-60 min.

STEP 3 — Apply re-prompt verdict
  For each ambiguous case:
    if LLM verdict == "B": pred = {primary, rank2}
    if LLM verdict == "A": pred = {primary}  (= BETA-2b primary-only)
  Non-ambiguous cases: pred = {primary} (unchanged)

STEP 4 — Compute metrics on this re-prompt policy
  EM, F1, Precision, Recall, mgEM (multi-gold EM), mgR (multi-gold recall), 
  emit_rate, size_match — same metrics as sandbox audit.

STEP 5 — Write audit report
  docs/paper/integration/GAP_E_TIER2A_REPROMPT_AUDIT.md
  Sections:
    1. Setup — vLLM model, temperature, prompt template
    2. Ambiguous case statistics — count per mode, distribution of (primary, rank2) pairs
    3. LLM verdict distribution — % A vs B per mode
    4. Final metrics per mode (EM, F1, mgR, etc)
    5. Comparison vs BETA-2b primary-only and vs sandbox Combo (1B+1F)
    6. Verdict — does LLM judgment outperform hand-crafted gates?

HARD CONSTRAINTS
- No commit, no push, no tag movement, no merge
- Must run on existing checked-out vLLM model (no new model download)
- Must NOT modify hied.py / production code
- All outputs to outputs/ for user review BEFORE any commit decision
- Original predictions on disk remain untouched (read-only)

RETURN
- Audit file path
- Summary table (≤30 lines):
    ambiguous case count per mode
    LLM verdict A/B split per mode
    final metrics per mode
    comparison vs BETA-2b
- Total wall time
```

---

## Prompt 2B — Hierarchical primary+comorbid LLM prompt (5-7 hr GPU)

```
Round 150 — Tier 2B sandbox: Hierarchical primary+comorbid LLM prompt.

GOAL: Run a fresh canonical evaluation with Diagnostician prompt modified to ask 
for primary + (optional) comorbid in one shot, instead of ranked top-5 + post-hoc emission.

This is HIGH-COST: 5-7 hr GPU canonical rerun. Run only after lower-cost options 
have been evaluated and rejected. Do NOT run by default.

PRECONDITIONS
- Branch: feature/gap-e-beta2-implementation, NEW sub-branch tier2b/hierarchical-prompt
- vLLM running with Qwen3-32B-AWQ
- Disk space: ~500 MB for new prediction artifacts

STEP 1 — Branch off
  git checkout -b tier2b/hierarchical-prompt feature/gap-e-beta2-implementation

STEP 2 — Modify Diagnostician prompt (one targeted change)
  Edit prompts file (likely src/culturedx/modes/hied.py or src/culturedx/prompts/diagnostician.py)
  
  OLD prompt (single-label):
    "Output the most likely diagnosis as ICD-10 code."
  
  NEW prompt:
    "Output diagnosis as JSON:
       {{
         "primary": "<single most likely ICD-10 code>",
         "comorbid": "<optional second ICD-10 code if strongly indicated, else null>"
       }}
    
    Only include comorbid if the patient clearly has a second distinct disorder 
    in addition to the primary. Do not include comorbid if the case is single-disorder."
  
  Update parsing to extract primary + comorbid from JSON response.

STEP 3 — Run canonical evaluation (6 modes)
  Use scripts/run_canonical_eval.py or auto_chain.sh equivalent
  Sequential or parallel per round 114 lessons
  Total time: ~7 hr (sequential LingxiDiag) + ~2 hr (parallel MDD) = ~9 hr realistic

STEP 4 — Compute metrics
  Same evaluation contract as round 114
  EM, F1, P, R, mgEM, mgR, emit_rate, size_match

STEP 5 — Compare to BETA-2b + Combo
  Three-way: BETA-2b vs Combo (1B+1F) vs hierarchical prompt
  Note: hierarchical prompt is the only one with no DOMAIN_PAIRS hardcoding
  
STEP 6 — Audit report
  docs/paper/integration/GAP_E_TIER2B_HIERARCHICAL_AUDIT.md
  Sections: setup, prompt diff, canonical metrics, comparison, verdict.

HARD CONSTRAINTS
- New branch tier2b/hierarchical-prompt; not on feature/gap-e-beta2-implementation directly
- 7-9 hr GPU is significant cost — confirm GPU availability before starting
- Outputs to outputs/ for review before any merge or tag
- BETA-2b feature branch HEAD must remain at 2c82f42
- paper-integration-v0.1 tag must remain at c3b0a46

DECISION TRIGGER
This is high-cost. Run ONLY if user explicitly triggers:
  "Run Tier 2B hierarchical prompt canonical evaluation"

RETURN
- Branch SHA after run
- Audit file path
- 3-way comparison table (≤30 lines)
- Total GPU wall time
```

---

## Prompt 2D — Two-stage classifier (1-2 hr CPU)

```
Round 150 — Tier 2D sandbox: Train two-stage emission classifier.

GOAL: Train a separate classifier on dev split that predicts emission decision 
(emit comorbid yes/no) given case features. Apply at inference to gate emission 
without GPU rerun.

This is CPU-only ~1-2 hr training. Sandbox-friendly. Single audit output.

PRECONDITIONS
- Branch: feature/gap-e-beta2-implementation
- HEAD: 2c82f42
- Python env with sklearn / lightgbm available
- Dev split on disk (LingxiDiag-16K full set, NOT just N=1000 pilot)

STEP 1 — Define features per case (CPU-only)
  Per record, extract from decision_trace:
    primary_met_ratio: met_ratio[primary]
    rank2_met_ratio: met_ratio[ranked[1]]
    rank3_met_ratio: met_ratio[ranked[2]]
    primary_in_confirmed: bool
    rank2_in_confirmed: bool
    rank2_in_pair: bool (rank2 in DOMAIN_PAIRS[primary])
    confirmed_count: len(confirmed_set)
    veto_applied: bool
    case_text_len: len(input case text) (cross-ref dataset)
    diagnostician_confidence: from confidence field
    primary_class: one-hot (F32, F33, F41, F42, F51, F98, ...)
    cross_mode_agree: bool (ICD-10 primary == DSM-5 primary)

STEP 2 — Generate training labels
  For each case, label = 1 if gold_size > 1 else 0
  Imbalanced: 91% label=0, 9% label=1
  Use class weights or SMOTE.

STEP 3 — Train/dev/test split
  Use existing dataset splits from docs/paper/repro/
  If no explicit dev split, use 70/15/15 stratified.

STEP 4 — Train binary classifier
  LightGBM or LogisticRegression
  Class weights: balanced or class_weight={0: 1, 1: 10}
  Hyperparameter sweep: ~30 configurations
  Pick model with best dev F1 on label=1 (multi-gold)

STEP 5 — Apply at inference
  For each test case:
    if classifier_predict(features) == 1:
      pred = {primary, rank2_from_pair_and_confirmed}  (Combo-style emission)
    else:
      pred = {primary}  (BETA-2b primary-only)

STEP 6 — Evaluate on test split
  EM, F1, P, R, mgEM, mgR, emit_rate
  Compare vs BETA-2b, Combo (1B+1F), per-class threshold (1E)

STEP 7 — Report
  docs/paper/integration/GAP_E_TIER2D_CLASSIFIER_AUDIT.md
  Sections:
    1. Feature engineering
    2. Class imbalance handling
    3. Hyperparameter sweep results
    4. Best model performance on dev/test
    5. Comparison vs sandbox candidates (Combo, 1B-α, BETA-2b)
    6. Feature importance — which signals matter for emission decision?
    7. Verdict — does learned model outperform hand-crafted gates?

HARD CONSTRAINTS
- CPU-only, ~1-2 hr
- No production code change — classifier output applied externally
- No commit, no tag, no push
- Outputs to outputs/ for review

RETURN
- Audit file path
- Hyperparameter sweep summary (≤20 lines)
- Best model metrics
- Feature importance ranking (top 5)
- Comparison vs sandbox candidates
```

---

## Combined trigger — run all three sequentially

```
Round 150+ — Run Tier 2A → Tier 2D → (optionally) Tier 2B in sequence.

Sequencing rationale:
  - 2A first (~30-60 min): cheapest, tests LLM judgment
  - 2D second (~1-2 hr CPU): tests learned model
  - 2B last (~7-9 hr GPU): only if 2A and 2D verdicts unclear

Each produces a separate audit file. After all three:
  - Decision: which policy (sandbox Combo, 2A re-prompt, 2D classifier, 2B hierarchical) 
    to adopt for paper-integration-v0.2.
  - User makes Q1/Q2/Q3 verdicts only after all audits complete.

Branch hygiene:
  - 2A and 2D run on feature/gap-e-beta2-implementation (existing branch)
  - 2B uses new branch tier2b/hierarchical-prompt
  - paper-integration-v0.1 tag never moved
  - main-v2.4-refactor never modified
  - All outputs to /mnt/user-data/outputs/ first for review
```
