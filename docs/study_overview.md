# Study Overview

This document gathers the repo's study design, methods, architecture, major
experiment families, and committed results into one place.

It is intentionally conservative:

- it summarizes committed scripts, docs, and result artifacts in this repo
- it avoids claiming improvements that are not backed by committed outputs
- it separates completed evaluation from ongoing or partially documented work

For the more narrative paper framing, see
[paper_narrative_v2.md](/home/user/YuNing/CultureDx/docs/paper_narrative_v2.md).
For the repo operating manual, see
[AGENTS.md](/home/user/YuNing/CultureDx/AGENTS.md).

## 1. Research Scope

CultureDx studies culture-adaptive psychiatric differential diagnosis from
clinical dialogue, with emphasis on Chinese and cross-lingual settings.

The core research questions visible in the repo are:

1. Can a hybrid architecture combine LLM extraction with deterministic
   diagnostic logic to reduce error compounding?
2. Does explicit evidence grounding help on culturally embedded Chinese
   presentations?
3. Which component is the actual bottleneck:
   detection, ranking, calibration, or comorbidity resolution?
4. How much of the remaining error comes from criterion overlap, especially
   F32 vs F41.1?

The repo contains both system code and research analysis artifacts. The most
important completed evaluation line is the final 18-condition sweep summarized
in [paper_results_table.md](/home/user/YuNing/CultureDx/outputs/paper_results_table.md).

## 2. Methods And Architecture Used

### 2.1 System Pattern

CultureDx is not a single end-to-end prompt. The main system combines:

- LLM-based routing and criterion checking
- deterministic ICD-10 threshold logic
- statistical calibration
- rule-based comorbidity filtering
- optional evidence extraction and Chinese somatization normalization

The main diagnosis orchestrator is
[hied.py](/home/user/YuNing/CultureDx/src/culturedx/modes/hied.py).

### 2.2 Main Diagnosis Pipeline

The primary research path is `HiED`:

1. triage broad disorder categories
2. run per-disorder criterion checkers
3. apply deterministic ICD-10 threshold logic
4. calibrate confidence and split primary/comorbid/rejected
5. optionally rerank or run differential disambiguation
6. apply comorbidity rules and exclusions

Key implementation files:

- [hied.py](/home/user/YuNing/CultureDx/src/culturedx/modes/hied.py)
- [logic_engine.py](/home/user/YuNing/CultureDx/src/culturedx/diagnosis/logic_engine.py)
- [calibrator.py](/home/user/YuNing/CultureDx/src/culturedx/diagnosis/calibrator.py)
- [comorbidity.py](/home/user/YuNing/CultureDx/src/culturedx/diagnosis/comorbidity.py)
- [triage.py](/home/user/YuNing/CultureDx/src/culturedx/agents/triage.py)
- [triage_routing.py](/home/user/YuNing/CultureDx/src/culturedx/agents/triage_routing.py)

### 2.3 Evidence Pipeline

The evidence pipeline is a separate subsystem that can be enabled or disabled
per experiment condition.

Its stages are:

1. symptom extraction
2. Chinese somatization mapping
3. temporal feature extraction where relevant
4. criterion retrieval and matching
5. evidence brief assembly

Key implementation files:

- [pipeline.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/pipeline.py)
- [extractor.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/extractor.py)
- [somatization.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/somatization.py)
- [temporal.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/temporal.py)
- [retriever.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/retriever.py)
- [criteria_matcher.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/criteria_matcher.py)

### 2.4 Reasoning Modes Studied

The main compared modes are:

- `single`
  one-shot baseline
- `hied`
  hierarchical evidence-grounded path
- `psycot`
  checker-driven path without triage
- `specialist`
  specialist-agent ensemble
- `debate`
  debate-style ensemble

The final paper-style results table currently focuses on:

- Single
- HiED
- PsyCoT

### 2.5 Calibration, Selective Prediction, And Routing

Two separate calibration layers exist:

