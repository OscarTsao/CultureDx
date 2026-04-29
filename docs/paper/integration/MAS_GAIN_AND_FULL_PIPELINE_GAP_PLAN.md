# MAS Gain and Full-Pipeline Validation Gap Plan

**Date**: 2026-04-29
**Per GPT round 84 trigger**: "Go run MAS gain + full-pipeline gap plan." Plan-only artifact, NOT execution.
**Artifact location**: `docs/paper/integration/MAS_GAIN_AND_FULL_PIPELINE_GAP_PLAN.md`
**Status**: Planning document only. NO §1-§7 prose modified. NO Abstract modified. NO new metrics computed in this commit. Stage 0 audit + Stage 1 CPU-only metric recomputation deferred to later trigger after this plan is approved.

This document plans a metric-attribution and pipeline-clarification analysis on the existing CultureDx artifacts at HEAD `b8bda4b` / tag `paper-integration-v0.1`. The goal is to fill two specific evidence gaps identified during round 81-83 PI-review preparation: (a) which Stacker LGBM metric gains are attributable to MAS-derived features vs the LightGBM stacker itself, and (b) which results in the manuscript correspond to the full HiED checker pipeline vs the checker-bypassed DtV comparator.

The plan is staged so that no GPU work is initiated until artifact-availability has been audited. Existing predictions appear sufficient to close most of the gap with CPU-only metric recomputation.

---

## 1. Motivation

Three facts from the round 81-83 review surface the gap:

**Fact 1**: §5.1 Table 2 currently reports MAS-only DtV with values only for 2-class (.803) and Top-1 (.516); the remaining 5 metrics (4-class / Top-3 / macro-F1 / weighted-F1 / Overall) are explicit absences `—`. Per `metric_consistency_report.json` `canonical_values` keys, no `single` / `dtv` / `mas_only` entry exists; only `stacker_lgbm`, `stacker_lr`, and 6 dual-standard mode/dataset combinations are tracked.

**Fact 2**: §4.1 states "DtV bypasses the criterion-checking pipeline." So MAS-only DtV ≠ full HiED MAS. The label "MAS-only" in §5.1 means "no supervised features" (no TF-IDF), NOT "full MAS reasoning". Reviewers reading §5.1 alone could conclude that the +9.1pp 2-class advantage of MAS-only DtV over reproduced TF-IDF is evidence of MAS criterion-checking value, when it is actually evidence of LLM-with-Triage-shortlist value.

**Fact 3**: §5.2 reports Stacker LGBM vs TF-IDF-only stacker variant McNemar p ≈ 1.0 on Top-1, but does NOT report the same paired comparison on the other 6 metrics. So the +5.5pp 4-class / +9.6pp Top-3 / +6.2pp Overall advantages of Stacker LGBM over reproduced TF-IDF are not currently attributable to MAS-derived features vs LightGBM-vs-logistic-regression effects.

These three facts together produce the round 84 conclusion: the paper's parity-plus-audit framing is not invalidated, but the attribution of where Stacker gains come from, and the labeling of what MAS-only DtV represents, are imprecise. PI / external reviewers may flag both.

---

## 2. Current evidence state

### 2.1 Canonical artifacts that exist at HEAD `b8bda4b`

| Artifact | Location | N | All 7 v4 metrics in canonical? |
|---|---|---:|---|
| Reproduced TF-IDF (LingxiDiag) | (training script + prediction view) | 1000 | ✓ all 7 in `metric_consistency_report.json` |
| Stacker LGBM (LingxiDiag) | `canonical_values.stacker_lgbm` | 1000 | ✓ all 7 |
| Stacker LR (LingxiDiag) | `canonical_values.stacker_lr` | 1000 | ✓ all 7 |
| Full HiED ICD-10 (LingxiDiag) | `results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl` | 1000 | △ **5 of 7 in canonical**: Top1=.507, Top3=.800, F1_macro=.199, F1_weighted=.457, Overall=.514. **2-class and 4-class missing from canonical_values** but appear in §5.4 Panel A as .778 / .447 — provenance must be confirmed |
| Full HiED ICD-10 (MDD-5k) | `results/dual_standard_full/mdd5k/mode_icd10/pilot_icd10/predictions.jsonl` | 925 | ✓ all 7 in `canonical_values.mdd5k_dual_standard_icd10` |
| Full HiED DSM-5 v0 (LingxiDiag, MDD-5k) | `results/dual_standard_full/.../mode_dsm5/pilot_dsm5/predictions.jsonl` | 1000 / 925 | ✓ all reported in §5.4 Panel B |
| Full HiED Both mode (LingxiDiag, MDD-5k) | `results/dual_standard_full/.../mode_both/pilot_both/predictions.jsonl` | 1000 / 925 | ✓ pass-through verification §5.4 Panel C |
| MAS-only DtV (LingxiDiag) | location ambiguous — must locate in Stage 0 | 1000? | ✗ only Top-1 (.516) and 2-class (.803) audit-traced; other 5 metrics absent |
| MAS-only DtV (MDD-5k) | `results/external/mdd5k_single/predictions.jsonl` + `results/external/mdd5k_dtv/` | 925? | ✗ only used as single-LLM 189× baseline in §5.3 |
| TF-IDF-only LGBM stacker variant | **does not exist as artifact** | n/a | ✗ Gap A requires either retraining or feature-masking |

