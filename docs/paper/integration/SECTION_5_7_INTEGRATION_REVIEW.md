# §5–§7 Integration Review (Phase 2 / Step 1)

**Date**: 2026-04-27
**Status**: Read-only review; no edits to committed sections.
**Scope**: Cross-section consistency audit for §5.1 / §5.2 / §5.3 / §5.4 / §5.5 / §5.6 / §6.1 / §6.2 / §7.
**Output**: Issue catalog with severity tags. Edits proposed for a future round, NOT applied here.

---

## 1. Source sections (read-only at HEAD = `d816e06`)

| File | Lines | Words | Anchor commit |
|---|---:|---:|---|
| `SECTION_5_1.md` | 7 | ~545 | 3508bc9 (originally) |
| `SECTION_5_2.md` | 3 | ~210 | 3508bc9 |
| `SECTION_5_3.md` | 30 | ~590 | 8a38344 (closure) |
| `SECTION_5_4.md` | 58 | ~700 | ee8e3c3 (closure) |
| `SECTION_5_5.md` | 3 | ~225 | 3508bc9 |
| `SECTION_5_6.md` | 3 | ~210 | 535bcd8 |
| `SECTION_6.md` | 60 | ~825 | 453193d (closure) |
| `SECTION_7.md` | 29 | ~640 | d816e06 (closure) |
| **Total prose** | **193** | **~3,945** | — |

---

## 2. Table numbering audit

### Declared tables

| Table | Section | Caption | Status |
|---|---|---|:---:|
| 5.4a | §5.4 line 13 | LingxiDiag-16K mode comparison (N = 1000) | ✓ |
| 5.4b | §5.4 line 26 | MDD-5k mode comparison (N = 925) | ✓ |
| 5.4c | §5.4 line 40 | Both vs ICD-10 agreement | ✓ |
| 6.1a | §6.1 line 9 | Model-discordance vs confidence baseline | ✓ |
| 6.1b | §6.1 line 21 | Union policy | ✓ |
| 6.2a | §6.2 line 44 | Diagnostic-standard discordance across datasets | ✓ |

### 🔍 Finding T1 — §5.1, §5.3, §5.5, §5.6 cite many numbers in inline text but declare no Table

**Severity**: MEDIUM (manuscript-integration concern)

The committed prose for §5.1 packs 10+ numerical anchors into single inline sentences (Top-1 / Top-3 / Overall / pp gaps for 4 systems × 2 baselines). This is hard to scan and would benefit from a Table 5.1 in the integrated manuscript. Same applies to §5.3 (cascade table is currently a Markdown table without an explicit "Table 5.3" caption).

**Suggested action for future round**: Add explicit Table captions:
- Table 5.1 — Main benchmark results on LingxiDiag-16K test_final
- Table 5.3 — F32/F41 asymmetry cascade (Single LLM → MAS R6v2 → MAS ICD-10 v4)

NOT applied here — flagged for review.

### 🔍 Finding T2 — Tables 5.4a/b/c skip §5.5 / §5.6 entirely; numbering jumps to 6.1a

**Severity**: LOW (could be intentional "no tables in §5.5 / §5.6")

Some manuscripts add Table 5.5 / Table 5.6 even for inline-cited results. Current state: §5.4 ends at Table 5.4c, §6 starts at Table 6.1a. If §5.5 (TF-IDF reproduction) gets a table per Finding T1, numbering would be 5.4a-c → 5.5 → 6.1a-b → 6.2a, which is fine.

NOT applied here.

---

## 3. Repeated-number ledger

For each cross-section anchor, list every occurrence and verify consistency.

### Anchor 1 — `0.612` Stacker LGBM Top-1 (4 occurrences)

| Location | Wording |
|---|---|
| §5.1 line 3 | "Stacker LGBM achieves Top-1 = 0.612, Top-3 = 0.925, and Overall = 0.617" |
| §5.5 line 3 | "Stacker LGBM is compared against our stronger reproduced TF-IDF baseline (Top-1 = 0.612 vs 0.610)" |
| §5.5 line 3 | "the stricter one" (parity claim) |
| §7 line 24 | "Stacker LGBM 0.612 vs reproduced TF-IDF 0.610" |