- triage routing calibration:
  [triage_routing.py](/home/user/YuNing/CultureDx/src/culturedx/agents/triage_routing.py)
- diagnosis confidence calibration:
  [calibrator.py](/home/user/YuNing/CultureDx/src/culturedx/diagnosis/calibrator.py)

The repo now supports learned artifact paths for both, but the committed
research story remains partly heuristic because not every deployed path has a
fully committed trained artifact.

### 2.6 Serving / Runtime

Inference backends include:

- Ollama
- vLLM

Relevant files:

- [client.py](/home/user/YuNing/CultureDx/src/culturedx/llm/client.py)
- [runtime.py](/home/user/YuNing/CultureDx/src/culturedx/llm/runtime.py)
- [vllm_client.py](/home/user/YuNing/CultureDx/src/culturedx/llm/vllm_client.py)

## 3. Datasets And Evaluation Setup

### 3.1 Main Datasets Referenced In The Repo

- `LingxiDiag-16k`
  Chinese psychiatric dialogue dataset used as the main culturally embedded
  evaluation set
- `MDD-5k`
  another Chinese psychiatric dataset, but with more explicit symptom wording
- `E-DAIC`
  used for auxiliary ablation work such as scale-score experiments

Dataset adapters live under
[data/adapters](/home/user/YuNing/CultureDx/src/culturedx/data/adapters).

### 3.2 Main Experiment Scripts

- [pilot_experiment.py](/home/user/YuNing/CultureDx/scripts/pilot_experiment.py)
  small pilot comparisons across modes
- [ablation_sweep.py](/home/user/YuNing/CultureDx/scripts/ablation_sweep.py)
  main evaluation matrix
- [mcnemar_final.py](/home/user/YuNing/CultureDx/scripts/mcnemar_final.py)
  pairwise significance testing
- [validate_calibrator_update.py](/home/user/YuNing/CultureDx/scripts/validate_calibrator_update.py)
  offline validation of calibrator changes
- [analyze_comorbidity.py](/home/user/YuNing/CultureDx/scripts/analyze_comorbidity.py)
  comorbidity metrics and error analysis

### 3.3 Main Evaluation Conventions

The repo uses both:

- parent-normalized metrics
  for disorder-family-level matching
- exact-match metrics
  for stricter code-level matching

Common metrics include:

- Top-1 accuracy
- Top-3 accuracy
- macro F1
- recall for high-interest disorder groups such as F32 and F41
- bootstrap confidence intervals
- McNemar exact tests on paired predictions

## 4. Experiment Inventory

### 4.1 Final 18-Condition Sweep

This is the main paper-style evaluation artifact family.

Primary summary files:

- [paper_results_table.md](/home/user/YuNing/CultureDx/outputs/paper_results_table.md)
- [bootstrap_ci_final.md](/home/user/YuNing/CultureDx/outputs/bootstrap_ci_final.md)
- [mcnemar_final.md](/home/user/YuNing/CultureDx/outputs/mcnemar_final.md)
- [evidence_gap_analysis.md](/home/user/YuNing/CultureDx/outputs/evidence_gap_analysis.md)

Scope:

- 3 modes:
  Single, HiED, PsyCoT
- 3 evidence conditions:
  none, BGE-M3 evidence, BGE-M3 evidence without somatization
- 2 datasets:
  LingxiDiag-16k and MDD-5k
- `N=200` per condition in the paper-ready tables

### 4.2 Pilot Experiments

Pilot experiments are implemented and partially archived in:

- [pilot_experiment.py](/home/user/YuNing/CultureDx/scripts/pilot_experiment.py)
- `outputs/pilot_*`

These are useful for repo history and prototyping, but they are not the main
artifact line to cite when reporting the matured system.

### 4.3 Calibration And Ranking Studies

Relevant committed artifacts:

- [calibrator_tuning_results.json](/home/user/YuNing/CultureDx/outputs/calibrator_tuning_results.json)
- [calibrator_update_validation.json](/home/user/YuNing/CultureDx/outputs/calibrator_update_validation.json)

These analyze weight tuning and offline effects of calibrator updates.

### 4.4 Comorbidity Studies

Relevant committed artifacts:

- [comorbidity_analysis.md](/home/user/YuNing/CultureDx/outputs/comorbidity_analysis.md)
- [comorbidity_analysis.json](/home/user/YuNing/CultureDx/outputs/comorbidity_analysis.json)
- [comorbidity_classifier_results.json](/home/user/YuNing/CultureDx/outputs/comorbidity_classifier_results.json)
- [comorbidity_threshold_tuning.json](/home/user/YuNing/CultureDx/outputs/comorbidity_threshold_tuning.json)

### 4.5 Cross-Lingual / Evidence-Gap Studies

Relevant committed artifacts:

- [evidence_gap_analysis.md](/home/user/YuNing/CultureDx/outputs/evidence_gap_analysis.md)
- [evidence_gap_analysis.json](/home/user/YuNing/CultureDx/outputs/evidence_gap_analysis.json)

### 4.6 Scale-Score And Demographic Ablations

Relevant committed artifacts:

- [scale_score_impact.json](/home/user/YuNing/CultureDx/outputs/scale_score_impact.json)
- [demographics_ablation.json](/home/user/YuNing/CultureDx/outputs/demographics_ablation.json)

### 4.7 Somatization Benchmark Infrastructure

This is a research infrastructure contribution rather than a completed empirical
benchmark result.

Relevant files:

- [somatization_benchmark.md](/home/user/YuNing/CultureDx/docs/somatization_benchmark.md)
- [somatization_dataset.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/somatization_dataset.py)
- [somatization_benchmark.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/somatization_benchmark.py)

### 4.8 Temporal Tool Evaluation

A small committed comparison harness exists for deterministic temporal parsing:

- [eval_temporal_tools.py](/home/user/YuNing/CultureDx/scripts/eval_temporal_tools.py)
- [temporal_eval_results.json](/home/user/YuNing/CultureDx/outputs/temporal_eval_results.json)

This is a tool-comparison harness, not a full benchmark paper result.

### 4.9 SFT / Fine-Tuning Pipeline

The repo also contains a criterion-checker SFT pipeline:

- [prepare_sft_dataset.py](/home/user/YuNing/CultureDx/scripts/prepare_sft_dataset.py)
- [finetune_checker.py](/home/user/YuNing/CultureDx/scripts/finetune_checker.py)
- teacher dataset metadata:
  [teacher_config.json](/home/user/YuNing/CultureDx/data/sft/teacher_v1/teacher_config.json)

The pipeline is real and committed, but the model cards in `outputs/finetune/`
remain mostly placeholders. This means the training path is present, but the
repo does not yet contain a clean, reviewer-ready final fine-tune report.

## 5. Main Results From Committed Artifacts

### 5.1 Final 18-Condition Sweep: Best Conditions

From [paper_results_table.md](/home/user/YuNing/CultureDx/outputs/paper_results_table.md):

| Dataset | Metric family | Best condition | Result |
|---|---|---|---:|
| LingxiDiag-16k | Parent-normalized Top-1 | HiED + BGE-M3 evidence | 45.0% |
| LingxiDiag-16k | Parent-normalized Top-3 | HiED + BGE-M3 evidence | 74.0% |
| LingxiDiag-16k | Exact Top-1 | Single + BGE-M3 evidence | 36.0% |
| MDD-5k | Parent-normalized Top-1 | Single, no evidence | 52.5% |
| MDD-5k | Parent-normalized Top-3 | Single, no evidence | 76.5% |
| MDD-5k | Exact Top-1 | HiED, no evidence | 40.5% |

### 5.2 Evidence Effect Is Dataset-Dependent

The strongest artifact-backed finding is the asymmetry between datasets.