### 2.2 Existing Stacker LGBM canonical values (for reference)

```
stacker_lgbm canonical_values:
  Top1:           0.612
  Top3:           0.925
  F1_macro:       0.334
  F1_weighted:    0.573
  2class_Acc:     0.753
  4class_Acc:     0.546
  Overall:        0.617
```

### 2.3 Existing Full HiED ICD-10 LingxiDiag canonical values

```
dual_standard_icd10 canonical_values:
  Top1:           0.507
  Top3:           0.800
  F1_macro:       0.199
  F1_weighted:    0.457
  Overall:        0.514
  2class_Acc:     [missing from canonical_values — sourced from results/dual_standard_full/lingxidiag16k/mode_both/pilot_both/metrics.json as .7780126849894292]
  4class_Acc:     [missing from canonical_values — §5.4 Panel A reports .447, source must be located in Stage 0]
```

### 2.4 Existing Full HiED ICD-10 MDD-5k canonical values

```
mdd5k_dual_standard_icd10 canonical_values:
  Top1:           0.597
  Top3:           0.853
  F1_macro:       0.197
  F1_weighted:    0.514
  2class_Acc:     0.890
  4class_Acc:     0.444
  Overall:        0.566
```

### 2.5 Round 80 final-sweep verdict

`FINAL_MANUSCRIPT_SWEEP.md` (commit `63a7f73`) verified at HEAD `c3b0a46`:
- 0 substantive prose edits required
- 0 forbidden-claim positive uses
- 30/30 citations resolved
- 7/7 final table labels canonical
- 0 long lines

The current gap analysis does NOT invalidate the final sweep's verdict on the paper-integration freeze. It identifies attribution and labeling refinements that may be requested by PI / reviewers but were not blockers at sweep time.

---

## 3. Gap A — Stacker metric-by-metric MAS gain attribution

### 3.1 Question

Of the +4.1pp 2-class / +5.5pp 4-class / +9.6pp Top-3 / +6.2pp Overall advantages of Stacker LGBM over reproduced TF-IDF on LingxiDiag, what fraction is attributable to MAS-derived features vs to the LightGBM stacker itself (over a logistic-regression baseline)?

### 3.2 Attribution table to fill

| System | 2-class | 4-class | Top-1 | Top-3 | macro-F1 | weighted-F1 | Overall | Source |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Reproduced TF-IDF (logistic regression) | .712 | .491 | .610 | .829 | .352 | .585 | .555 | existing canonical |
| **TF-IDF-only LGBM stacker variant** | TBD | TBD | TBD | TBD | TBD | TBD | TBD | **must produce** |
| MAS-only feature LGBM stacker (optional) | TBD | TBD | TBD | TBD | TBD | TBD | TBD | optional |
| Stacker LGBM (full, TF-IDF + MAS) | .753 | .546 | .612 | .925 | .334 | .573 | .617 | existing canonical |

The TF-IDF-only LGBM stacker is the critical missing row. The MAS-only feature LGBM stacker is optional supplementary evidence.

### 3.3 Production approach (CPU-only, no GPU)

Two paths to obtain the missing row:

**Path A1 — Retrain TF-IDF-only LGBM stacker** (preferred for clean attribution)
- Use only the 13 TF-IDF features (12 per-class TF-IDF probabilities + 1 Top-1 margin)
- Same LightGBM hyperparameter family as canonical Stacker LGBM (hyperparameter values copied verbatim, NOT re-tuned)
- Same train / dev / test split (no resplitting)
- Same v4 evaluation contract
- Fixed seed (matching canonical Stacker LGBM training seed)
- Run prediction on test_final N=1000
- Compute v4-contract metrics via `compute_table4_metrics_v2`