✅ **Consistent**. All 3 mentions have the same 0.612 value with appropriate wording.

### Anchor 2 — `0.610` reproduced TF-IDF Top-1 (5 occurrences)

| Location | Wording |
|---|---|
| §5.1 line 5 | "stronger reproduced TF-IDF baseline (Top-1 = 0.610), against which the Stacker LGBM advantage shrinks to +0.2 percentage points" |
| §5.1 line 7 | "MAS-only (DtV) underperforms our reproduced TF-IDF on fine-grained Top-1 (0.516 vs 0.610, −9.4 percentage points)" |
| §5.5 line 3 | "Our reproduced TF-IDF baseline reaches Top-1 = 0.610 on LingxiDiag-16K test_final" |
| §7 line 23 | "Our reproduced TF-IDF baseline reaches Top-1 = 0.610" |
| §7 line 24 | "vs reproduced TF-IDF 0.610" |

✅ **Consistent**.

### Anchor 3 — `11.6` vs `11.4` percentage-point gap (potential reader confusion)

**Severity**: LOW-MEDIUM (factually correct but could confuse reviewers)

| Location | Number | Description |
|---|---:|---|
| §5.1 line 3 | **11.6 pp** | Stacker LGBM (0.612) vs published TF-IDF (0.496) on Top-1 |
| §5.1 line 5 | **+11.4 pp** | reproduced TF-IDF (0.610) vs published TF-IDF (0.496) on Top-1 |
| §5.5 line 3 | **11.4 pp** | reproduced TF-IDF vs published TF-IDF gap |
| §7 line 23 | **11.4 pp** | same as §5.5 |

🔍 **Finding R1**: 11.6 vs 11.4 are two different gaps:
- 11.6pp = `Stacker LGBM (0.612)` − `published TF-IDF (0.496)` ✓
- 11.4pp = `reproduced TF-IDF (0.610)` − `published TF-IDF (0.496)` ✓

Both are factually correct but the integrated reader may conflate them. §5.1 line 3 ("exceeding the published TF-IDF baseline by 11.6 percentage points on Top-1") is the WEAKER comparison (against published baseline) which §5.5 / §7 explicitly says is NOT our primary parity claim.

**Suggested action for future round**: Reframe §5.1 line 3 to lead with the parity-against-reproduced claim and mention the +11.6pp-against-published gap as secondary, OR make explicit that §5.1 line 3's headline is intentionally generous-to-LingxiDiag-paper-framing while §5.1 line 5 + §5.5 use the stricter comparison.

NOT applied here — flagged for manuscript-integration discussion.

### Anchor 4 — `11.9%` MAS feature-importance share (3 occurrences)

| Location | Wording |
|---|---|
| §5.2 line 3 | "MAS-derived features account for the remaining 11.9%" |
| §5.3 line 28 | "The 11.9% MAS feature-importance share documented in §5.2 is consistent with MAS having limited measured split utility for stacker Top-1" |
| §6.1 line 33 | "The §5.2 analysis assigns MAS reasoning an aggregate 11.9% feature-importance share in the Stacker" |

✅ **Consistent denominator and scope** ("aggregate" / "feature-importance share" with §5.2 attribution). Appropriate cross-section reference pattern.

### Anchor 5 — `189× → 3.97×` F32/F41 asymmetry (multiple occurrences across §5.3 / §5.4 / §7)