From [evidence_gap_analysis.md](/home/user/YuNing/CultureDx/outputs/evidence_gap_analysis.md):

- LingxiDiag HiED Top-1:
  `0.410 -> 0.450` with evidence, `+4.0pp`
- MDD-5k HiED Top-1:
  `0.520 -> 0.460` with evidence, `-6.0pp`
- Average evidence delta across modes:
  `+1.3pp` on LingxiDiag and `-5.8pp` on MDD-5k

Interpretation supported by the artifacts:

- evidence helps more culturally embedded Chinese presentations
- the same evidence stack can hurt more explicit symptom-report datasets

### 5.3 Somatization Helps LingxiDiag Mainly Through F41

From [evidence_gap_analysis.md](/home/user/YuNing/CultureDx/outputs/evidence_gap_analysis.md):

- LingxiDiag, HiED:
  evidence with somatization vs without somatization = `+3.5pp` Top-1
- LingxiDiag, HiED, F41:
  `0.254 -> 0.394`, `+14.1pp`
- LingxiDiag, HiED, F32:
  `0.838 -> 0.797`, `-4.0pp`

This supports the repo's culture-adaptive hypothesis:

- somatization mapping is load-bearing for anxiety-like Chinese bodily idioms
- but it can trade off against depression ranking in overlap-heavy settings

### 5.4 Evidence Changes Detection More Than Ranking

From [paper_results_table.md](/home/user/YuNing/CultureDx/outputs/paper_results_table.md):

- LingxiDiag single:
  Top-1 `40.5`, Top-3 `52.5 -> 73.0`
- LingxiDiag HiED:
  Top-1 `41.0 -> 45.0`, Top-3 `63.0 -> 74.0`
- MDD-5k single:
  Top-1 `52.5 -> 47.0`, Top-3 `76.5 -> 62.5`

The pattern suggests that the evidence stack often expands plausible candidate
coverage, but the downstream ranking and disambiguation layers remain the real
bottleneck.

## 6. Statistical Support

### 6.1 Bootstrap Confidence Intervals

From [bootstrap_ci_final.md](/home/user/YuNing/CultureDx/outputs/bootstrap_ci_final.md):

- LingxiDiag, HiED evidence vs no evidence:
  Top-1 `+4.0pp [-1.5, 9.5]`
  Top-3 `+11.0pp [7.0, 15.5]`
  Macro F1 `+1.9pp [0.3, 3.8]`
- LingxiDiag, somatization effect within HiED:
  F41 recall `+12.3pp [2.5, 22.5]`
- MDD-5k, HiED evidence vs no evidence:
  Top-1 `-7.5pp [-15.0, 0.0]`
  Top-3 `-10.0pp [-17.0, -3.5]`
  F32 recall `-28.9pp [-40.7, -17.4]`
  F41 recall `+15.6pp [1.5, 29.1]`

The artifact-supported conclusion is not just "evidence helps" or "evidence
hurts." It is:

- LingxiDiag:
  evidence materially improves candidate recovery and macro-level performance
- MDD-5k:
  evidence shifts recall from F32 toward F41 and lowers overall accuracy

### 6.2 McNemar Exact Tests

From [mcnemar_final.md](/home/user/YuNing/CultureDx/outputs/mcnemar_final.md):

- family-wise alpha: `0.05`
- Bonferroni-corrected alpha: `0.0083`
- no listed pairwise comparison survives Bonferroni correction

This matters for reporting discipline:

- the sweep shows consistent directional effects
- but the repo's committed exact paired tests do not support strong corrected
  significance claims for those pairwise comparisons

## 7. Error And Bottleneck Findings

### 7.1 Ranking Is Still The Main Bottleneck

The repo narrative and committed analyses consistently point to a separation
between:

- criterion detection / candidate recovery
- final ranking among overlap-heavy diagnoses

This is visible in:

- large Top-3 gains that do not fully translate into Top-1 gains
- calibrator and evidence-gap analyses
- repeated F32 vs F41 tradeoffs