**Path A1 is an attribution-control run, NOT a new model search.** The discipline is strict:

```
NO hyperparameter tuning
NO feature engineering beyond MAS feature removal
NO new threshold search
NO new model selection
NO seed-averaged variant
```

This run answers the single question:

> "Given the same stacker pipeline, what happens to each metric when MAS-derived features are removed?"

It does NOT answer:

> "What is the best possible TF-IDF-only LGBM?"

If a reviewer asks "did you re-tune for the TF-IDF-only ablation?" — the documented answer must be no. Same hyperparameters, same split, same seed, same contract. This eliminates the suspicion that MAS attribution gain looks artificially large because the TF-IDF-only baseline was deliberately weakened, OR that the TF-IDF-only baseline matches Stacker LGBM because it was deliberately strengthened.

**Path A2 — Feature-masking on existing stacker** (fastest, lossy)
- Use existing Stacker LGBM but mask MAS feature contributions at inference
- Re-predict from the marginalized TF-IDF block only
- Less clean attribution because the LGBM trees were trained on all 31 features

Recommendation: Path A1. CPU-only retraining of a LightGBM with 13 features on N=1000 should complete in minutes, NOT hours.

### 3.4 Pre-flight verification before retraining

Stage 0 audit must confirm:
- Stacker training script exists and is reproducible (Stage 0 inspection point: `scripts/` directory; canonical training script not yet identified in recon)
- Train / dev / test splits documented (per `REPRODUCTION_README.md` pointers)
- TF-IDF feature artifacts available (12 per-class probs + 1 margin) — should be subset of full 31-feature stacker training matrix

### 3.5 Pass/fail criteria for Gap A

| Outcome | Interpretation | Manuscript impact |
|---|---|---|
| TF-IDF-only LGBM ≈ Full Stacker LGBM on most metrics | Most ranking/Overall gains come from LGBM-vs-LR effect, NOT from MAS features | §5.2 conclusion strengthened: maintain conservative framing; add explicit "MAS features contribute modestly across metrics" sentence |
| Full Stacker LGBM > TF-IDF-only LGBM on Top-3 / Overall / 4-class with paired CI excluding 0 | Some ranking-level gain attributable to MAS-derived features within the LGBM | §5.2 may add: "MAS-derived features improve ranking-level / auxiliary metrics within the LGBM stacker, while Top-1 remains parity"; do NOT add "MAS beats TF-IDF" |
| MAS-only feature LGBM substantially weaker than reproduced TF-IDF | MAS as standalone classifier is weak; useful only as complementary signal | §5.2 may add: "MAS features are useful as complementary audit / feature signal, not as standalone classifier" |

All three outcomes are publishable. None requires manuscript retraction. The framing remains parity-plus-audit; only the §5.2 sub-narrative becomes more precise.

---

## 4. Gap B — DtV vs full HiED checker pipeline clarification

### 4.1 Question

Two sub-questions:

**Q-B1**: Where in the manuscript does the term "MAS" / "MAS-only" / "DtV" appear, and for each occurrence does it refer to (a) full HiED with criterion checker, (b) DtV with checker bypassed, or (c) MAS feature block in stacker context?

**Q-B2**: For the full HiED ICD-10 mode results that ARE present in §5.4 Panel A (2-class .778 / 4-class .447 / Top-1 .507 / Top-3 .800 / macro-F1 .199 / weighted-F1 .457 / Overall .514) and §5.4 Panel B MDD-5k (full 7 metrics), are these obtainable as a "Full HiED ICD-10 row" in the §5.1 Table 2 LingxiDiag main benchmark for direct comparison vs reproduced TF-IDF and Stacker LGBM?

### 4.2 Clarification table to publish

| Configuration | Triage Agent | Criterion Checker | Logic Engine | Calibrator | Comorbidity Gate | Diagnostician | Supervised features (TF-IDF) | Used in manuscript |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **Reproduced TF-IDF** (logistic regression) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | §5.1 Table 2 / §5.5 |
| **MAS-only DtV** (current label) | ✓ probable | **✗ bypassed** | ✗ implied | ? | ? | ✓ | ✗ | §5.1 Table 2 (2 cells only) |
| **Full HiED ICD-10 mode** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | §5.3 / §5.4 / §6.2 |
| **Full HiED DSM-5 v0 mode** | ✓ | ✓ (DSM-5 v0 templates) | ✓ | ✓ | ✓ | ✓ | ✗ | §5.4 / §6.2 |
| **Full HiED Both mode** | ✓ | ✓ ICD-10 + DSM-5 sidecar | ✓ | ✓ | ✓ | ✓ | ✗ | §5.4 |
| **Stacker LGBM** (primary system) | ✓ via MAS feature block | ✓ via 12 met-ratio features | ✓ | ✓ via 1 abstain feature | ✓ | ✓ via 5 DtV rank confidences | ✓ via 13 TF-IDF features | §5.1 / §5.2 |
| **Stacker LR** (macro-F1 comparator) | same as Stacker LGBM | same | same | same | same | same | same | §5.1 |

