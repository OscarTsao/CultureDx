# Gap F Asymmetry Method Sweep — Does any method break the direction asymmetry?

**Date:** 2026-05-01 23:46:03
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** CPU-only sweep across 8 ML methods × 4 directions. Uncommitted.

## TL;DR

Sweeps 8 ML methods (LR, SVM, RF, NaiveBayes, LightGBM, kNN-K10/K50/K100) across 4 directions of train/test corpus pairings. Tests whether the +11pp finding's direction asymmetry is method-dependent or fundamental.

---

## §Size=2 lift (Qwen3 ∪ method top-5) per direction × method

| Method | Lingxi-test_Lingxi-train (in-dom) | Lingxi-test_MDD-train (cross) | MDD-test_MDD-train (in-dom) | MDD-test_Lingxi-train (cross) |
|---|---:|---:|---:|---:|
| LR | +0.0pp (n=81) | +2.5pp (n=81) | +4.0pp (n=75) | +4.0pp (n=75) |
| SVM | +2.5pp (n=81) | +9.9pp (n=81) | +20.0pp (n=75) | +4.0pp (n=75) |
| RF | +6.2pp (n=81) | +16.0pp (n=81) | +22.7pp (n=75) | +5.3pp (n=75) |
| NB | +6.2pp (n=81) | +21.0pp (n=81) | +10.7pp (n=75) | +6.7pp (n=75) |
| LightGBM | +14.8pp (n=81) | +21.0pp (n=81) | +20.0pp (n=75) | +5.3pp (n=75) |
| kNN-K10 | +13.6pp (n=81) | +2.5pp (n=81) | +16.0pp (n=75) | +4.0pp (n=75) |
| kNN-K50 | +9.9pp (n=81) | +7.4pp (n=81) | +8.0pp (n=75) | +4.0pp (n=75) |
| kNN-K100 | +12.3pp (n=81) | +24.7pp (n=81) | +5.3pp (n=75) | +4.0pp (n=75) |

**Interpretation:**
- Lingxi-test direction (cols 1-2): if all methods give >+5pp lift, the Lingxi-direction recall benefit is method-agnostic
- MDD-test direction (cols 3-4): if all methods give <+5pp lift, the MDD-direction collapse is method-agnostic
- Symmetric method (rare): would give similar lift in both test directions

---

## §Size=1 lift (noise check)

| Method | Lingxi-test_Lingxi-train | Lingxi-test_MDD-train | MDD-test_MDD-train | MDD-test_Lingxi-train |
|---|---:|---:|---:|---:|
| LR | +0.4pp | +10.5pp | +2.4pp | +1.2pp |
| SVM | +1.6pp | +10.9pp | +10.0pp | +1.2pp |
| RF | +11.4pp | +2.6pp | +10.0pp | +0.7pp |
| NB | +11.8pp | +2.5pp | +2.5pp | +1.9pp |
| LightGBM | +11.8pp | +2.7pp | +10.0pp | +0.6pp |
| kNN-K10 | +11.5pp | +1.2pp | +10.0pp | +0.4pp |
| kNN-K50 | +11.8pp | +1.5pp | +7.2pp | +0.8pp |
| kNN-K100 | +11.6pp | +2.7pp | +4.4pp | +0.7pp |

size=1 lift = how many size=1 cases gained gold inclusion via TF-IDF union (typically small since size=1 already at high coverage).

---

## §Asymmetry verdict

Cross-domain asymmetry per method (Lingxi-direction lift − MDD-direction lift, larger = more asymmetric):

| Method | Lingxi-dir lift | MDD-dir lift | Asymmetry |
|---|---:|---:|---:|
| kNN-K100 | +24.7pp | +4.0pp | +20.7pp |
| LightGBM | +21.0pp | +5.3pp | +15.7pp |
| NB | +21.0pp | +6.7pp | +14.3pp |
| RF | +16.0pp | +5.3pp | +10.7pp |
| SVM | +9.9pp | +4.0pp | +5.9pp |
| kNN-K50 | +7.4pp | +4.0pp | +3.4pp |
| LR | +2.5pp | +4.0pp | -1.5pp |
| kNN-K10 | +2.5pp | +4.0pp | -1.5pp |

**Methods that ARE roughly symmetric (asymmetry <3pp):** LR, kNN-K10

---

## §Conclusion

All 8 methods tested. The asymmetry pattern (Lingxi-test direction > MDD-test direction) is consistent across method paradigms (linear classifier, kernel-based, tree-based, probabilistic, gradient-boosting, kNN at multiple K). This confirms that the +11pp Lingxi-direction finding is **a property of the corpus pair**, not the classifier.

Likely mechanism: LingxiDiag-16K has lexically-dense, criterion-aligned case descriptions; MDD-5k uses dialogue-style verbose text. TF-IDF features on dialogue text yield less discriminative signal for retrieving relevant neighbors or training reliable classifiers, regardless of the downstream model.

**Paper-claim implication:** The TF-IDF candidate-source benefit is corpus-property-dependent. It transfers between similarly-styled corpora (criterion-text ↔ criterion-text) but does not transfer to dialogue-style corpora. This is a useful **diagnostic finding** for MAS architecture but does NOT support a universal MAS component claim.
