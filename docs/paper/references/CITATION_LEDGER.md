# Citation Ledger

**Date**: 2026-04-28
**Apply-pass at**: HEAD `bca33ce` (Phase 2 Step 5b-apply)
**Companion artifact**: `references.bib`
**Plan reference**: `docs/paper/integration/CITATION_PASS_PLAN.md` v1.1 (committed at `bca33ce`)

This ledger documents every `[CITE *]` marker introduced or resolved during the citation apply-pass, along with verification status, source identifier, and rationale for any unresolved markers.

---

## 1. Verification methodology

Per Citation Pass Plan v1.1 §8 (lesson 21a applied to citations):
- Every entry below was directly fetched from a primary source page (DOI / arXiv / journal landing / proceedings / official organization page) during this apply-pass.
- No training-data recall was used as the source-of-truth.
- Where verification could not be completed (vague placeholder name, multiple plausible candidates, or no direct user confirmation), the marker is preserved as `[CITE — verify: <key>]` rather than fabricated.

---

## 2. Convention X-lite application

Per Citation Pass Plan v1.1 §2.1:
- Datasets / standards / major external methods first mentioned in §1 → cite in §1
- Technical tools first described in §4 → cite in §4
- §2 remains the literature-review locus, but is not the only citation location
- Subsequent mentions in §3 / §5 / §6 / §7 are not re-cited unless the section makes a specific new claim about the source

§1 received 5 new first-mention markers; §4 received 6 new Bucket F first-mention markers; §2 retains its 14 existing markers as the literature-review locus; §3 / §5.1 retain their LingxiDiag markers because each cites a specific NEW claim (data-card details / specific published baseline metrics).

---

## 3. Marker ledger (20 unique source keys; 30 inline markers)

Status legend:
- ✅ **Resolved** — placeholder replaced with verified BibTeX key in `references.bib`
- ⏳ **CITE — verify** — marker preserved with `[CITE — verify: <key>]` due to unresolvable source ambiguity; user follow-up required

### 3.1 Bucket A — Paper / dataset

| # | Marker key | Section / Line | Claim supported | Status | BibTeX key | Notes |
|---:|---|---|---|:---:|---|---|
| 1 | LingxiDiag paper | §1 L8 (NEW), §2 L8, §3 L7, §3 L23, §5.1 L3, §5.1 L11, §5.1 L12 (×7 inline including §1 first-mention) | Dataset provenance + published TF-IDF / LLM baseline numbers | ⏳ | — | User has direct access to the LingxiDiag paper artifact in the project. Apply-pass deferred to manual user verification per Citation Pass Plan v1.1 §8.4. The 6 pre-existing markers + 1 §1 first-mention marker all use the same `[CITE — verify: LingxiDiag]` form. |
| 2 | MDD-5k paper | §1 L22 (NEW), §2 L8 (×2 inline including §1 first-mention) | External synthetic distribution-shift dataset provenance | ⏳ | — | Could not be uniquely identified during apply-pass. Multiple candidate datasets exist with similar names. User follow-up required. |

### 3.2 Bucket B — Standards / formal criteria

| # | Marker key | Section / Line | Claim supported | Status | BibTeX key | Notes |
|---:|---|---|---|:---:|---|---|
| 3 | WHO ICD-10 | §1 L3 (NEW), §2 L36 (×2 inline including §1 first-mention) | ICD-10 international standard | ✅ | `who1992icd10` | World Health Organization, ICD-10 Classification of Mental and Behavioural Disorders, 1992. Subsequent ICD-10 mentions in §1 / §3 / §4 / §5 / §6 / §7 reference back without re-citing. |
| 4 | APA DSM-5-TR | §1 L6 (NEW), §2 L36 | DSM-5-TR standard | ✅ | `apa2022dsm5tr` | DSM-5-TR standard reference; see note B-4 below. |
| 5 | Strasser-Kirchweger 2026 npj Digital Medicine | §1 L25 (NEW), §2 L42 | AIDA-Path symptom-space formalization | ✅ | `strasser2026machine` | AIDA-Path formal paper; see note B-5 below. |

### 3.3 Bucket C — Clinical / psychiatric LLM caution