### 7.2 F32 vs F41.1 Is The Dominant Structural Confusion

Across the committed analyses, the recurring failure mode is overlap between
depression and generalized anxiety criteria.

Evidence for this comes from:

- [paper_narrative_v2.md](/home/user/YuNing/CultureDx/docs/paper_narrative_v2.md)
- [evidence_gap_analysis.md](/home/user/YuNing/CultureDx/outputs/evidence_gap_analysis.md)
- [comorbidity_analysis.md](/home/user/YuNing/CultureDx/outputs/comorbidity_analysis.md)

The committed artifact story is:

- evidence and somatization often boost F41 recall
- but these gains can come with F32 tradeoffs
- overlap-heavy criteria make post-hoc ranking hard even when detection improves

### 7.3 Comorbidity Is Structurally Over-Predicted

From [comorbidity_analysis.md](/home/user/YuNing/CultureDx/outputs/comorbidity_analysis.md):

- gold comorbidity rate: `10.2%`
- predicted comorbidity rate: `67.0%`
- over-prediction factor: `6.5x`
- F32+F41 precision: `3.8%`

The strongest conclusion in that artifact is that current criterion-checker
features are not sufficient to discriminate true comorbidity from overlap-based
false positives.

The accompanying LightGBM analysis reaches:

- AUC `0.61`
- better subset accuracy only by suppressing all comorbidity predictions

So the repo's current evidence supports a negative result:

- current feature sets are too weak for reliable comorbidity classification

## 8. Calibration, Demographics, And Scale-Score Findings

### 8.1 Calibrator Tuning

From [calibrator_tuning_results.json](/home/user/YuNing/CultureDx/outputs/calibrator_tuning_results.json):

- baseline total accuracy: `0.446`
- pooled training accuracy after optimization: `0.514`
- leave-one-out test accuracy:
  `0.479` on MDD-5k style split, `0.433` on LingxiDiag style split

This should be interpreted cautiously:

- these are tuning/validation artifacts, not the same as the final deployed
  paper table
- they show that calibrator weights matter
- they do not by themselves prove a universally improved deployed calibrator

### 8.2 Offline Calibrator Update Validation

From [calibrator_update_validation.json](/home/user/YuNing/CultureDx/outputs/calibrator_update_validation.json):

- `v10_lingxidiag`: `+1.5pp`
- `v10_mdd5k`: `+6.0pp`

This is useful evidence that ranking tweaks can move accuracy, but it is still
an offline replay analysis over saved sweeps.

### 8.3 Demographic Prior Ablation

From [demographics_ablation.json](/home/user/YuNing/CultureDx/outputs/demographics_ablation.json):

- effect is small to negligible
- best reported LingxiDiag gain is `+0.5pp`
- cross-validation style result slightly regresses

So demographic priors are not a major committed driver of the current system.

### 8.4 Scale-Score Impact On E-DAIC

From [scale_score_impact.json](/home/user/YuNing/CultureDx/outputs/scale_score_impact.json):

- `hied_no_evidence`: Top-1 `12.7 -> 28.6`, `+15.9pp`
- `hied_bge-m3_evidence`: Top-1 `20.6 -> 38.1`, `+17.5pp`
- `hied_bge-m3_no_somatization`: `0.0 -> 38.1`

These are auxiliary results and should be reported as such. They are not the
same evaluation regime as the main LingxiDiag / MDD-5k final sweep.

## 9. Deterministic Module Studies

### 9.1 Temporal Tool Comparison

From [temporal_eval_results.json](/home/user/YuNing/CultureDx/outputs/temporal_eval_results.json):

- `regex_current`: 13/20 cases with non-null `estimated_months`
- `jionlp`: 5/20
- `dateparser`: 4/20
- `ChineseTimeNLP`: 16/20
- `stanza`: 15/20

This should not be over-read as a production leaderboard:

