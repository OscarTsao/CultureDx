# 7. Discussion

## Clinical Implications

- Potential for culture-adaptive diagnostic support in Chinese psychiatric practice
- Somatization mapping as a reusable resource for Chinese clinical NLP
- Evidence-grounded reasoning improves transparency and auditability over black-box LLM diagnosis

## Limitations

- **Dataset scope**: Evaluation limited to 2 Chinese psychiatric datasets; generalization to other languages/cultures not tested
- **Model dependency**: Results tied to Qwen3 model family; transferability to other LLMs unknown
- **Somatization ontology**: Current 150-entry mapping covers common presentations but is not exhaustive
- **No clinical validation**: System is a research prototype; no real-world clinical trial conducted
- **Comorbidity ground truth**: Multi-label ground truth is incomplete in some datasets
- **Temporal criteria**: ICD-10 duration requirements (e.g., "symptoms for ≥2 weeks") are difficult to verify from single-session transcripts

## Ethical Considerations

- All diagnostic outputs are research artifacts, not clinical advice
- Risk of over-reliance on automated diagnosis in resource-limited settings
- Cultural sensitivity: somatization mapping must be maintained and validated by domain experts
- Patient privacy: all datasets used are either publicly available or properly anonymized

## Future Work

- Expand somatization ontology to cover more disorders and regional Chinese dialects
- Multi-lingual extension (Japanese, Korean psychiatric presentations)
- Clinical validation study with practicing psychiatrists
- Integration with electronic health record systems
- Active learning for somatization ontology expansion
- Longitudinal diagnosis tracking across multiple sessions

<!-- TODO: Write full discussion prose -->