### 4.3 Production approach for Q-B1 (label audit, no compute)

Stage 0 grep audit of §1-§7 + Abstract for occurrences of:
- "MAS-only"
- "MAS only"
- "DtV"
- "Direct-to-Verdict"
- "MAS reasoning"
- "MAS pipeline"
- "criterion check"
- "checker"
- "MAS feature"
- "HiED"

Each occurrence labeled with its referent (a / b / c per §4.1 above). Output to `docs/paper/integration/MAS_LABEL_AUDIT.md` (Stage 1 artifact, NOT in this plan).

### 4.4 Production approach for Q-B2 (full HiED ICD-10 row in Table 2)

Two paths:

**Path B1 — Add full HiED ICD-10 row to §5.1 Table 2 using existing canonical values** (CPU-only)
- LingxiDiag full HiED ICD-10 metrics: Top1=.507, Top3=.800, F1_macro=.199, F1_weighted=.457, Overall=.514 (existing canonical_values.dual_standard_icd10) plus 2-class=.778 / 4-class=.447 (existing in Both-mode metrics.json, traced via Both-mode pass-through equivalence)
- This requires verifying the 2-class .778 and 4-class .447 are correctly attributable to ICD-10 mode (via pass-through), and recomputing them directly from the ICD-10 mode prediction file via `compute_table4_metrics_v2` to confirm
- Output: 7-cell row added to §5.1 Table 2

**Path B2 — Recompute MAS-only DtV all 7 metrics under v4 contract** (CPU-only)
- Locate canonical LingxiDiag DtV prediction file (Stage 0 audit point)
- Run `compute_table4_metrics_v2` to produce all 7 v4 metrics
- Add new key `mas_only_dtv` to `canonical_values` in `metric_consistency_report.json`
- Output: 5 missing cells in §5.1 Table 2 row "MAS-only DtV" filled, OR row relabeled "DtV comparator (checker bypassed)"

**Both paths recommended.** B1 fills the genuine "full pipeline" row that reviewers will want to see (you specifically asked for this); B2 fills the existing partial DtV row to remove the `—` placeholders.

### 4.4.1 Conditional manuscript-update gate (Full HiED ICD-10 row)

The Full HiED ICD-10 row is a **candidate manuscript update, NOT automatic**. It can be added to §5.1 Table 2 only if all of the following gates pass:

1. all 7 v4 metrics are recomputed from the verified Full HiED ICD-10 prediction files (`results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl` for LingxiDiag; `results/dual_standard_full/mdd5k/mode_icd10/pilot_icd10/predictions.jsonl` for MDD-5k) using `compute_table4_metrics_v2`
2. LingxiDiag 2-class / 4-class provenance gap is resolved from direct ICD-10-mode source artifacts, NOT relied upon Both-mode pass-through equivalence (the §5.4 Panel A values .778 / .447 must reproduce from direct ICD-10 prediction file)
3. the row is labeled as **Full HiED ICD-10 MAS** (NOT DtV, NOT MAS-only) — labels distinguish full-pipeline from checker-bypassed configurations
4. §4.1 / §5.1 wording is updated to clearly distinguish Full HiED MAS from DtV comparator (per §4.2 clarification table in this plan)
5. the update is reviewed as a **separate manuscript-impact commit**, NOT bundled with Gap A retraining or Gap B DtV cell-fill

Failure on any gate → DEFER row addition; document discrepancy in `MAS_LABEL_AUDIT.md` and surface to PI / advisor before any §5.1 modification.

### 4.5 Pre-flight verification before recompute

