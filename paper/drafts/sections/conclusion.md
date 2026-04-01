# 8. Conclusion

We presented CultureDx, a culture-adaptive multi-agent system for Chinese psychiatric differential diagnosis. Our key findings:

1. **Evidence-grounded MAS outperforms single-LLM baselines** for Chinese psychiatric diagnosis, with the HiED pipeline providing the best balance of accuracy and efficiency
2. **Chinese somatization mapping is essential** — without explicit cultural adaptation, LLMs fail to connect somatic presentations to diagnostic criteria
3. **Deterministic ICD-10 logic improves reliability** — separating criterion checking (LLM) from threshold evaluation (deterministic) and confidence scoring (statistical) produces auditable, reproducible diagnoses
4. **Agent decomposition enables genuine specialization** — different diagnostic stages benefit from different reasoning strategies, and a single model cannot optimally serve all roles

CultureDx demonstrates that culture-aware evidence extraction combined with structured multi-agent reasoning can address the fundamental limitations of LLMs for non-Western psychiatric diagnosis.

<!-- TODO: Finalize with specific quantitative claims from results -->