| Location | Wording |
|---|---|
| §5.3 line 3 | "189 F41→F32 errors versus 1 F32→F41 error, an asymmetry ratio of 189×" |
| §5.3 line 13 | Table row: `Single LLM (Qwen3-32B-AWQ) | 189 | 1 | 189×` |
| §5.3 line 16 | Table row: `MAS ICD-10 v4 (current) | 151 | 38 | 3.97×` |
| §5.3 line 18 | "MAS ICD-10 v4: 151/38 = 3.97× (95% bootstrap CI [2.82, 6.08])" / "47.7-fold reduction" |
| §5.3 line 22 | "Switching to DSM-5 v0 reasoning increases the MDD-5k asymmetry to 181/25 = 7.24× (95% CI [5.03, 11.38])" |
| §5.3 line 30 | "3.97× remains an asymmetric error pattern, not a resolved one" |
| §5.4 line 53 | "F41→F32 / F32→F41 asymmetry ratio increases from 3.97× under ICD-10 mode to 7.24× under DSM-5-only mode" |
| §7 line 13 | "from 189× under the single-LLM baseline (raw 189 / 1) to 3.97× under MAS ICD-10 v4 (raw 151 / 38, 95% bootstrap CI [2.82, 6.08])" |
| §7 line 14 | "we do not claim F32/F41 bias is solved" |

✅ **Consistent direction (F41→F32 / F32→F41) across all 8 mentions**. ✅ **Consistent magnitudes**. ✅ **CI cited consistently** in §5.3 line 18 + §7 line 13.

### Anchor 6 — `R6v2 (5.58×)` (2 occurrences in §5.3 only)

| Location | Wording |
|---|---|
| §5.3 line 15 | Table row: `MAS R6v2 (somatization-aware) | 145 | 26 | 5.58×` |
| §5.3 line 18 | "R6v2 (5.58×) is retained as a cascade step documenting the somatization-aware prompt-mitigation checkpoint; MAS ICD-10 v4 is the current best asymmetry result, not R6v2" |

🔍 **Finding R2**: R6v2 only appears in §5.3 cascade. NOT cross-referenced in §7 or elsewhere. This may be intentional (R6v2 is descriptive cascade row, not a primary claim), but reviewers may ask "why mention R6v2 in §5.3 if it's not the headline result?"

**Severity**: LOW. Likely best left as-is — R6v2 documents methodological provenance.

### Anchor 7 — `26.4%` / `2.06×` / `42.5%` (§6.1 internal anchors)

7 occurrences each within §6.1 paragraph + Tables 6.1a/b + connector. ✅ All consistent.

### Anchor 8 — `2.06×` reused in §6.2 (DSM-5 perspective enrichment on MDD-5k)

| Location | Context |
|---|---|
| §6.1 lines 13/17/25/32 | TF-IDF/Stacker disagreement enrichment on LingxiDiag (2.06×) |
| §6.2 line 51/54/59 | DSM-5 perspective enrichment on MDD-5k (2.06×) |

🔍 **Finding R3**: `2.06×` is **the same numerical value used for two different concepts** in §6.1 vs §6.2. A reader skimming might think these are related findings.

**Severity**: LOW-MEDIUM. The two 2.06× values are coincidental (different denominators, different signal types). §6.2 explicitly attributes its 2.06× to "DSM-5 v0 primary-output perspective" on MDD-5k flagged-subset; §6.1 attributes its 2.06× to "TF-IDF/Stacker disagreement" on LingxiDiag.

**Suggested action for future round**: When the two values appear close together in the integrated manuscript, add a one-clause clarifier in §6.2 (e.g., "coincidentally the same magnitude as the §6.1 model-discordance signal but a different signal type"). NOT critical — flagged for awareness.

### Anchor 9 — `1000 / 1000` and `925 / 925` (Both mode pairwise agreement)

| Location | Wording |
|---|---|
| §5.4 line 44 | Table 5.4c row: `ICD-10 vs Both pairwise agreement | 1000 / 1000 | 925 / 925` |
| §5.4 line 45 | Table 5.4c row: `Metric-key differences | 0 / 15 | 0 / 15` |
| §7 line 10 | "pairwise agreement with ICD-10 mode is 1000 / 1000 on LingxiDiag-16K and 925 / 925 on MDD-5k, with 0 / 15 metric-key differences on both datasets" |

