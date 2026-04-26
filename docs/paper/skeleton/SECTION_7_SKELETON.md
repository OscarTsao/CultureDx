# CultureDx Paper — Section 7 Skeleton (Limitations)

**Format**: (b) section-by-section with paste markers + Allowed/Forbidden wording guards
**Status**: skeleton ONLY (no prose). Pre-sync version.

---

## Section 7 — Limitations

### Overall narrative arc

> Document limitations honestly. Hide nothing. Reviewer attacks on limitations are pre-empted by Section 7's transparency.

### Order of subsections

```
7.1 Synthetic data limitation
7.2 DSM-5 v0 stubs are LLM-drafted (UNVERIFIED_LLM_DRAFT)
7.3 TF-IDF reproduction gap (link to §5.5)
7.4 Class coverage limitations (link to §5.6)
7.5 F32/F41 asymmetry (3.97× still asymmetric, not zero)
7.6 F42 OCD collapse mechanism
7.7 Statistical caveats (bootstrap CI, non-equivalence framing)
7.8 No clinical validation yet (Chang Gung pending, AIDA-Path pending)
```

---

## §7.1 — Synthetic Data Limitation

### Key claims
1. All experiments are on synthetic Chinese clinical dialogues (LingxiDiag, MDD-5k)
2. Synthetic data may not reflect real clinical conversation distribution
3. Real clinical data evaluation pending Chang Gung Memorial Hospital collaboration

### Allowed wording
- ✅ "All experiments are on synthetic Chinese clinical dialogues"
- ✅ "Generalization to real clinical conversation requires validation"
- ✅ "Pending Chang Gung Memorial Hospital data access"

