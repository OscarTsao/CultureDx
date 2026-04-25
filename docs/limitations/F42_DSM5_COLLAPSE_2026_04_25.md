# F42 OCD Collapse in DSM-5 Mode — Trace Analysis

**File**: target `docs/analysis/F42_DSM5_COLLAPSE_TRACE.md`
**Source**: full LingxiDiag benchmark (commit `f8adb4a`), 25 F42-gold cases
**GPT round 4 verdict**: "Don't auto-assume threshold/schema bug — trace first"

---

## Headline finding

DSM-5 mode F42 (OCD) recall collapses from 52% (ICD-10) to 12% (DSM-5), a 40pp drop. **Root cause is NOT the same as F32/F33 threshold mismatch.** F42 uses `all_required: true`, not `min_total: N`, but the underlying clinical issue is similar: an exclusion criterion (D) that cannot be reliably verified from a single transcript.

---

## DSM-5 F42 schema

```json
"F42": {
  "icd10_equivalent": "F42",
  "is_lossy_reasoning": false,
  "threshold": {"all_required": true, "time_per_day_hours": 1},
  "criteria": {
    "A": {"type": "core",       "text_zh": "存在強迫思考、強迫行為，或兩者同時存在。"},
    "B": {"type": "severity",   "text_zh": "症狀耗費大量時間，或造成顯著痛苦與干擾。"},
    "C": {"type": "experience", "text_zh": "當事人將症狀經驗為侵入、不受歡迎，或被某種驅力推動，而非單純愉悅的習慣。"},
    "D": {"type": "exclusion",  "text_zh": "此型態不能由物質、其他醫療狀況或另一個主要障礙更佳解釋。"}
  }
}
```

`all_required: true` = ALL 4 criteria (A, B, C, D) must be `met` for F42 to be confirmed by the logic engine.

---

## Per-criterion failure pattern (all 25 F42-gold cases)

| Criterion | met | not_met | insufficient_evidence | Total |
|---|---:|---:|---:|---:|
| A (core: obsessions/compulsions) | 15 | 1 | 9 | 25 |
| B (severity: time-consuming/distress) | 24 | 1 | 0 | 25 |
| C (experience: intrusive/unwanted) | 15 | 0 | 10 | 25 |
| **D (exclusion: not better explained by other)** | **5** | **0** | **20** | 25 |

D is `insufficient_evidence` in 80% of F42-gold cases.

---

## Comparison: 3 cases DSM-5 got CORRECT vs 22 cases DSM-5 got WRONG

### Cases DSM-5 correctly predicted F42 (3 cases, all 4/4 met)

```
Case 390266185: A=met B=met C=met D=met → F42 confirmed → F42 predicted ✓
Case 399886066: A=met B=met C=met D=met → F42 confirmed → F42 predicted ✓
Case 396096331: A=met B=met C=met D=met → F42 confirmed → F42 predicted ✓
```

### Cases DSM-5 wrong (22 cases, D rarely met)

Pattern observed in 18+ wrong cases:

```
Case 339178683: A=met B=met C=met D=insufficient_evidence
                → met=3/total=4, all_required FAIL
                → F42 not confirmed → veto F42→F39 → predicted F39

Case 324767336: A=met B=met C=met D=insufficient_evidence
                → met=3/total=4, all_required FAIL
                → F42 not confirmed → veto F42→F51 → predicted F51

Case 363112097: A=not_met B=met C=insufficient_evidence D=insufficient_evidence
                → met=1/total=4 → F42 not confirmed → predicted F41
```

The dominant failure mode: **A+B+C all `met`, but D `insufficient_evidence`, fails `all_required`, gets vetoed to F39/F41/F51**.

ICD-10 mode does not have this issue because ICD-10 F42 has different criterion structure that doesn't include the same exclusion-D requirement.

---

## Why criterion D fails

DSM-5 F42 criterion D requires ruling out:
1. Substance/medication causing the symptoms
2. Other medical conditions
3. Other primary mental disorders better explaining the presentation