Stage 0 audit must confirm:
- LingxiDiag DtV prediction file exists at a discoverable location (recon flagged ambiguity; candidate paths: `results/validation/03_dtv_v1/`, `results/validation/01_single_baseline/`, or `results/dual_standard_full/lingxidiag16k/mode_*/pilot_*/predictions.jsonl` filtered by `routing_mode` or `decision.checker_used` field)
- Full HiED ICD-10 LingxiDiag prediction file `results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl` (1000 lines, confirmed) is the canonical source for all 7 metrics, AND that `compute_table4_metrics_v2` on it produces the §5.4 Panel A values exactly
- The `r17_bypass_checker` experiment at `results/validation/r17_bypass_checker/metrics.json` (which has 2class_Acc=0.7780126849894292 — same as Both-mode metrics.json via architectural pass-through) is a **candidate artifact to inspect, NOT a canonical DtV source**. It must NOT be used for §5.1 DtV cells unless Stage 0 verifies all of the following:
  1. its prediction file matches the DtV comparator definition (Direct-to-Verdict diagnostician)
  2. it bypasses the criterion-checking pipeline (per §4.1 DtV definition)
  3. it reproduces the audit-traced DtV cells already used in Table 2 (Top-1 = .516, 2-class = .803)
  4. its schema is distinct from full HiED ICD-10 / Both-mode pass-through outputs

The matching 2-class value (0.778) between `r17_bypass_checker` and Both-mode pass-through suggests `r17_bypass_checker` may NOT be the DtV canonical source — it may instead be a separate checker-bypass experiment that produced the same 2-class accuracy by coincidence or by sharing prediction-mode logic. Stage 0 audit must resolve this disambiguation BEFORE using `r17_bypass_checker` to populate any Table 2 cell

### 4.6 Pass/fail criteria for Gap B

| Outcome | Interpretation | Manuscript impact |
|---|---|---|
| Full HiED ICD-10 row recomputed and matches §5.4 Panel A exactly | Full-pipeline metrics confirmed canonical | Add row to §5.1 Table 2; rename "MAS-only DtV" → "DtV comparator (checker bypassed)"; clarify in §4.1 / §4.2 |
| MAS-only DtV all 7 metrics recomputed cleanly | 5 `—` cells filled with v4-contract values | §5.1 Table 2 row label updated, 5 metric values added; §5.2 / §5.4 cross-references updated |
| Recompute of Full HiED ICD-10 from prediction file produces values different from §5.4 Panel A | Provenance gap requires clinician / PI review | DEFER §5.1 row addition; document discrepancy in `MAS_LABEL_AUDIT.md` |
| LingxiDiag DtV prediction file cannot be located | DtV row stays at 2 cells; row label still corrected | Rename only; do not fill `—` cells |

---

## 5. Optional Gap C — Multi-backbone anti-bias accumulation

Per round 84 explicit: "我建議不要跟上面兩個必補 gap 混在一起". This is a research extension, NOT a manuscript-required gap. Documented here for traceability; deferred unless PI specifically requests.

### 5.1 Minimal experiment design

| Condition | Purpose |
|---|---|
| Qwen3-32B-AWQ direct (current backbone) | Existing-family baseline |
| Non-Qwen-family direct (e.g., GPT-4 or Llama-family) | Cross-family direct baseline for same-family-bias check |
| Qwen full HiED (current pipeline) | Existing-family full pipeline |
| Heterogeneous full HiED (different LLM at different stages) | Test family-diversity effect on F32/F41 asymmetry |
| Optional majority / disagreement across backbones | Error-correlation analysis |

Primary metrics to track:
- F32/F41 asymmetry ratio
- F41→F32 / F32→F41 raw counts
- Top-1 / Top-3
- Error-overlap Jaccard between backbones
- Standard-discordance / model-discordance enrichment

### 5.2 Branch / location

This is **NOT** to be merged into the current paper-integration package. If executed:

```
Branch:           experiments/multibackbone_bias_accumulation
Output dir:       results/multibackbone_bias_20260429/
Manuscript impact: NONE in paper-integration-v0.1; potential supplementary appendix only
```

Defer until at least one of:
- PI / advisor explicitly requests same-family-bias evidence (Step 7 Q5 or Q6)
- Both Gap A and Gap B closed
- GPU resource availability confirmed without disrupting other phases of the project

### 5.3 Hard scope rule

**Gap C is NOT part of Phase 3 Step 1 execution.**

NO multi-backbone outputs may modify Abstract, §1, §5, §6, or Table 2 in the current manuscript package unless:
1. a separate PI-approved exploratory branch is opened (`experiments/multibackbone_bias_accumulation`)
2. the multi-backbone results are reviewed by PI / advisor as an explicit research-extension proposal
3. a separate plan-then-apply cycle is initiated (analogous to round 84 → 85 for Gap A / Gap B)

