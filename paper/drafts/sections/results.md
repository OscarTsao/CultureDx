# 5. Results

## 5.1 Main Results

The committed comparison table places CultureDx first among the LLM-based methods currently tracked in the paper materials.

| Method | Type | 2c Acc | 4c Acc | 12c Top-1 | 12c Top-3 | Overall |
|--------|------|--------|--------|-----------|-----------|---------|
| TF-IDF + LR | ML | .753 | .476 | .496 | .645 | .533 |
| Grok-4.1-Fast | LLM | .841 | .470 | .465 | .495 | .521 |
| Claude-Haiku-4.5 | LLM | .825 | .444 | .478 | .501 | .516 |
| Gemini-3-Flash | LLM | .854 | .422 | .492 | .574 | .510 |
| GPT-5-Mini | LLM | .803 | .434 | .487 | .505 | .504 |
| DeepSeek-V3.2 | LLM | .820 | .441 | .438 | .489 | .501 |
| **CultureDx (ours)** | **MAS** | **.812** | **.448** | **.523** | **.599** | **.527** |

CultureDx does not beat the best traditional baseline in this table, but it narrows the gap to 0.006 Overall while ranking first among the committed LLM-based systems. This is a meaningful result because the system achieves it through explicit verification and deterministic diagnosis logic rather than by simply scaling up unconstrained generation.

## 5.2 Validation Ablations

| Row | Config | 2c Acc | 2c F1m | 4c Acc | 4c F1m | 12c Acc | 12c Top-1 | 12c Top-3 | 12c F1m | Overall |
|-----|--------|--------|--------|--------|--------|---------|-----------|-----------|---------|---------|
| 01 | Single | .753 | .708 | .404 | .379 | .249 | .478 | .575 | .167 | .482 |
| 02 | Single + RAG | .792 | .752 | .354 | .306 | .024 | .541 | .702 | .198 | .469 |
| 03 | DtV V1 | .733 | .701 | .411 | .374 | .252 | .456 | .532 | .174 | .475 |
| 04 | DtV V1 + RAG | .765 | .752 | .440 | .395 | .262 | .500 | .571 | .210 | .480 |
| 05 | **DtV V2 + RAG** | **.812** | **.794** | **.448** | **.408** | **.317** | **.523** | **.599** | .193 | **.527** |
| 06 | DtV V2 + RAG + Gate | .808 | .790 | .451 | .407 | .316 | .520 | .597 | **.194** | .526 |

Three patterns stand out. First, diagnose-then-verify is stronger than the single baseline once retrieval and the V2 prompts are combined: Row 05 improves over Row 01 by +0.045 Overall, +0.068 in 12-class exact accuracy, and +0.045 in 12-class top-1. Second, retrieval alone is not enough. Row 02 increases top-3 recall to .702, but its 12-class exact accuracy collapses to .024, showing that similar-case retrieval without criterion verification encourages broad but poorly controlled predictions. Third, the comorbidity gate has almost no effect on headline performance, confirming that the main gain comes from the verification stack rather than from a late-stage rule patch.

## 5.4 Multi-Backbone Robustness

The same architectural pattern transfers to smaller backbones in the partial multi-backbone validation runs.

| Backbone | Single | DtV | Delta |
|----------|--------|-----|-------|
| Qwen3-8B BF16 | .318 | .508 | +.190 |
| Qwen3-8B AWQ | .228 | .491 | +.262 |
| Qwen3-14B AWQ | .371 | .475 | +.104 |
| Qwen3-32B AWQ | .482 | .527 | +.045 |

DtV improves every tested backbone. The gain is largest for the smaller and more heavily compressed models, which suggests that structural decomposition compensates for limited model capacity better than pure prompt-only scaling.

## 5.5 Comorbidity and Safety Effects

Compared with the single baseline, the best DtV configuration substantially improves multi-label consistency. Subset accuracy rises from .019 to .317, hamming accuracy rises from .311 to .454, and label precision rises from .318 to .474. At the same time, the average number of predicted labels drops from 2.094 to 1.358, indicating that the verification stack reduces indiscriminate over-prediction.

The explicit comorbidity gate is best interpreted as a safety net rather than as a performance driver. The committed gate re-score analysis shows that it changes only 1 of 1000 validation cases by removing the forbidden pair `F20+F32`, with negligible overall metric change.