- the harness is small
- non-null month conversion is not the whole quality story
- external parsers still have false-positive and semantic-mismatch issues

The committed takeaway is:

- the repo has begun tool-level temporal evaluation
- no single external parser is yet cleanly documented as a drop-in replacement

### 9.2 Somatization Benchmark Status

From [somatization_benchmark.md](/home/user/YuNing/CultureDx/docs/somatization_benchmark.md):

- the benchmark schema exists
- loaders, baselines, evaluation harness, review queue, and adjudication flow
  exist
- the repo does not yet ship real expert-labeled benchmark data

This is a method contribution and research infrastructure asset, not yet a
completed empirical benchmark result.

## 10. Training / Fine-Tuning Status

### 10.1 Teacher-Data Generation

From [teacher_config.json](/home/user/YuNing/CultureDx/data/sft/teacher_v1/teacher_config.json):

- teacher model: `Qwen/Qwen3-32B-AWQ`
- total cases: `1000`
- total examples: `4816`
- train / val: `4334 / 482`
- disorders:
  `F32`, `F33`, `F41.1`, `F42`, `F43.1`
- datasets:
  `lingxidiag16k`, `mdd5k_raw`

### 10.2 Fine-Tuning Pipeline

The pipeline is implemented in:

- [prepare_sft_dataset.py](/home/user/YuNing/CultureDx/scripts/prepare_sft_dataset.py)
- [finetune_checker.py](/home/user/YuNing/CultureDx/scripts/finetune_checker.py)

Current training method:

- criterion-checker SFT
- LoRA / QLoRA style setup
- HuggingFace transformers + peft
- base models including Qwen2.5-7B and Qwen3-8B variants

### 10.3 Current Reporting Gap

The repo contains fine-tuning outputs and model directories under `outputs/finetune`,
but the auto-generated model cards are still placeholders.

That means:

- the training path exists
- generated datasets exist
- logs exist
- but the repo does not yet contain a final, reviewer-ready fine-tune result
  report with clean evaluation tables

## 11. What The Repo Can Honestly Claim Today

Based on committed artifacts, the strongest defensible claims are:

1. The repo implements a hybrid psychiatric diagnosis architecture that uses
   deterministic ICD-10 logic rather than pure LLM voting or judging.
2. The main paper-ready result line is the 18-condition sweep over
   LingxiDiag-16k and MDD-5k.
3. Evidence grounding is dataset-dependent:
   it helps LingxiDiag but hurts MDD-5k on committed final-sweep artifacts.
4. Chinese somatization handling is an important part of the LingxiDiag gain,
   especially for F41-like presentations.
5. Ranking and overlap resolution remain the main bottleneck after candidate
   recovery improves.
6. Current comorbidity prediction is structurally weak and over-predictive.

## 12. What The Repo Should Not Claim Yet

The committed artifacts do not yet support claiming:

- universal evidence benefits across datasets
- statistically decisive superiority after multiple-comparison correction
- solved confidence calibration
- solved comorbidity reasoning
- completed fine-tuned checker gains with publication-ready model cards
- completed real-data somatization benchmark scores

## 13. Recommended Citation Order Inside The Repo

If you need to cite the repo's study from another doc or PR, use this order:

1. [paper_results_table.md](/home/user/YuNing/CultureDx/outputs/paper_results_table.md)
2. [bootstrap_ci_final.md](/home/user/YuNing/CultureDx/outputs/bootstrap_ci_final.md)
3. [mcnemar_final.md](/home/user/YuNing/CultureDx/outputs/mcnemar_final.md)
4. [evidence_gap_analysis.md](/home/user/YuNing/CultureDx/outputs/evidence_gap_analysis.md)
5. [comorbidity_analysis.md](/home/user/YuNing/CultureDx/outputs/comorbidity_analysis.md)
6. [paper_narrative_v2.md](/home/user/YuNing/CultureDx/docs/paper_narrative_v2.md)

That order keeps claims closest to their underlying committed evidence.
