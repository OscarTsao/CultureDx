# Section 3 — Task and Datasets

## 3.1 Task definition

CultureDx evaluates Chinese-language psychiatric differential diagnosis as a benchmark task.
The input is a Chinese psychiatric clinical dialogue or transcript; the output is a primary diagnosis code together with a ranked list of diagnostic candidates and, for multilabel metrics, a final predicted label set.
The main target is the ICD-10 paper-parent 12-class taxonomy used by the LingxiDiag report [CITE — verify: LingxiDiag], with auxiliary 2-class and 4-class evaluations constructed from raw `DiagnosisCode` annotations to capture diagnostically meaningful distinctions required by the auxiliary evaluation tasks that the 12-class collapse cannot represent.
We frame the task throughout as a benchmark differential diagnosis task, not as a clinical diagnosis system; we make no claim of clinical deployment readiness or prospective clinical validity.

## 3.2 Datasets

**Table 1 — Datasets used in the present study.**

| Dataset | Role | N | Language | Source type | Used for |
|---|---|---:|---|---|---|
| LingxiDiag-16K (test_final) | in-domain benchmark | 1000 | Chinese | synthetic / curated dialogue | main benchmark, stacker, dual-standard, model-discordance triage |
| MDD-5k | external synthetic distribution-shift evaluation | 925 | Chinese | synthetic vignette / dialogue | bias-asymmetry, dual-standard, diagnostic-standard discordance |

Both datasets are synthetic or curated rather than clinician-adjudicated real-world clinical transcripts; benchmark-level results are not equivalent to clinical validation (§7.1).

### 3.2.1 LingxiDiag-16K

LingxiDiag-16K is the primary in-domain benchmark, consisting of synthetic / curated Chinese psychiatric clinical dialogues released by the original LingxiDiag report [CITE — verify: LingxiDiag].
We evaluate on the published `test_final` split (N = 1000) for all primary in-domain claims throughout §5 and §6.
Each case carries a raw `DiagnosisCode` annotation that we preserve for raw-code-aware auxiliary tasks; the 12-class evaluation collapses these raw codes to the paper's parent-level taxonomy via the `to_paper_parent` mapping defined in §3.3.

### 3.2.2 MDD-5k

MDD-5k is an external synthetic distribution-shift dataset of Chinese clinical vignettes (N = 925) used for cross-dataset synthetic evaluation of bias-robustness (§5.3) and dual-standard audit behavior (§5.4 / §6.2).
This is external synthetic distribution-shift evaluation, not external clinical validation; the dataset consists of synthetic vignettes rather than prospectively collected, clinician-adjudicated clinical transcripts.
F33 cases occur 2/925 in MDD-5k, and the dataset's raw `ICD_Code` field is used for the same raw-code-aware 2-class / 4-class auxiliary-task construction described in §3.3.

### 3.2.3 Datasets not used

We do not evaluate on E-DAIC or other cross-lingual psychiatric datasets in the present paper.
We mention these only as potential future cross-lingual extensions; we make no claim about cross-lingual generalization based on the present results.

## 3.3 Taxonomy and label normalization

The 12-class paper taxonomy locked in `src/culturedx/eval/lingxidiag_paper.py` consists of eleven ICD-10 parent codes plus an `Others` bucket: F20, F31, F32, F39, F41, F42, F43, F45, F51, F98, Z71, Others.
F33 (recurrent depressive disorder) is not a 12-class label; F33 cases collapse to `Others` via `to_paper_parent`, consistent with the LingxiDiag paper's original taxonomy.
The empirical impact is small: F33 cases occur 0/1000 in LingxiDiag-16K and 2/925 in MDD-5k.
The DSM-5 v0 ontology in §4.3 retains an F33 stub for system extensibility, but it is not a 12-class evaluation label.

The 12-class task uses paper-parent normalization: all F32.x codes collapse to F32, all F33.x to Others, all F41.x including F41.2 to F41, all F43.x to F43, and so on.
This collapse is appropriate for the 12-class metrics because it matches the LingxiDiag report's evaluation contract.
The 2-class and 4-class auxiliary tasks, however, are constructed from raw `DiagnosisCode` annotations rather than paper-parent labels, in order to preserve the F41.2 (mixed anxiety-depression) distinction that is diagnostically meaningful but is lost under paper-parent collapse.
Mixing the two normalization regimes is a known evaluation hazard: an earlier version of our auxiliary-task construction collapsed F41.2 to F41 before computing 2-class accuracy, which falsely included mixed anxiety-depression cases in the binary task and inflated the 2-class denominator (n = 696 instead of n = 473); this defect is documented in `docs/audit/AUDIT_RECONCILIATION_2026_04_25.md` and corrected under the v4 evaluation contract described in §4.4.

F41.2 is excluded from the binary depression / anxiety task per the paper's task definition and treated as Mixed in the four-class task.
Mixed F32+F41 comorbid cases are similarly excluded from the 2-class task and counted as Mixed in the 4-class task.
After F41.2 and mixed-comorbid exclusions, the 2-class evaluation has n = 473 cases on LingxiDiag-16K and n = 490 cases on MDD-5k; the 4-class evaluation retains all 1000 / 925 cases respectively.
We do not claim uniform per-class performance: macro-F1 is limited by rare-class blind spots and by the `Others` bucket, as discussed in §7.4.
