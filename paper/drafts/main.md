# CultureDx: Culture-Adaptive Diagnostic Multi-Agent System with Evidence Grounding for Chinese Psychiatric Differential Diagnosis

**Yu-Ning Tsao**
National Yunlin University of Science and Technology
M11237033@yuntech.edu.tw

---

## Abstract

Large language models (LLMs) are increasingly capable medical reasoners, but Chinese psychiatric diagnosis remains difficult because symptom descriptions are often indirect, somatized, and culturally mediated. We present CultureDx, a culture-adaptive diagnose-then-verify multi-agent system that separates evidence extraction, diagnostic ranking, per-disorder criterion checking, deterministic ICD-10 logic, confidence calibration, and comorbidity filtering. The evidence stack combines a 150-entry Chinese somatization ontology, temporal feature extraction, scope-aware negation handling, and BGE-M3-based retrieval. On the committed LingxiDiag-16K validation split (N=1000) under paper-aligned manual-scope evaluation, the best configuration reaches 0.527 Overall, outperforming the zero-shot single-model baseline by 0.045 absolute and ranking first among the committed LLM baselines while remaining within 0.006 of TF-IDF+LR. Partial multi-backbone validation shows the same architecture consistently helps smaller models, with DtV improving Overall by +0.104 to +0.262 depending on backbone. Error analysis shows that the main remaining bottleneck is not ICD-10 logic or the comorbidity gate, but persistent failure on Z71/Others cases, where criterion checkers still over-confirm disorder evidence. These results suggest that for Chinese psychiatric diagnosis, culture-aware evidence normalization and structured verification matter more than additional free-form generation alone.

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