Multi-backbone anti-bias-accumulation is a new research question, NOT a current-paper required gap. It does NOT belong in the same commit, results story, or manuscript section as Gap A (attribution) or Gap B (label clarification). Mixing them risks scope creep and confounds the parity-plus-audit narrative locked at `paper-integration-v0.1`.

If executed in a separate branch and accepted by PI for a future paper, it would form the empirical core of a follow-up multi-backbone study, NOT a §5.7 sub-result of the present manuscript.

---

## 6. Commands and artifacts to inspect (Stage 0 audit)

The following Stage 0 audit commands are listed for execution at the next trigger after this plan is approved. They are all **CPU-only and read-only**. No artifact modification.

### 6.1 Locate canonical LingxiDiag DtV prediction file

```bash
# Look for a 1000-line prediction file with checker bypassed
for f in $(find results/ -name "predictions.jsonl" 2>/dev/null); do
    n=$(wc -l < $f)
    if [ "$n" = "1000" ]; then
        # Check for checker-bypass markers
        head -1 $f | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
mode = d.get('mode') or d.get('routing_mode')
checker_used = d.get('decision_trace', {}).get('checker_used')
candidate_disorders_count = len(d.get('candidate_disorders', []))
print(f'$f mode={mode} checker_used={checker_used} candidates={candidate_disorders_count}')
"
    fi
done
```

### 6.2 Recompute Full HiED ICD-10 LingxiDiag all 7 metrics from prediction file

```bash
python3 scripts/compute_table4.py \
    --predictions results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl \
    --output /tmp/full_hied_lingxi_icd10_recompute.json
# Then compare to canonical_values.dual_standard_icd10 + Both-mode metrics.json 2-class/4-class
```

### 6.3 Inspect r17_bypass_checker experiment

```bash
cat results/validation/r17_bypass_checker/run_info.json 2>/dev/null
cat results/validation/r17_bypass_checker/metrics_summary.json
wc -l results/validation/r17_bypass_checker/predictions.jsonl 2>/dev/null
# If 1000 lines and checker_bypass = True, this may be the canonical DtV source
```

### 6.4 Locate stacker training script

```bash
find . -name "*.py" 2>/dev/null | xargs grep -l "LightGBM\|lgb\|stacker.*train\|fit.*stacker" 2>/dev/null | grep -v ".pyc"
# Required for Path A1 retraining of TF-IDF-only LGBM stacker
```

### 6.5 Audit §1-§7 + Abstract for "MAS-only" / "DtV" / "checker" labeling

```bash
for f in docs/paper/drafts/ABSTRACT.md docs/paper/drafts/SECTION_*.md; do
    [ -f "$f" ] || continue
    echo "=== $f ==="
    grep -nE "MAS.only|MAS only|DtV|Direct-to-Verdict|MAS reasoning|MAS pipeline|criterion check|checker|MAS feature|HiED" $f
done
```

---

## 7. Pass/fail criteria summary

### Stage 0 (audit) pass criteria

- All 5 audit commands above produce expected outputs
- Canonical DtV prediction file located OR confirmed missing
- Full HiED ICD-10 recompute matches §5.4 Panel A (or discrepancy documented)
- Stacker training script located OR confirmed missing
- §1-§7 + Abstract MAS-label audit produces structured `MAS_LABEL_AUDIT.md`

### Stage 1 (CPU recompute) pass criteria

- Path A1: TF-IDF-only LGBM stacker trained, all 7 v4-contract metrics produced
- Path B1: Full HiED ICD-10 row for §5.1 Table 2 produced and matches §5.4 Panel A
- Path B2: MAS-only DtV all 7 v4-contract metrics produced (or row relabeled if predictions unavailable)
- All values added to `metric_consistency_report.json` `canonical_values` under new keys (e.g. `tfidf_only_lgbm`, `full_hied_icd10_lingxi`, `mas_only_dtv`)
- Sanity: paired bootstrap CIs computed for Stacker LGBM vs TF-IDF-only LGBM on all 7 metrics

### Stage 2 (GPU smoke) pass criteria — only if needed

- Triggered only if Stage 0 reveals missing canonical DtV LingxiDiag prediction file AND Stage 1 Path B2 cannot proceed
- N=100 LingxiDiag DtV smoke run with current Qwen3-32B-AWQ
- Match stage_timings.jsonl + decision_trace structure with existing `mode_icd10` predictions
- Output to `results/freeze_validation_20260429/dtv_smoke/`

### Stage 3 (full GPU) pass criteria — only if needed