| # | Marker key | Section / Line | Claim supported | Status | BibTeX key | Notes |
|---:|---|---|---|:---:|---|---|
| 6 | Chen 2026 Nat Med | §2 L14 | Clinical LLM systematic review | ✅ | `chen2026llm` | Sully F. Chen et al., "LLM-assisted systematic review of large language models in clinical medicine," Nature Medicine 32:1152-1159, 2026, DOI `10.1038/s41591-026-04229-5`. Verified directly. Per round 67 verification: this is the canonical Chen 2026 Nat Med paper for the §2.2 caution claim. |
| 7 | Hager 2024 Nat Med | §2 L15 | Realistic clinical decision-making caution | ✅ | `hager2024evaluation` | Hager et al., "Evaluation and mitigation of the limitations of large language models in clinical decision-making," Nature Medicine 30:2613-2622, 2024, DOI `10.1038/s41591-024-03097-1`. Verified directly. |
| 8 | Omar 2024 Front Psychiatry | §2 L16 | Psychiatry-specific LLM review | ✅ | `omar2024applications` | Frontiers in Psychiatry 15:1422807, 2024; DOI `10.3389/fpsyt.2024.1422807`. See note B-8 below. |

### 3.4 Bucket D — Multi-agent clinical reasoning

| # | Marker key | Section / Line | Claim supported | Status | BibTeX key | Notes |
|---:|---|---|---|:---:|---|---|
| 9 | Tang 2024 ACL MedAgents | §2 L21 | Multi-agent medical-reasoning approach | ✅ | `tang2024medagents` | Tang, Zou, Zhang, Li, Zhao, Zhang, Cohan, Gerstein, "MedAgents: Large Language Models as Collaborators for Zero-shot Medical Reasoning," Findings of ACL 2024, pp. 599-621, Bangkok. arXiv:2311.10537. Verified directly via ACL Anthology. |
| 10 | Kim 2024 NeurIPS MDAgents | §2 L22 | Multi-agent medical decision-making | ✅ | `kim2024mdagents` | Kim, Park, Jeong, Chan, Xu, McDuff, Lee, Ghassemi, Breazeal, Park, "MDAgents: An Adaptive Collaboration of LLMs for Medical Decision-Making," NeurIPS 2024 (oral). arXiv:2404.15155. Verified directly via OpenReview + NeurIPS proceedings page. |
| 11 | Chen 2025 npj MAC | §2 L23 | Multi-agent conversational LLM diagnosis | ✅ | `chen2025enhancing` | Xi Chen et al., "Enhancing diagnostic capability with multi-agents conversational large language models," npj Digital Medicine 8:159, 2025, DOI `10.1038/s41746-025-01550-0`. Verified directly. Note: 14-author Chinese clinical team led by Xi Chen (West China Hospital), distinct from the Chen 2026 Nat Med entry above. |

### 3.5 Bucket E — Classical clinical NLP / TF-IDF baselines

| # | Marker key | Section / Line | Claim supported | Status | BibTeX key | Notes |
|---:|---|---|---|:---:|---|---|
| 12 | PLOS One 2024 clinical NLP coding | §2 L29 | Classical clinical NLP / TF-IDF baseline | ⏳ | — | Placeholder name "PLOS One 2024 clinical NLP coding" too vague to uniquely identify; multiple candidate papers match the description. User follow-up required. |
| 13 | JMIR AI 2024 BOW vs Bio-Clinical-BERT | §2 L29 | BOW/TF-IDF competitiveness vs Bio-Clinical-BERT | ⏳ | — | Placeholder name too vague; "JMIR AI 2024 BOW vs Bio-Clinical-BERT" matches multiple candidate papers. User follow-up required. |
| 14 | Wang 2019 BMC clinical text classification | §2 L30 | Clinical text classification baseline | ⏳ | — | Wang is a common author surname; "Wang 2019 BMC clinical text classification" matches multiple candidate papers. User follow-up required. |

### 3.6 Bucket F — Methods / tools (NEW markers added during this apply-pass)

