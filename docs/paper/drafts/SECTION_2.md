# Section 2 — Related Work

CultureDx sits at the intersection of psychiatric NLP benchmarks, clinical LLM evaluation, multi-agent diagnostic reasoning, classical supervised baselines, and formal diagnostic criteria.
Prior work in each area motivates the present framing: the system should be evaluated as a benchmark differential-diagnosis system focused on accuracy parity and audit-relevant behavior, rather than as an LLM-only state-of-the-art classifier or a clinically validated diagnostic tool.

## 2.1 Chinese psychiatric NLP and benchmark setting

Recent Chinese psychiatric NLP benchmarks include synthetic and curated dialogue resources for diagnostic classification, such as the LingxiDiag-style 12-class paper-parent ICD-10 taxonomy used as our primary in-domain benchmark [CITE LingxiDiag paper] and the MDD-5k cross-dataset distribution-shift evaluation set [CITE MDD-5k paper].
The datasets used in the present study are synthetic or curated rather than clinician-adjudicated real-world clinical transcripts, and benchmark performance on such datasets is distinct from real-world clinical validation.
This distinction shapes the rest of §2: prior work motivates which dimensions to evaluate, but does not license clinical-deployment claims.

## 2.2 Clinical and psychiatric LLM caution

Recent systematic evidence suggests that clinical LLM evaluations remain dominated by simulated or exam-style tasks, with relatively few prospective trials [CITE Chen 2026 Nat Med].
Medical LLM performance on controlled benchmarks also does not remove the need to evaluate information gathering, guideline adherence, and workflow integration in realistic clinical settings [CITE Hager 2024 Nat Med].
Psychiatry-specific reviews identify potential uses of LLMs in diagnostic support and education, while emphasizing limitations in complex cases and risk-sensitive settings such as suicide-risk estimation [CITE Omar 2024 Front Psychiatry].
CultureDx adopts the cautious posture that follows from this literature: we report benchmark behavior with explicit scope statements, disclose evaluation-contract details, and frame DSM-5 outputs as experimental audit observations rather than clinical diagnoses (§7).

## 2.3 Multi-agent diagnostic reasoning

Recent LLM-agent work has explored role-specialized, multi-round collaboration for medical reasoning, in which domain-expert agents discuss a case and reach a consensus diagnosis [CITE Tang 2024 ACL MedAgents].
Other medical-agent frameworks adapt collaboration structure or team composition to task complexity, allocating either solo or group reasoning depending on case difficulty [CITE Kim 2024 NeurIPS MDAgents]; CultureDx instead uses fixed diagnostic-role modules to expose criterion-level audit traces.
Multi-agent diagnostic systems have also been explored in rare-disease and general medical diagnosis settings, where multi-disciplinary-team-inspired pipelines have reported improved benchmark diagnostic and test-suggestion outputs over single-model baselines [CITE Chen 2025 npj MAC].
CultureDx belongs in this family but is scoped to Chinese psychiatric differential diagnosis and to a benchmark-level analysis of audit properties; we do not claim primacy among multi-agent psychiatric diagnosis systems.

## 2.4 Classical baselines and hybrid systems

Classical lexical and supervised baselines remain serious comparators in clinical NLP rather than weak strawmen.
Clinical-note classification work commonly evaluates TF-IDF or other lexical representations as reproducible baseline feature spaces [CITE PLOS One 2024 clinical NLP coding], and clinical NLP evaluations often compare BERT-style models with TF-IDF logistic-regression baselines because they represent different computational and interpretability trade-offs [CITE JMIR AI 2024 BOW vs Bio-Clinical-BERT].
Machine-learning approaches more broadly have long been effective for extracting structured information from clinical narratives [CITE Wang 2019 BMC clinical text classification].
CultureDx is framed accordingly: we treat the supervised TF-IDF baseline as a strong reproduced comparator rather than an easily defeated baseline, and our reported benchmark system is a hybrid supervised + MAS stacker rather than an LLM-only system.
The detailed numerical comparison and reproduction-gap discussion are deferred to §5.1, §5.2, and §5.5; here we record only that respect for classical baselines is structural to our framing, not incidental.

## 2.5 Diagnostic standards and criteria formalization

ICD-10 [CITE WHO ICD-10] and DSM-5 [CITE APA DSM-5] encode different diagnostic abstractions for psychiatric conditions, and formalizing narrative diagnostic criteria into machine-actionable representations can support criterion-level audit and structured reasoning.
The validity of such formalization, however, depends on the quality of the underlying schema: an LLM-drafted v0 schema is a starting point for audit, not a clinically validated artifact.
CultureDx uses a v0 DSM-5 schema as an experimental audit formalization with this caveat made explicit (§4.3, §7.2), and treats Both mode as an architectural pass-through that exposes DSM-5 reasoning as sidecar audit evidence on the same case rather than as an ICD-10 / DSM-5 ensemble (§5.4, §7.3).

## 2.6 AIDA-Path and external structural anchors

Strasser-Kirchweger et al. formalize narrative DSM-5 criteria into machine-actionable symptom-space representations, providing a deterministic external criteria-formalization reference; the associated code and data resource is named AIDA-Path [CITE Strasser-Kirchweger 2026 npj Digital Medicine].
We treat this as a relevant external structural anchor, but the present paper does not present any AIDA-Path overlap result as part of its evidence; structural alignment between the v0 DSM-5 schema and the AIDA-Path symptom-space representation is planned future work (§7.8).
We do not claim AIDA-Path validation of CultureDx; if the planned overlap analysis completes before submission, §2.6 and §7.8 will be updated to a scoped external structural-alignment result.