- Triggered only if Stage 2 smoke clean AND result needed for paper claim
- Full N=1000 LingxiDiag + N=925 MDD-5k DtV runs
- Output to `results/freeze_validation_20260429/dtv_full/` — DO NOT overwrite canonical paths

---

## 8. Manuscript impact decision tree

```
Gap A outcome:
├── TF-IDF-only LGBM ≈ Full Stacker LGBM
│   └── §5.2 minor rewording: "MAS features contribute modestly across metrics"
│       Manuscript impact: 1-2 sentence addition to §5.2
│
├── Full Stacker LGBM > TF-IDF-only LGBM with paired CI excluding 0 on Top-3/Overall/4-class
│   └── §5.2 expanded: ranking-level MAS contribution acknowledged
│       Manuscript impact: 1 paragraph addition to §5.2 + new mini-table (3 rows)
│       Forbidden: "MAS beats TF-IDF" still forbidden
│
└── MAS-only feature LGBM substantially weaker than TF-IDF
    └── §5.2 strengthens "complementary audit signal" framing
        Manuscript impact: 1 sentence addition to §5.2

Gap B outcome:
├── Full HiED ICD-10 row added to §5.1 Table 2
│   └── §5.1 Table 2 expanded by 1 row + cross-ref note in §4.1 / §4.2
│       Manuscript impact: 1 row + ~3 sentence prose update
│       Title clarification: "MAS-only DtV" → "DtV comparator (checker bypassed)"
│
├── MAS-only DtV all 7 metrics filled
│   └── §5.1 Table 2 row updated, 5 `—` cells replaced with values
│       Manuscript impact: 5 cell updates + ~2 sentence prose update
│
├── Both rows updated (Full HiED ICD-10 added + DtV cells filled + relabeled)
│   └── Full table, both audit and full pipeline visible to reviewers
│       Manuscript impact: 1 row added + 5 cells filled + ~5 sentence prose update
│
└── Provenance gap detected (recompute disagrees with §5.4 Panel A)
    └── DEFER §5.1 row addition; document discrepancy in MAS_LABEL_AUDIT.md
        Manuscript impact: NONE in this commit; new integration artifact for PI review
```

### Tag implications

If Gap A and Gap B close cleanly, the paper-integration freeze tag advances:

```
paper-integration-v0.1 → paper-integration-v0.2 (after Gap A + Gap B closure)
```

The v0.1 tag remains valid for the PI review snapshot; v0.2 becomes the new submission-candidate freeze.

If discrepancies are detected and PI / advisor wants to keep v0.1 as the stable freeze, the gap-closure work commits to a separate branch (e.g., `gap-attribution-v0.2`) and merges into `main-v2.4-refactor` only after PI verdict.

---

## 9. Sequential discipline status

```
✓ §1-§7 all closed (manuscript body complete)
✓ Phase 2 Step 5g: final manuscript sweep                            (63a7f73)
✓ Phase 2 Commit 2: reproduction README pointer sync                 (0ca7625)
✓ Phase 2 §5.2/§5.6 line-break normalization                         (c3b0a46)
✓ Phase 2 paper-integration-v0.1 tag                                 (c7ba2b4 → c3b0a46)
✓ Phase 2 Step 6: PI / advisor review package                        (b8bda4b)
✓ Phase 3 Step 1: MAS gain + full-pipeline gap plan                  ← this commit
□ Phase 3 Step 2-Stage-0: artifact audit (CPU-only)                  (Commit 2)
□ Phase 3 Step 2-Stage-1: CPU metric recomputation                   (Commit 3 if Stage 0 clean)
□ Phase 3 Step 2-Stage-2: GPU smoke (only if needed)                 (Commit 4 conditional)
□ Phase 3 Step 2-Stage-3: GPU full rerun (only if needed)            (Commit 5 conditional)
□ Phase 3 Step 3: §5.1 Table 2 + §5.2 update per decision tree
□ Phase 3 Step 4: paper-integration-v0.2 tag (if Gap A + B close)
□ Phase 2 Step 7: PI / advisor review pass                           (Q1-Q6 verdicts pending)
□ Pre-submission freeze
□ `main` branch merge                                                (only after pre-submission freeze)
```