✅ **Consistent**. §7 line 10 inlines the Table 5.4c values for limitation framing.

### Anchor 10 — `47.7-fold reduction` (2 occurrences)

| Location | Wording |
|---|---|
| §5.3 line 18 | "a 47.7-fold reduction in the asymmetry ratio relative to the single-LLM baseline" |
| §7 line 13 | "a 47.7-fold reduction relative to the baseline" |

✅ **Consistent**. Both correctly use "47.7-fold reduction" not "47.7× improvement" (lesson 18).

### Anchor 11 — N values (1000 LingxiDiag, 925 MDD-5k)

10 mentions across §5.1 / §5.4 / §6 / §7. ✅ All consistent.

---

## 4. Claim consistency audit

### Claim A — Top-1 parity (locked story core)

| Section | Claim |
|---|---|
| §5.1 | Stacker LGBM 0.612 vs reproduced TF-IDF 0.610, ±5pp non-inferiority margin pass, McNemar p ≈ 1.0 |
| §5.2 | "stacker reaches Top-1 parity with the reproduced TF-IDF baseline, not superiority" |
| §5.5 | "parity claim in §5.1 depends only on the stricter [reproduced] comparison" |
| §7 | "the §5.1 parity claim uses our stronger reproduced baseline ... rather than the easier published baseline" |

✅ **Coherent**. All sections converge on the parity (not superiority) claim, anchored to the reproduced TF-IDF.

### Claim B — MAS-enabled audit properties (3 sub-claims)

| Sub-claim | Section | Status |
|---|---|:---:|
| F32/F41 bias-robustness under ICD-10 MAS | §5.3 | ✅ Correctly scoped (DSM-5 v0 explicitly excluded from this claim per §5.3 line 24) |
| Model/standard-discordance triage | §6.1 + §6.2 | ✅ Two distinct signals; CI interpretations correct |
| Dual-standard ICD-10/DSM-5 audit output | §5.4 | ✅ Both mode = pass-through, not ensemble |

✅ **Coherent**.

### Claim C — DSM-5 v0 vs ICD-10 trade-off (potential reviewer confusion)

🔍 **Finding C1**: §5.4 reports DSM-5-only mode is **lower** than ICD-10 mode on Top-1 / weighted-F1 / Overall on LingxiDiag-16K, but **higher** on Top-1 / Top-3 / etc. on some metrics on MDD-5k. §5.3 says DSM-5 v0 **worsens** F32/F41 asymmetry on both datasets.

**Severity**: LOW. The trade-off pattern is dataset-dependent and metric-specific (per §5.4 "DSM-5-only mode reveals dataset-dependent, metric-specific trade-offs"). §5.4 explicitly handles this. But a reader skimming §5.3 alone might think DSM-5 is uniformly worse, while §5.4 alone might suggest mixed findings.

**Existing mitigation** in committed prose: §5.3 line 24 forwards DSM-5 to §5.4 dual-standard audit framing; §5.4 line 50-58 explicitly caveats trade-offs as "not as evidence that DSM-5 v0 is superior or more robust".

✅ **Coherent if read in section order**. NOT a contradiction.

### Claim D — F42/OCD limitation (definition-specific magnitudes)

| Section | Claim |
|---|---|
| §5.4 line 55 | "DSM-5-only mode also reduces F42/OCD recall on both datasets; the magnitude depends on the slice or class definition and is reported in §7.6" |
| §7 lines 16-17 | LingxiDiag paper-parent 52→12 (n=25); LingxiDiag v4 slice −30.6pp (n=36); MDD-5k paper-parent −23.1pp (n=13); MDD-5k v4 slice −23.8pp (n=21) |

✅ **Coherent**. §5.4 forwards to §7.6; §7 delivers definition-specific magnitudes correctly.

### Claim E — Synthetic-only / no clinical validation

