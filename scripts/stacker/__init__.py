"""MAS-conditioned stacker: learned combination of TF-IDF and DtV predictions.

See scripts/stacker/README.md for the full protocol.

The stacker is the headline contribution of the v2.5 rebase. It replaces
the earlier RRF (reciprocal rank fusion) approach, which ignored confidence
signals and was shown to degrade Top-1 from TF-IDF's 0.610 down to 0.557.

A learned meta-learner (LR or LightGBM) trained on dev_hpo 1k cases and
evaluated on test_final 1k cases is expected to reach Top-1 0.62-0.65 with
clean held-out semantics.

Protocol:
    1. Train TF-IDF on rag_pool, predict on both dev_hpo and test_final.
    2. Run DtV on both dev_hpo (for stacker training) and test_final.
       [Requires GPU + vLLM. Skip on CPU-only dev machines.]
    3. build_features.py — join predictions, produce 30-dim feature vectors.
    4. train_stacker.py — fit LR and LightGBM meta-learners on dev_hpo.
    5. eval_stacker.py — apply frozen stackers to test_final, report
       bootstrap CIs and McNemar p-values vs. TF-IDF and DtV alone.
"""
