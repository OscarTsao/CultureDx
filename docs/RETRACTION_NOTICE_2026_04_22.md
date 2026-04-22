# Retraction Notice — 2026-04-22

## Affected experiments

### WS-C Experiment 1: TF-IDF Cross-Dataset (commit 5f04416)
**Status**: RETRACTED — results not usable for paper claims.
**Issue**: TF-IDF trained on LingxiDiag-16K predicts ~100% "Others" on MDD-5k
due to fundamental text format mismatch (clinical notes vs synthetic dialogue).
The cross-dataset degradation numbers do not reflect meaningful generalization failure.
**Resolution**: Need domain-adapted TF-IDF or shared feature representation. 
Deferred — not blocking paper.

### WS-C Experiment 2: Novel-Class Expansion (commit 2308358)
**Status**: RETRACTED as generalization evidence. Negative result retained as honest finding.
**Issue**: 0% recall across all 5 novel classes (G47, F50, F34, F30, F90) despite
criteria JSON additions. LLM backbone cannot reliably detect novel classes through
criteria-based prompting alone.
**Resolution**: Reported as negative finding in paper. Not a bug — genuine limitation.

## Unaffected experiments
- WS-C Experiment 3: R6v2 bias transfer (commit 0201b97) — VALID, G3 gate passed
- All v2.5 stacker results — VALID
- All LingxiDiag ablation runs (R21v3, R6v2, R20v2) — VALID
- WS-A DSM-5 translator — VALID
- WS-B ensemble null result — VALID
- WS-D standards.py + DSM-5 criteria — VALID