| Section | Wording |
|---|---|
| §5.3 line 3 | "On MDD-5k synthetic vignettes" |
| §6.1 line 34 | "evaluated on synthetic / curated test data; we do not claim deployment readiness" |
| §6.2 line 60 | "all §6 numbers as observations on synthetic / curated test data without claiming deployment readiness" |
| §7 lines 3-4 | "synthetic or curated benchmark data ... We do not claim clinical deployment readiness or prospective clinical validity" |
| §7 line 5 | "We have not yet evaluated CultureDx on clinician-adjudicated real-world clinical transcripts" |

✅ **Coherent and well-scoped**. §7 is the consolidated home; §6 inlines short caveats; §5.3 only mentions "synthetic vignettes" descriptively.

🔍 **Finding C2**: §5.4 prose contains NO explicit "synthetic / curated" mention. It refers to LingxiDiag-16K and MDD-5k by name but doesn't characterize them as synthetic.

**Severity**: LOW. §5.4's setup paragraph cross-refers to §5.1 which has dataset framing. Adding "(both synthetic / curated)" to §5.4 line 9 might be a small clarity gain.

NOT applied here.

---

## 5. Forbidden wording scan (across §5-§7 PROSE only, not PREP files)

```
=== Hard forbidden patterns scanned ===
'DSM-5 superiority':                        0 in prose ✓ (only in PREP forbidden lists)
'DSM-5 generalizes better':                 0 in prose ✓
'DSM-5 improves robustness':                0 in prose ✓
'deployment-ready':                         0 in prose ✓
'Both mode ensemble':                       0 in prose ✓
'ensemble gain':                            0 in prose ✓
'bias solved':                              0 in prose ✓
'asymmetry resolved':                       0 in prose ✓
'bias removed':                             0 in prose ✓
'disagreement beats confidence':            0 in prose ✓
'captures 99%':                             0 in prose ✓
'AIDA-Path validation completed':           0 in prose ✓
'clinician-reviewed criteria':              0 in prose ✓
'criterion-D = OCD time/distress':          0 in prose ✓
'time/distress threshold':                  0 in prose ✓
```

✅ **All forbidden patterns clean across §5-§7 prose**. PREP files contain expected forbidden examples.

### 🔍 Finding F1 — "deployment" root reused in positive context (lesson 42a violation across §5.1 / §5.2 / §5.3)

**Severity**: MEDIUM (lesson 42a / round 42 Edit 1 pattern carries over)

§7 prose was fixed in round 42 to use "system properties" instead of "deployment properties" because §7 also says "we do not claim clinical deployment readiness". Same root-reuse problem exists in §5.1 / §5.2 / §5.3:

| Location | Phrase |
|---|---|
| §5.1 line 7 | "...examine **deployment properties** not captured by Top-1 alone" |
| §5.2 line 3 | "...the **deployment-oriented properties** examined in subsequent sections" |
| §5.3 line 28 | "Top-1 parity and F32/F41 error asymmetry measure different **deployment properties**" |

These were drafted before round 42's lesson 42a was internalized. Now that §7 says "do not claim clinical deployment readiness" + "We have not yet evaluated CultureDx on clinician-adjudicated real-world clinical transcripts", the §5.1 / §5.2 / §5.3 references to "deployment properties" create the same semantic dissonance lesson 42a was meant to prevent.

**Suggested action for future round**: Replace "deployment properties" / "deployment-oriented properties" in §5.1 / §5.2 / §5.3 with:
- "system properties" (matching §7 precedent)
- "audit-relevant properties"
- "post-Top-1 properties"

3 instances total. Pure wording sync — no fact change. Pattern matches round 38 Option 2 (prose + prep cross-section sync).

NOT applied here — flagged as required edit for round 43 (or whenever Phase 2 Step 2 runs).

---

## 6. Unresolved markers / gaps

### 🔍 Finding G1 — `[CITE LingxiDiag paper]` placeholder in §5.1

§5.1 line 3 contains: `against two reference baselines from the original LingxiDiag report [CITE LingxiDiag paper]`

**Severity**: MEDIUM (single placeholder, expected during drafting; needs resolution before submission)