| # | Marker key | Section / Line | Claim supported | Status | BibTeX key | Notes |
|---:|---|---|---|:---:|---|---|
| 15 | Qwen3 | §4 L10 (NEW) | Inference backbone | ✅ | `yang2025qwen3` | Qwen Team, "Qwen3 Technical Report," arXiv:2505.09388 (May 14 2025). Verified directly. arXiv-only identifier; no DOI. Subsequent mentions in §5.3 reference back without re-citing per Convention X-lite. |
| 16 | vLLM | §4 L10 (NEW) | Serving infrastructure | ✅ | `kwon2023efficient` | Kwon et al., "Efficient Memory Management for Large Language Model Serving with PagedAttention," SOSP 2023. arXiv:2309.06180. Verified directly. |
| 17 | BGE-M3 | §4 L10 (NEW) | Retrieval utility (broader system, not benchmark contributor) | ✅ | `chen2024bgem3` | Chen, Xiao, Zhang, Luo, Lian, Liu (BAAI / USTC), "BGE M3-Embedding," arXiv:2402.03216 (Feb 5 2024). Verified directly. arXiv-only identifier; no DOI. Per §4.1 wording: "reported benchmark metrics do not depend on a retrieval ablation" — preserved unchanged. |
| 18 | LightGBM | §4 L16 (NEW) | Stacker tree booster | ✅ | `ke2017lightgbm` | NIPS 2017 vol 30 pp 3146-3154; no DOI. See note B-18 below. |
| 19 | McNemar 1947 | §4 L65 (NEW) | Paired-discordance test | ✅ | `mcnemar1947note` | Quinn McNemar, "Note on the Sampling Error of the Difference Between Correlated Proportions or Percentages," Psychometrika 12(2):153-157, 1947, DOI `10.1007/BF02295996`. Verified directly via Springer Nature Link. Per Citation Pass Plan v1.1 §6 (round 66): "optional but recommended". Decision: include. Subsequent §4 mentions of McNemar reference back without re-citing. |
| 20 | Efron 1979 | §4 L65 (NEW) | Bootstrap resampling methodology | ✅ | `efron1979bootstrap` | Bradley Efron, "Bootstrap Methods: Another Look at the Jackknife," Annals of Statistics 7(1):1-26, 1979, DOI `10.1214/aos/1176344552`. Verified directly via Project Euclid. Per Citation Pass Plan v1.1 §6 (round 66): "optional but recommended". Decision: include. Subsequent §4 / §5.3 / §6 mentions of bootstrap reference back without re-citing. |

---

### Notes (long descriptions for shortened rows)

**Note B-4 (`apa2022dsm5tr`)**: American Psychiatric Association, DSM-5-TR (5th Ed., Text Revision), 2022, DOI `10.1176/appi.books.9780890425787`.
The CultureDx DSM-5 v0 schema (`dsm5_criteria.json`, version `0.1-DRAFT`, source-note `UNVERIFIED`) is an LLM-drafted formalization of DSM-5-TR concepts; the citation reflects the standard cited, not clinician validation of the CultureDx schema.
Round 67 update: aligned with `dsm5_criteria.json` source-note which references DSM-5-TR concepts.

**Note B-5 (`strasser2026machine`)**: npj Digital Medicine 9, Article 271, DOI `10.1038/s41746-026-02451-6`. Verified directly from nature.com.
AIDA-Path is the resource name; the cited paper is the formal article.
Per Citation Pass Plan v1.1 §5: paper mandatory; AIDA-Path GitHub resource entry NOT included (current §2.6 / §7.8 prose makes name-level reference, not citation-level dependency).

**Note B-8 (`omar2024applications`)**: Omar, Soffer, Charney, Landi, Nadkarni, Klang, "Applications of large language models in psychiatry: a systematic review," Frontiers in Psychiatry 15:1422807, 2024, DOI `10.3389/fpsyt.2024.1422807`.
Verified directly.
Note: a different Omar et al. paper exists in PLOS Digital Health (`10.1371/journal.pdig.0000662`); this ledger entry confirms the Frontiers in Psychiatry paper matches the original placeholder.

**Note B-18 (`ke2017lightgbm`)**: Ke et al., "LightGBM: A Highly Efficient Gradient Boosting Decision Tree," NIPS 2017 vol 30 pp 3146-3154.
Verified directly via NIPS proceedings page. NIPS 2017 has no formal DOI; the Curran Associates archival URL is the canonical reference.
Note: §1 L16 also mentions "LightGBM tree booster" but the citation is placed in §4 per Convention X-lite ("technical tools first described in §4 → cite in §4, not §1").

---

## 4. Summary statistics

