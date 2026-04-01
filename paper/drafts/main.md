# CultureDx: Culture-Adaptive Diagnostic Multi-Agent System with Evidence Grounding for Chinese Psychiatric Differential Diagnosis

**Yu-Ning Tsao**
National Yunlin University of Science and Technology
M11237033@yuntech.edu.tw

---

## Abstract

Large language models (LLMs) show promise for psychiatric differential diagnosis, but their parametric knowledge of non-Western clinical presentations remains weak. Chinese psychiatric interviews feature pervasive somatic idioms of distress (e.g., "chest tightness" for anxiety, "head dizziness" for depression) that map poorly to ICD-10 criteria without explicit cultural adaptation. We present CultureDx, a culture-adaptive multi-agent system (MAS) that decomposes clinical reasoning into specialized agent roles: triage routing, per-disorder criterion checking against ICD-10 criteria, deterministic logic evaluation, and statistical confidence calibration. Our evidence pipeline includes a 150-entry Chinese somatization ontology, temporal extraction, scope-aware negation detection, and hybrid dense-sparse retrieval. Experiments on LingxiDiag-16K and MDD-5k demonstrate that evidence-grounded MAS outperforms single-LLM baselines for Chinese psychiatric diagnosis, with particular gains in comorbidity detection and culture-specific symptom attribution.

<!-- TODO: Add specific numbers once experiments complete -->

---

## Table of Contents

1. [Introduction](sections/introduction.md)
2. [Related Work](sections/related_work.md)
3. [Method](sections/method.md)
4. [Experimental Setup](sections/experiments.md)
5. [Results](sections/results.md)
6. [Analysis](sections/analysis.md)
7. [Discussion](sections/discussion.md)
8. [Conclusion](sections/conclusion.md)
9. [Supplementary Materials](sections/supplementary.md)

---

## References

See [references.bib](references.bib)