This is the ONLY `[CITE` placeholder in committed §5-§7 prose. Will need resolution during the references / citations pass.

NOT applied here — flagged for citation pass.

### 🔍 Finding G2 — Missing AIDA-Path mention in §5/§6 prose

§7 line 26-28 introduces AIDA-Path as a future-work limitation. But the term "AIDA-Path" appears nowhere in §5 or §6 prose.

**Severity**: LOW (acceptable for now; AIDA-Path slotting decision pending per round 42 explicit)

If AIDA-Path overlap is completed before submission, AIDA-Path content will need to slot into §5.4 / §5.7 (new section) or Discussion. If not, current §7-only mention is correct.

NOT applied here — depends on AIDA-Path completion decision.

### 🔍 Finding G3 — `dsm5_criteria.json` source-note string

| Location | Wording |
|---|---|
| §5.4 line 8 | "version `0.1-DRAFT`, source-note `UNVERIFIED`" |
| §6.2 line 60 | "the LLM-drafted unverified `dsm5_criteria.json` schema" |
| §7 line 8 | "version `0.1-DRAFT`, source-note `UNVERIFIED`" |

🔍 **Note**: §6.2 doesn't use the literal `0.1-DRAFT` / `UNVERIFIED` strings, but §5.4 and §7 do. This is fine — §6.2 references §7.2 for the full caveat, and using literal strings repeatedly would be tedious.

✅ **Acceptable**.

---

## 7. Caveat repetition assessment

### DSM-5 v0 unverified caveat — repetition count

- §5.3 line 24 — "exclude DSM-5 v0 from this bias-robustness claim"
- §5.4 line 8 — full caveat (`0.1-DRAFT` / `UNVERIFIED` / "experimental audit observations")
- §5.4 line 58 — repeats "audit observations under LLM-drafted unverified criteria" + forward-ref §7.2
- §6.2 line 60 — short caveat + forward-ref §7.2
- §7 line 8-9 — full caveat (the consolidated home)

**Verdict**: ✅ **Appropriately scoped**. §5.4 line 8 is the first-use full caveat; §5.4 line 58 / §6.2 line 60 are short reminders; §7 line 8-9 is the consolidated home. Repetition is aligned with reading order: a reviewer reading §5.4 alone gets enough caveat; a reviewer reading §7 alone gets enough caveat; a sequential reader sees consistent wording.

### Both mode pass-through caveat — repetition count

- §5.3 line 24 — short reference: "Both-mode results inherit ICD-10 by architectural pass-through and are not an ICD-10/DSM-5 ensemble"
- §5.4 lines 6, 38, 47-48 — full claim with Table 5.4c proof
- §7 lines 10-11 — limitation framing with inlined numbers

**Verdict**: ✅ **Appropriately scoped**. §5.4 carries the full claim; §5.3 / §7 are short consistent references.

### Synthetic / no-clinical-validation caveat — repetition count

- §5.3 line 3 — "synthetic vignettes" (descriptive)
- §6.1 line 34 — "synthetic / curated test data"
- §6.2 line 60 — "synthetic / curated test data"
- §7 lines 3-5 — full caveat with explicit clinician-adjudication statement

**Verdict**: ✅ **Appropriately scoped**.

---

## 8. Integration edit queue

### Required edits (for future round)

| # | Section | Issue | Action |
|---|---|---|---|
| F1.a | §5.1 line 7 | "deployment properties" — lesson 42a violation | Replace with "system properties" or equivalent |
| F1.b | §5.2 line 3 | "deployment-oriented properties" — lesson 42a violation | Replace with "system-level properties" or "post-Top-1 properties" |
| F1.c | §5.3 line 28 | "deployment properties" — lesson 42a violation | Replace with "system properties" |
| G1 | §5.1 line 3 | `[CITE LingxiDiag paper]` placeholder | Resolve in citations pass |

### Optional edits (manuscript polish)

