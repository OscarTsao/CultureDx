# Section 5.5 — TF-IDF Reproduction Gap

Our reproduced TF-IDF baseline reaches Top-1 = 0.610 on LingxiDiag-16K test_final, substantially stronger than the published TF-IDF baseline of Top-1 = 0.496 — an 11.4 percentage-point gap that we have not fully isolated.
Plausible contributors include tokenization choices, character n-gram configuration, `min_df` / `max_df` thresholds, `sublinear_tf` settings, logistic-regression hyperparameters, parent-code label normalization, and train/dev/test split handling.
Our reproduction script and audit trail are documented in `scripts/train_tfidf_baseline.py`, `docs/analysis/AUDIT_REPORT_2026_04_22.md`, and the post-v4 audit reconciliation.
We disclose this gap rather than treating the published TF-IDF comparison as our primary evidence of model strength.
Our main in-domain claim is therefore deliberately stricter: Stacker LGBM is compared against our stronger reproduced TF-IDF baseline (Top-1 = 0.612 vs 0.610) and reaches parity within the ±5 percentage-point non-inferiority margin defined in the post-v4 evaluation contract, rather than against the weaker published baseline.
Reviewers and readers may inspect both comparisons; our parity claim in §5.1 depends only on the stricter one.