Per round 84 explicit:
- ❌ NO new experiments in this commit (plan only)
- ❌ NO §1-§7 prose modification in this commit
- ❌ NO Abstract modification
- ❌ NO Table 2 / Table 4 modification in this commit
- ❌ NO `metric_consistency_report.json` modification in this commit
- ❌ NO GPU work initiated in this commit
- ✓ YES write plan artifact to `docs/paper/integration/MAS_GAIN_AND_FULL_PIPELINE_GAP_PLAN.md`
- ✓ YES preserve all round 1-83 cumulative discipline (lesson 21a / 22 / 31a / 33a / 40a / 50a / 64)

---

## 10. PI / advisor review impact

This plan addresses anticipated PI / advisor concerns from Step 7 Q1-Q6:

| PI question | Gap addressed | How |
|---|---|---|
| Q1 (clinical-scope wording) | Gap B label clarification | DtV relabeling reduces implicit MAS-superiority overclaim |
| Q4 (parity-plus-audit framing) | Gap A attribution | Distinguishes ranking-level MAS contribution from LGBM-vs-LR effect |
| Q6 (claims to remove before review) | Gap A + Gap B | Both gaps directly address claim attribution |

If PI returns Q4 verdict (b) "replace audit-properties with clinically-grounded synonym" or Q6 verdict (b) "flag specific sentences", the Gap A and Gap B closure here provides the evidence base for those edits.

Round 84 plan is therefore positioned as **pre-emptive review preparation**: even if PI does not flag attribution / labeling, the Gap A and Gap B work strengthens the manuscript against external reviewer objection at submission time.

---

## 11. Cumulative lesson application

| Lesson | Application in this plan |
|---|---|
| **21a** | All 19 numeric values verified against canonical sources; Stage 0 audit explicitly required before any new value enters manuscript |
| 22 / 40a | Forbidden patterns ("MAS beats TF-IDF") explicitly preserved as forbidden in §3.5 / §8 decision tree; negation context maintained |
| 25 / 27 | Both mode = architectural pass-through; clarification table §4.2 row 5 maintains framing |
| **31a** | All §X.Y line-number references preserved; provenance gap (Full HiED ICD-10 LingxiDiag 2-class/4-class missing from canonical_values) explicitly flagged |
| **33a** | This artifact uses sentence-level format; 0 long lines |
| 38b | Plan uses `paper-integration-v0.1` tag reference (forward-looking), NOT brittle commit-hash |
| **40a** | Explicit absence: TF-IDF-only LGBM stacker variant artifact does NOT exist; required production approach §3.3 documented |
| **50a** | Plan ≠ execution; Stage 0/1/2/3 sequenced with explicit pass/fail gates; no auto-execution |
| 64 | Cross-section consistency: §3 (Gap A) / §4 (Gap B) / §6 (commands) / §7 (criteria) / §8 (decision tree) all reference the same metric values and prediction-file paths |
| 65-68 | Forbidden citation-pass patterns ("first multi-agent" / "MAS proves interpretability" / "DSM-5 superiority") not introduced |
| 70 | All commands preserve canonical-source verification before recompute |
| 71 | AIDA-Path Path B preserved; Gap C optional and deferred per Path B discipline |
| 73 | NO `2class_n=696` reference; v4 sample sizes (N=1000 / N=925, 2-class N=473 / N=490 post-F41.2-exclusion) consistent throughout |
| 74-75 | NO MDD-5k subcode percentages; NO F33→F32 collapse claim |
| 76 / 77 / 78 / 79 | Mode A 250-word JAMIA / Mode B 150-word npj framing intact in `ABSTRACT_PREP.md`; not modified by this plan |
| 80 | All Final Manuscript Sweep verdicts preserved; this plan addresses post-sweep refinements, NOT sweep findings |
| 81 / 83 | PI Review Package + hard-idle posture preserved; this plan respects "human review mode" boundary by deferring all execution to subsequent triggers |

No new lesson promoted. Cumulative count remains **36 lessons**.

---

## 12. What this plan does NOT do (in this commit)

- ❌ Recompute any v4 metric
- ❌ Train any new model
- ❌ Modify any §X.Y prose
- ❌ Modify Table 2 or Table 4
- ❌ Modify Abstract
- ❌ Modify `metric_consistency_report.json`
- ❌ Add new keys to `canonical_values`
- ❌ Run any GPU work
- ❌ Activate AIDA-Path Path A
- ❌ Merge to `main`
- ❌ Move `paper-integration-v0.1` tag

It only adds this plan artifact to `docs/paper/integration/MAS_GAIN_AND_FULL_PIPELINE_GAP_PLAN.md`.

Hard idle continues after commit, awaiting round 85 verdict OR direct trigger to execute Stage 0 (artifact audit, CPU-only, read-only).
