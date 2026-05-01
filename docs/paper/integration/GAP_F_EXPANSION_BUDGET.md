# Gap F Expansion Budget Sweep

**Date:** 2026-05-01 23:57:44
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** CPU-only sweep. Uncommitted.

## TL;DR

How many TF-IDF unique candidates per case maximizes recall while minimizing noise?
Tests budgets {0, 1, 2, 3, 5, 10} across 3 gates.

---

## §Sweep table — size=2 coverage / size=1 noise

| Gate | Budget B | size=2 coverage | size=1 noise/case |
|---|---:|---:|---:|
| G_ALL | 0 | 56.8% | 3.93 |
| G_ALL | 1 | 70.4% | 4.82 |
| G_ALL | 2 | 77.8% | 5.80 |
| G_ALL | 3 | 82.7% | 6.79 |
| G_ALL | 5 | 96.3% | 8.79 |
| G_ALL | 10 | 100.0% | 10.99 |
| G_LOW_MARGIN | 0 | 56.8% | 3.93 |
| G_LOW_MARGIN | 1 | 60.5% | 4.05 |
| G_LOW_MARGIN | 2 | 60.5% | 4.19 |
| G_LOW_MARGIN | 3 | 60.5% | 4.33 |
| G_LOW_MARGIN | 5 | 63.0% | 4.61 |
| G_LOW_MARGIN | 10 | 63.0% | 4.93 |
| G_ANY_TWO | 0 | 56.8% | 3.93 |
| G_ANY_TWO | 1 | 60.5% | 4.09 |
| G_ANY_TWO | 2 | 60.5% | 4.27 |
| G_ANY_TWO | 3 | 61.7% | 4.46 |
| G_ANY_TWO | 5 | 64.2% | 4.83 |
| G_ANY_TWO | 10 | 64.2% | 5.24 |

---

## §Per-gate Pareto curves

### G_ALL

| B | size=2 cov | size=1 noise | recall/noise marginal |
|---:|---:|---:|---:|
| 0 | 56.8% | 3.93 | — |
| 1 | 70.4% | 4.82 | 15.2 |
| 2 | 77.8% | 5.80 | 7.5 |
| 3 | 82.7% | 6.79 | 5.0 |
| 5 | 96.3% | 8.79 | 6.8 |
| 10 | 100.0% | 10.99 | 1.7 |

### G_LOW_MARGIN

| B | size=2 cov | size=1 noise | recall/noise marginal |
|---:|---:|---:|---:|
| 0 | 56.8% | 3.93 | — |
| 1 | 60.5% | 4.05 | 30.5 |
| 2 | 60.5% | 4.19 | 0.0 |
| 3 | 60.5% | 4.33 | 0.0 |
| 5 | 63.0% | 4.61 | 8.8 |
| 10 | 63.0% | 4.93 | 0.0 |

### G_ANY_TWO

| B | size=2 cov | size=1 noise | recall/noise marginal |
|---:|---:|---:|---:|
| 0 | 56.8% | 3.93 | — |
| 1 | 60.5% | 4.09 | 22.6 |
| 2 | 60.5% | 4.27 | 0.0 |
| 3 | 61.7% | 4.46 | 6.8 |
| 5 | 64.2% | 4.83 | 6.7 |
| 10 | 64.2% | 5.24 | 0.0 |

---

## §Recommendation

**Best (gate, budget) for ≥70% size=2 coverage minimizing noise:**
- Gate: G_ALL, Budget: 1
- size=2 coverage: 70.4%
- size=1 noise/case: 4.82
