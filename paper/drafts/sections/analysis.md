# 6. Analysis

## 6.1 Retrieval Helps Only When Coupled With Verification

The ablation table shows that retrieval is not universally beneficial. Adding RAG to a single-call baseline raises 12-class top-3 from .575 to .702, but exact 12-class accuracy collapses from .249 to .024 and Overall drops from .482 to .469. The most plausible interpretation is that retrieval increases label recall while simultaneously making unconstrained generation more willing to hedge across related diagnoses. Once retrieval is paired with diagnose-then-verify, however, the picture changes: DtV V2 + RAG reaches .317 exact 12-class accuracy and .527 Overall. In other words, retrieval seems to help candidate recall, but explicit criterion verification is what turns that recall into correct final decisions.

## 6.2 The Main Gain Is Better Label Discipline

The largest single behavioral change is not a dramatic increase in raw top-3 recall, but a reduction in uncontrolled label explosion. The single baseline predicts an average of 2.094 labels per case, whereas the best DtV system predicts 1.358. At the same time, subset accuracy improves from .019 to .317 and hamming accuracy from .311 to .454. Label precision also rises from .318 to .474. This indicates that the verify-and-filter stages are not merely finding additional comorbidities; they are suppressing unsupported ones and making the final label set much closer to the gold structure.

This also explains an apparent anomaly in the metrics: comorbidity detection F1 is slightly lower for Row 05 than for Row 01. The single baseline inflates recall by over-predicting labels, while DtV trades some of that opportunistic recall for much better exact-match and label precision. For a benchmark that ultimately scores exact and structured predictions, this trade is desirable.

## 6.3 Z71/Others Remains the Dominant Failure Mode

The committed abstention analyses show that the current bottleneck is not a missing threshold on confidence. In the corrected Z71/Others study, baseline recall for both `Z71` and `Others` is 0.0. A separate oracle analysis estimates that perfect recovery of these cases would raise Overall from .527 to roughly .564, a gain of +0.037. However, simple threshold heuristics do not recover this gap in practice, because the checker stack over-confirms disorder evidence even on counseling-style cases.

The corrected distribution analysis makes the issue concrete: Z71 cases still have a mean confirmed `met_ratio` of 0.72, compared with 0.93 for Other cases and 1.20 for specific disorders. That is low enough to signal ambiguity but not low enough for a simple abstention rule to separate the classes cleanly. The implication is that CultureDx likely needs a dedicated counseling/residual detector rather than another generic calibration threshold.

## 6.4 The Gate Is Cheap Insurance

The comorbidity gate has the intended qualitative behavior. It removes a clinically implausible forbidden pair (`F20+F32`) in exactly one validation case and leaves all headline metrics essentially unchanged. This is the right failure mode for a rule like this. A forbidden-pair gate should not be expected to carry benchmark performance; it should exist to prevent low-frequency but high-cost errors that remain possible after LLM-based verification.

## 6.5 Structural Gains Persist Across Backbones

The multi-backbone slice suggests that the architecture is doing real work rather than merely amplifying the strongest model. DtV improves Overall by +0.190 on Qwen3-8B BF16, +0.262 on Qwen3-8B AWQ, +0.104 on Qwen3-14B AWQ, and +0.045 on Qwen3-32B AWQ. The largest gains appear where model capacity or quantization pressure is strongest, which is consistent with the idea that explicit decomposition offloads tasks that smaller models handle poorly in a single generation.