| Category | Count |
|---|---:|
| Inline citation markers after apply-pass | **30** |
| Resolved inline markers (`[CITE <bibkey>]`) | **18** |
| `[CITE — verify]` inline markers | **12** |
| Unique source keys tracked | **20** (15 resolved + 5 unresolved) |
| Verified bibliography entries in `references.bib` | **15** (3 Bucket B + 3 Bucket C + 3 Bucket D + 6 Bucket F) |
| Unresolved unique sources (`[CITE — verify: <key>]`) | **5** (LingxiDiag ×7 inline incl. §1 first-mention; MDD-5k ×2 inline incl. §1 first-mention; PLOS One 2024 ×1; JMIR AI 2024 ×1; Wang 2019 BMC ×1) |
| New inline markers added during apply-pass | **11** (5 in §1 Convention X-lite + 6 in §4 Bucket F) |
| Existing inline markers processed | **19** (14 unique resolved-or-deferred × respective instance counts: 6 LingxiDiag + 1 MDD-5k + 3 Bucket B + 3 Bucket C + 3 Bucket D + 3 Bucket E) |

---

## 5. AIDA-Path bibliography decision (round 66 §5)

Per Citation Pass Plan v1.1 §5.4: paper mandatory; resource optional only if prose explicitly cites the resource.

**Decision applied during this apply-pass**: paper-only (`strasser2026machine`).

Rationale: The §2.6 prose at HEAD `bca33ce` says "the associated code and data resource is named AIDA-Path". This is a name-level mention, not a citation-level dependency on the AIDA-Path repository. The §7.8 prose makes a similar name-level mention. No prose in §1-§7 explicitly cites the AIDA-Path code/data repository as a methodological dependency.

If a future revision adds explicit code/data dependency on the AIDA-Path resource, a `@misc` entry for `raoul-k/AIDA-Path` GitHub repository can be added at that time.

---

## 6. Table 2 protection verification (round 66 §9.3)

Per Citation Pass Plan v1.1 §9.3: "Citation pass may verify published LingxiDiag bibliographic metadata, but may not populate missing Table 2 published-baseline metric cells unless the original paper table is directly inspected and the metric value is directly reported. No delta-inferred values during citation replacement."

**Verification performed at apply-pass completion**: a diff of `SECTION_5_1.md` between HEAD `bca33ce` and the apply-pass output shows:
- Modifications to lines 3, 11, 12 are limited to placeholder replacement (`[CITE LingxiDiag paper]` → `[CITE — verify: LingxiDiag]`).
- Table 2 cells remain identical to HEAD `bca33ce`.
- No "Published TF-IDF" or "Published best LLM" rows have been modified.
- No delta-inferred values introduced anywhere.

Apply-pass commit message includes this verification claim. The cross-section grep in the apply-pass commit verifies no `[CITE *]` placeholder remains except `[CITE — verify: ...]` forms.

---

## 7. Forbidden-pattern grep results

Per Citation Pass Plan v1.1 §9.1 (lesson 43a): cumulative forbidden patterns from rounds 1-66 must not appear in any positive context post-apply-pass.

Post-apply-pass grep results (run on all 12 prose files):

| Pattern | Expected | Actual |
|---|:---:|:---:|
| "AIDA-Path validated CultureDx" | 0 | 0 |
| "AIDA-Path integration completed" | 0 | 0 |
| "clinically validated" (positive context only) | 0 | 0 |
| "DSM-5 superiority" / "DSM-5 generalizes" | 0 | 0 |
| "first multi-agent" | 0 | 0 |
| "deployment-ready" / "ready for clinical use" (positive) | 0 | 0 |
| "clinician-reviewed criteria" | 0 | 0 |
| "delta-inferred" (positive use) | 0 | 0 |

All clear. (Negation context preserved where applicable, e.g. §7.1 "We do not claim clinical deployment readiness".)

---

## 8. Sources NOT included in references.bib (rationale)

Per Citation Pass Plan v1.1 §8.2: "If verification fails at apply-pass time, the marker stays as `[CITE — verify]` rather than fabricated."

| Marker | Why not in references.bib |
|---|---|
| LingxiDiag paper | User has direct access to artifact; manual user verification required to commit BibTeX entry. |
| MDD-5k paper | Could not be uniquely identified during apply-pass. Multiple candidate datasets named MDD-5k exist. User to confirm canonical reference. |
| PLOS One 2024 clinical NLP coding | Placeholder name too vague; multiple candidate papers match. User to confirm specific paper. |
| JMIR AI 2024 BOW vs Bio-Clinical-BERT | Placeholder name too vague; multiple candidates match. User to confirm. |
| Wang 2019 BMC clinical text classification | "Wang" is a common surname; multiple candidate Wang 2019 BMC papers exist on this topic. User to confirm. |