### Forbidden wording
- ❌ "Synthetic data is a close proxy for real clinical conversation" (we don't know that)
- ❌ "These results will likely transfer to real clinical settings"

### Length: ~80 words

---

## §7.2 — DSM-5 v0 Stubs Are LLM-Drafted

### Key claims
1. All DSM-5 v0 criterion stubs are LLM-drafted (Qwen3-32B-AWQ + manual review for syntax only)
2. Marked `UNVERIFIED_LLM_DRAFT` throughout repository
3. Two distinct failure modes documented:
   - F42 OCD collapse (conservative `insufficient_evidence` policy on exclusion criteria)
   - F32/F41 asymmetry amplification (~83% over ICD-10)
4. Both trace to v0 criteria being LLM-drafted without clinician review

### Allowed wording
- ✅ "DSM-5 v0 stubs are LLM-drafted"
- ✅ "Marked `UNVERIFIED_LLM_DRAFT` throughout"
- ✅ "Clinician validation is pending"
- ✅ "v0 stubs exhibit two distinct failure patterns"
- ✅ "Conservative evidence policy" (for F42)
- ✅ "Asymmetry amplification" (for F32/F41)

### Forbidden wording
- ❌ "DSM-5 v0 stubs are clinically valid"
- ❌ "DSM-5 v0 stubs are equivalent to clinician-drafted"
- ❌ "F42 conservative policy is clinically appropriate" (round 9 correction)
- ❌ Forbidden: DSM-5 generalizes better than ICD-10

### Length: ~150 words

---

## §7.3 — TF-IDF Reproduction Gap (link to §5.5)

### Key claims
1. Our reproduced TF-IDF outperforms paper's by +11.4pp Top-1
2. Cause not fully identified
3. Likely preprocessing or train/dev/test split differences
4. Parity claim is against our stronger reproduction, NOT against the paper's number

### Allowed wording
- ✅ "Cause not fully identified"
- ✅ "Likely preprocessing or split differences"
- ✅ "Parity is claimed against our stronger reproduced baseline"

### Forbidden wording
- ❌ "Paper's TF-IDF was buggy"
- ❌ "Our TF-IDF is the canonical version"

### Length: ~80 words

---

## §7.4 — Class Coverage Limitations

### Key claims
1. F31, F43, F98, Z71 near-zero recall on both datasets (~14% of cases unreachable)
2. F42 OCD: 40pp recall collapse in DSM-5 mode on LingxiDiag, 23pp on MDD-5k
3. Hard ceiling on aggregate Top-1
4. Documented but NOT patched (avoid test-set tuning)

### Allowed wording
- ✅ "Hard ceiling on aggregate Top-1"
- ✅ "Not patched to avoid test-set tuning"
- ✅ "Documented limitation"

### Forbidden wording
- ❌ "F42 limitation is solvable" (without clinician validation)
- ❌ "Near-zero recall is acceptable"

### Length: ~120 words

---

## §7.5 — F32/F41 Asymmetry Persists at 3.97×

### Key claims
1. MAS ICD-10 v4 reduces asymmetry to 3.97×, NOT zero
2. F32/F41 confusion remains the dominant error mode under MDD-5k distribution shift
3. Asymmetry direction (F41→F32 misclassification > reverse) is consistent across all systems
4. 95% bootstrap CI [2.82, 6.08] indicates uncertainty in exact ratio
5. Asymmetric excess (+113 cases) is more stable to small-denominator effects

### Allowed wording
- ✅ "F32/F41 asymmetry persists at 3.97×, not eliminated"
- ✅ "Dominant error mode under distribution shift"
- ✅ "Asymmetric excess is more stable to small-denominator effects"
- ✅ "47.7× cumulative reduction from single-LLM baseline, but residual asymmetry remains"

### Forbidden wording
- ❌ "Asymmetry is resolved"
- ❌ "MAS solves bias"
- ❌ "3.97× is acceptable"

### Length: ~150 words

---

## §7.6 — F42 OCD Collapse Mechanism

### Key claims
1. F42 DSM-5 recall: 12% (LingxiDiag), 15% (MDD-5k); ICD-10 baseline: 52% / 38%
2. Trace: 22/25 wrong cases have D=`insufficient_evidence` (exclusion criterion)
3. `all_required: true` schema means ANY missing criterion forces non-diagnosis
4. Conservative evidence policy: `insufficient_evidence` over assumption
5. Whether conservative policy is clinically appropriate requires clinician validation
6. NOT patched in this paper (avoid test-set tuning)
7. Full trace in `docs/limitations/F42_DSM5_COLLAPSE_2026_04_25.md`

### Allowed wording
- ✅ "Conservative evidence policy"
- ✅ "Checker frequently marks D as `insufficient_evidence`" (round 9 correction)
- ✅ "Whether this conservative policy is clinically appropriate requires clinician validation"
- ✅ "NOT patched to avoid test-set tuning"
- ✅ "Trace in `docs/limitations/F42_DSM5_COLLAPSE_2026_04_25.md`"

### Forbidden wording
- ❌ "LLM correctly outputs `insufficient_evidence`" (round 9 correction)
- ❌ "F42 conservative policy is clinically appropriate"
- ❌ "F42 limitation can be solved"
- ❌ "DSM-5 v0 F42 stub has correct behavior"

### Length: ~200 words

---

## §7.7 — Statistical Caveats

### Key claims
1. McNemar p ≈ 1.0 indicates failure to reject H0 at α=0.05 — NOT formal statistical equivalence
2. We claim non-inferiority within ±5pp pre-specified margin
3. Bootstrap CI on disagreement-vs-confidence triage edge INCLUDES 0 — comparable, NOT superior
4. Bootstrap CI on F32/F41 asymmetry [2.82, 6.08] — robust direction, exact ratio uncertain
5. Paired bootstrap on (DSM-5 - ICD-10) asymmetry CI excludes 0 — significant amplification

### Allowed wording
- ✅ "McNemar p ≈ 1.0 indicates failure to reject H0, not formal equivalence"
- ✅ "Non-inferiority within pre-specified margin"
- ✅ "Bootstrap CI includes zero — comparable, not superior"
- ✅ "Robust direction, exact ratio uncertain"

### Forbidden wording
- ❌ "Statistically equivalent" (without "non-inferiority within ±5pp")
- ❌ "Significantly different" (without specifying which CI excludes 0)
- ❌ "Disagreement triage is significantly better than confidence"

### Length: ~150 words

---

## §7.8 — No Clinical Validation Yet

### Key claims
1. Chang Gung Memorial Hospital collaboration: pending data access agreement
2. AIDA-Path structural alignment: not yet performed (planned next 2-3 days)
3. Clinical validity of all DSM-5 v0 stubs: NOT yet validated
4. Real clinical conversation evaluation: pending data access
5. CultureDx is research-grade software, NOT clinical decision support

### Allowed wording
- ✅ "Chang Gung Memorial Hospital collaboration is pending"
- ✅ "AIDA-Path structural alignment is pending"
- ✅ "Research-grade software, not clinical decision support"
- ✅ "Clinical validation is the highest-priority next step"

### Forbidden wording
- ❌ "AIDA-Path validation completed" (it isn't)
- ❌ "Clinically validated" (it isn't)
- ❌ "Ready for deployment"
- ❌ "Chang Gung clinicians have approved this work"

### Length: ~150 words

---

## Section 7 total length target

~1,080 words

---

## Section 7 narrative thread

The Limitations section should pre-empt every reviewer attack. By the time a reviewer reads §7, they should have:
- Synthetic data caveat (§7.1)
- DSM-5 v0 LLM-drafted caveat (§7.2)
- TF-IDF gap caveat (§7.3)
- Coverage caveats (§7.4)
- Asymmetry persists caveat (§7.5)
- F42 mechanism caveat (§7.6)
- Statistical method caveats (§7.7)
- Clinical validation pending (§7.8)

These 8 limitations cover:
- Data: synthetic, no clinical validation
- Model: LLM-drafted DSM-5 stubs, F32/F41 residual asymmetry
- Pipeline: F42 collapse mechanism
- Evaluation: TF-IDF reproduction gap
- Statistics: non-equivalence framing
- Validation: pending Chang Gung + AIDA-Path

This is the LOCKED list. Adding more limitations = good (transparency); removing any = bad (overclaiming).