| # | Section | Issue | Action |
|---|---|---|---|
| T1 | §5.1, §5.3 | Inline numbers would benefit from declared Tables | Add Table 5.1, Table 5.3 in integrated manuscript |
| T2 | §5.5 | Consider Table 5.5 for TF-IDF reproduction comparison | Optional |
| R1 | §5.1 line 3 | 11.6pp vs 11.4pp potential reader confusion | Reframe headline gap or add cross-clause |
| R3 | §6.2 | `2.06×` shared with §6.1 (different concepts) | Add brief disambiguating clause when integrated |
| C2 | §5.4 line 9 | No explicit "synthetic" framing for datasets | Add "(both synthetic / curated)" optional |

### Deferred (depend on external decisions)

| # | Issue | Depends on |
|---|---|---|
| G2 | AIDA-Path slot in §5/§6 prose | AIDA-Path overlap completion decision |

---

## 9. Five integration-pass questions answered

### Q1: Do §5, §6, and §7 tell one coherent story?

✅ **YES**. Locked story:
> "CultureDx reaches Top-1 parity with a strong reproduced TF-IDF baseline while adding MAS-enabled audit properties: cross-dataset F32/F41 bias-robustness under ICD-10 MAS, model/standard-discordance triage, and dual-standard ICD-10/DSM-5 audit output, with DSM-5-v0 and synthetic-data limitations explicitly scoped."

All 9 sections support this one sentence. Forward-references and back-references are consistent (§5.3 → §7.5; §5.4 → §7.6; §6 → §7).

### Q2: Are repeated numbers consistent?

✅ **YES** for all 11 anchors checked (0.612, 0.610, 11.4pp, 11.6pp, 11.9%, 189×, 3.97×, 7.24×, 26.4%, 2.06×, 1000/1000+925/925, 47.7-fold).

🔍 Two instances flagged for awareness, NOT inconsistencies:
- 11.6pp vs 11.4pp are different gaps (Stacker-vs-published vs reproduced-vs-published) — both correct
- 2.06× appears in both §6.1 and §6.2 for different signals — both correct

### Q3: Are caveats over-repeated or under-scoped?

✅ **Appropriately scoped**. DSM-5 v0 / Both mode / synthetic-data caveats follow the pattern: full caveat at first relevant section + short reminder at later sections + consolidated home in §7. No caveat is missing at first use.

### Q4: Do any sections undercut each other?

✅ **NO direct contradictions**. Trade-offs (DSM-5 better on some metrics / worse on others, F32/F41 worse under DSM-5) are clearly framed AS trade-offs, not undermining each other. §5.3 explicitly excludes DSM-5 v0 from bias-robustness claim and forwards to §5.4 / §7.

### Q5: Is §7 strong enough without making the paper sound invalid?

✅ **YES**. §7 delimits claims (synthetic-only / DSM-5 v0 / no clinical validation / pending external review) without apologizing for the work. The bias-asymmetry / dual-standard audit / disagreement-triage findings remain intact under §7's scope.

---

## 10. Recommended next move

### Required before manuscript assembly

- **Apply F1.a / F1.b / F1.c** (3 "deployment properties" replacements in §5.1 / §5.2 / §5.3) — round 43 candidate

### Optional polish

- **R1**: Reframe §5.1 line 3 to lead with reproduced-TF-IDF parity (manuscript-integration round)
- **T1**: Add explicit Table 5.1 / Table 5.3 captions (manuscript-integration round)

### Deferred

- AIDA-Path slotting depends on overlap-analysis completion
- Citations pass (G1)

### NOT to do now

- New experiments
- §3 / §4 prep (until F1.a/b/c applied)
- Introduction / Related work
- Abstract / Discussion

---

## Bottom line

§5–§7 read as a coherent paper unit. Locked story is supported by all 9 prose files. **Three required wording fixes** (F1.a/b/c, all "deployment properties" → "system properties" / equivalent) are the only blocker before declaring the §5-§7 manuscript-core stable.

Once those 3 fixes land, §3 + §4 prep can proceed.