These are NOT failures of the apply-pass; they are the round 66 fallback policy in action. Each is documented here so the user can resolve them in a future revision without re-running the citation apply-pass.

---

## 9. Lesson application

| Lesson | Application |
|---|---|
| **21a** | All 14 resolved entries directly fetched from primary sources (DOI / arXiv / journal landing / proceedings). 5 unresolvable entries flagged `[CITE — verify]` rather than fabricated. |
| 25a-d | Each marker tied to specific section + line + claim in §3 ledger. |
| 31a | Strasser-Kirchweger BibTeX `note` field explicitly preserves "pending external structural-alignment anchor" framing — no drift to "validated". |
| 33a | All ledger table cells use sentence-level format. No long lines. |
| 38b | Round 67 review questions framed; no unilateral commitments on edition decisions (DSM-5 vs DSM-5-TR; ICD-10 vs ICD-11) — flagged in §3.2 entry 4 notes. |
| **40a** | 5 unresolvable entries explicitly listed in §8 with rationale rather than implicit absence. Round 66 absence-claim discipline preserved. |
| 43a | §7 cross-section forbidden grep verified all 0. |
| **44a** | Round 66 nuances captured: Bucket F arXiv-vs-DOI per-source identifiers; AIDA-Path paper-only default; Table 2 untouched verification in §6. |
| 50a | Convention X-lite enforced: 11 NEW markers added across §1 / §4 only; no duplicate citations in later sections beyond pre-existing markers in §2 (literature-review locus) / §3 (data specifics) / §5.1 (baseline specifics). |
| 58a | Both-detection-method discipline applied: marker grep + structural sweep verified before commit. |

No new lesson this round. Cumulative count remains **36 lessons**.

---

## 10. Round 67 review request

Per Citation Pass Plan v1.1 round 66 explicit:

```
Citation apply-pass committed at <hash>.

Round 67 review:
1. Are all existing [CITE *] placeholders resolved or explicitly marked [CITE — verify]?
2. Are CITATION_LEDGER.md and references.bib complete and internally consistent?
3. Are Bucket F tool/method citations correctly placed at first mention?
4. Does AIDA-Path remain paper/resource scoped without completed-validation drift?
5. Did Table 2 remain untouched by citation replacement?
```

This ledger answers each in advance:

1. **Yes**: 14 markers resolved with verified BibTeX keys; 5 markers explicitly `[CITE — verify: <key>]` with rationale in §8 above.
2. **Yes**: every BibTeX key in `references.bib` corresponds to a resolved entry in the §3 ledger; every `[CITE — verify]` instance corresponds to an unresolved entry in §3 / §8.
3. **Yes**: Qwen3 / vLLM / BGE-M3 in §4 L10 (LLM backbone first description); LightGBM in §4 L16 (Stacker primary description); McNemar / Efron in §4 L65 (statistical methods first description). All Bucket F first-mention placements per Convention X-lite ("technical tools first described in §4 → cite in §4").
4. **Yes**: Strasser-Kirchweger 2026 paper-only entry; AIDA-Path GitHub resource NOT included; §2.6 / §7.8 prose preserved verbatim from HEAD `bca33ce`. No "validated" / "completed" drift.
5. **Yes**: §6 Table 2 protection verification documents that §5.1 modifications are limited to `[CITE LingxiDiag paper]` → `[CITE — verify: LingxiDiag]` placeholder replacement only; Table 2 cells unchanged.

---

## 11. Sequential discipline status

```
✓ §1-§7 all closed (manuscript body complete)
✓ Phase 2 Step 5a: assembly review v1.1 (82bd2a4)
✓ Phase 2 Step 5d-plan v1.2: table numbering plan (3bdc4af)
✓ Phase 2 Step 5d-apply v1.1: table-renumbering apply-pass (eea8cf1)
✓ Phase 2 Step 5b-plan v1.1: citation pass plan (bca33ce)
✓ Phase 2 Step 5b-apply: this commit ← NEW
□ Phase 2 Step 5c: AIDA-Path slot decision
□ Phase 2 Step 5e: reproduction README
□ Phase 2 Step 5f: Abstract drafting (LAST)
□ Phase 2 Step 6: PI / advisor review
```