In a clinical transcript:
- Substance history may not be discussed
- Medical comorbidities may not be ruled out within a single conversation
- Differential diagnosis with other conditions requires extended workup

LLM correctly outputs `insufficient_evidence` for D in 80% of cases — it's clinically appropriate to mark uncertain rather than assume "no exclusion = excluded".

This is the **same type of clinical phenomenon** that motivated the F32/F33 fix (`min_total: 5 → 3`), but it manifests through `all_required: true` instead.

---

## Three potential fixes (none applied yet — pending decision)

### Option A: Treat `insufficient_evidence` on exclusion criteria as "not blocking"

Modify logic engine: if `criterion.type == "exclusion"` and `status == "insufficient_evidence"`, treat as `met` for threshold purposes.

Rationale: exclusion criteria are about ruling things OUT. "No evidence of substance involvement" is functionally equivalent to "substance not the cause". This matches how clinicians actually reason from limited transcripts.

**Pros**: principled, generalizes to all disorders with exclusion-type criteria.
**Cons**: changes semantics of `all_required: true`. Need to verify no other disorder is improperly affected.

### Option B: Change F42 threshold from `all_required: true` to `min_total: 3`

Match the F32 fix style: require 3 of 4 criteria explicitly met.

**Pros**: matches F32/F33 pattern, simple JSON edit.
**Cons**: F42 schema is structurally different — criteria are not symmetric. Forcing min_total may incorrectly accept cases where A is `not_met` (non-OCD presentation) but B, C, D happen to all be met for unrelated reasons.

### Option C: Document as known limitation, do NOT fix for paper

Frame as: "DSM-5 v0 criteria use strict all-required exclusion semantics; in practice transcripts rarely contain explicit substance/medical exclusion evidence. F42 recall is therefore degraded relative to ICD-10 mode. Phase W clinician review will refine criterion D evidence-extraction strategy."

**Pros**: honest, doesn't risk introducing new bugs before submission.
**Cons**: leaves a known weakness in DSM-5 mode results; reviewer may push back.

---

## Recommendation

**Option C for paper submission** + **Option A for post-submission refinement**.

Rationale:
1. Fixing F42 alone (Option B) is suspiciously close to "tuning to test set" — the trace was done on the test_final dataset.
2. Option A is principled but requires more careful regression testing across all disorders.
3. Option C lets us submit with honest documentation of the limitation, then improve in revision/Phase W.

This is more defensible than rushing a fix that might shift other class boundaries.

---

## Impact on paper claims

### Add to limitations section

> "DSM-5 mode F42 (OCD) recall is 12% versus 52% in ICD-10 mode. We traced this to criterion D (exclusion) being marked `insufficient_evidence` in 20 of 25 F42-gold cases by the LLM checker, which then fails the `all_required: true` threshold. This represents a known weakness of LLM-based criterion verification on exclusion criteria from limited clinical transcripts. We document this as a v0 DSM-5 limitation pending Phase W clinician review and refined evidence-extraction strategies."

### Do NOT claim

- ❌ "F42 OCD detection works comparably across standards"
- ❌ "Threshold tuning resolved the F42 issue"
- ❌ "DSM-5 mode handles all disorder classes equally well"

### Honest framing

- ✅ "DSM-5 mode shows class-specific trade-offs vs ICD-10: improved F32 (+4pp), reduced F41 (-11pp) and F42 (-40pp), traced to specific criterion structures (F32 from `min_total` fix; F41/F42 from exclusion-criterion strictness)."

---

## Lesson for future ontology work

Both F32/F33 and F42 share a clinical reality: **exclusion criteria cannot be reliably verified from limited evidence**. This is a fundamental limitation, not a bug per se.

For Phase W with 長庚 review, propose:
1. Mark exclusion-type criteria explicitly via metadata
2. Logic engine treats `insufficient_evidence` on exclusion criteria as "not blocking"
3. Document this semantic in `docs/analysis/CRITERION_TYPE_SEMANTICS.md`

This is a generalizable contribution — it's how clinical reasoning actually works under uncertainty, not just a CultureDx-specific fix.
