# Gap F Gated TF-IDF Expansion Sweep

**Date:** 2026-05-01 23:55:39
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** CPU-only sweep. Uncommitted.

## TL;DR

Tests multiple gating criteria for SELECTIVELY invoking TF-IDF expansion. The blanket union (G_ALL) is the upper bound for both recall and noise; G_NEVER is Qwen3-alone (low recall, low noise). Gates aim to recover the recall benefit only on cases that need it.

**Goal:** identify a gate that captures most of the recall benefit on size=2 cases while keeping size=1 noise low.

---

## §Gate sweep results

| Gate | size=2 fire rate | **size=2 coverage** | size=1 fire rate | **size=1 noise/case** |
|---|---:|---:|---:|---:|
| G_ALL (always expand) | 100.0% | **79.0%** | 100.0% | **5.75** |
| G_NEVER (Qwen alone) | 0.0% | **56.8%** | 0.0% | **3.93** |
| G_LOW_MARGIN (top1-top2 met gap <0.05) | 11.1% | **60.5%** | 14.1% | **4.19** |
| G_QWEN_GEMMA_DISAGREE | 85.2% | **75.3%** | 0.0% | **3.93** |
| G_PRIMARY_NOT_CONFIRMED (1B-α-style) | 4.9% | **58.0%** | 6.9% | **4.04** |
| G_PAIR_CLASSES (primary in F3x/F4x) | 96.3% | **79.0%** | 94.7% | **5.66** |
| G_CHECKER_AMBIG (≥4 confirmed) | 98.8% | **79.0%** | 96.0% | **5.67** |
| G_ANY_TWO (≥2 triggers fire) | 86.4% | **75.3%** | 18.6% | **4.26** |

---

## §Pareto analysis

**Reference points:**
- G_ALL: size=2 = 79.0%, size=1 noise = 5.75
- G_NEVER: size=2 = 56.8%, size=1 noise = 3.93
- G_ALL recall lift over G_NEVER: +22.2pp
- G_ALL noise cost over G_NEVER: +1.82

**Best gates by recall-recovery / noise-saving ratio:**

| Gate | Recall recovered | Noise saved | Recall/Noise ratio |
|---|---:|---:|---:|
| G_LOW_MARGIN (top1-top2 met gap <0.05) | +3.7pp | -1.56 | 2.4 |
| G_QWEN_GEMMA_DISAGREE | +18.5pp | -1.82 | 10.2 |
| G_PRIMARY_NOT_CONFIRMED (1B-α-style) | +1.2pp | -1.71 | 0.7 |
| G_PAIR_CLASSES (primary in F3x/F4x) | +22.2pp | -0.10 | 233.5 |
| G_CHECKER_AMBIG (≥4 confirmed) | +22.2pp | -0.08 | 282.1 |
| G_ANY_TWO (≥2 triggers fire) | +18.5pp | -1.49 | 12.5 |

---

## §Recommendation

Best gated trigger: **G_QWEN_GEMMA_DISAGREE** — captures most of the recall benefit while saving substantial noise.
