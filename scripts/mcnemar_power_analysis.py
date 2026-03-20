"""
McNemar's Test Power Analysis
==============================
Context: CultureDx study comparing prompt styles (hied, single, debate)
on depression/mental-health classification tasks.

Questions answered:
  1. Detectable effect size (difference in proportions) at N=200, alpha=0.05, power=0.80
  2. Probability of significance at N=200 given N=50 pilot: hied=54%, single=56%, debate=58%
  3. Per-pair: expected discordant pairs and power at N=200
"""

import math
import numpy as np
from scipy import stats
from scipy.stats import norm, chi2
from scipy.optimize import brentq

# -----------------------------------------------------------------------
# Helper: McNemar power using normal approximation
# -----------------------------------------------------------------------
# For McNemar's test on N paired samples:
#   b = P(A correct, B wrong)   [discordant favoring A]
#   c = P(A wrong,  B correct)  [discordant favoring B]
#   discordant probability: p_disc = b + c
#   effect parameter:       delta  = |b - c|
#
# Under H0: b = c  =>  Z ~ N(0,1)
# Test statistic: Z = (b_obs - c_obs) / sqrt(b_obs + c_obs)
#
# Power formula (Schork & Williams, 1980 / Lachenbruch 1992):
#   n_disc = N * p_disc
#   lambda = delta * sqrt(N) / sqrt(p_disc)  (non-centrality)
#   Power = P(|Z| > z_alpha/2)  where Z ~ N(lambda, 1)
#
# We model the joint table using accuracy probabilities pA, pB and
# a correlation parameter rho (assumed 0.5 as a moderate within-subject
# correlation typical for LLM prompt-switching experiments).

def joint_table(pA, pB, rho=0.5):
    """
    Compute 2x2 joint probability table for two binary classifiers
    on the same items, given marginal accuracies pA, pB and
    correlation rho between them.

    Returns (p11, p10, p01, p00):
        p11 = P(A correct, B correct)
        p10 = P(A correct, B wrong)   -- discordant b
        p01 = P(A wrong,   B correct) -- discordant c
        p00 = P(A wrong,   B wrong)
    """
    # Tetrachoric / bivariate Bernoulli parameterisation:
    # Cov(A,B) = rho * sqrt(pA*(1-pA)) * sqrt(pB*(1-pB))
    cov = rho * math.sqrt(pA * (1 - pA) * pB * (1 - pB))
    p11 = pA * pB + cov
    p10 = pA - p11          # = pA*(1-pB) - cov
    p01 = pB - p11          # = pB*(1-pA) - cov
    p00 = 1 - p11 - p10 - p01
    # Clamp floating-point noise
    p11 = max(0.0, min(1.0, p11))
    p10 = max(0.0, min(1.0, p10))
    p01 = max(0.0, min(1.0, p01))
    p00 = max(0.0, min(1.0, p00))
    return p11, p10, p01, p00


def mcnemar_power(N, pA, pB, alpha=0.05, rho=0.5):
    """
    Power of McNemar's test for paired proportions pA vs pB
    with N paired observations and within-pair correlation rho.
    Returns (power, n_disc_expected, b, c, p_disc, delta)
    """
    _, b, c, _ = joint_table(pA, pB, rho)
    p_disc = b + c          # probability of a discordant pair
    delta  = abs(b - c)     # |b - c|

    if p_disc < 1e-12:
        return 0.0, 0.0, b, c, p_disc, delta

    n_disc = N * p_disc     # expected discordant pairs
    z_alpha = norm.ppf(1 - alpha / 2)

    # Non-centrality: lambda = delta*sqrt(N) / sqrt(p_disc)
    ncp = delta * math.sqrt(N) / math.sqrt(p_disc)

    # Power = P(Z > z_alpha - ncp) + P(Z < -z_alpha - ncp)
    power = norm.cdf(-z_alpha + ncp) + norm.cdf(-z_alpha - ncp)
    return power, n_disc, b, c, p_disc, delta


# -----------------------------------------------------------------------
# Q1: Minimum detectable effect at N=200, alpha=0.05, power=0.80
# -----------------------------------------------------------------------
# We fix pA = 0.50 (baseline) and sweep pB to find threshold.
# Also report as a function of p_disc.

print("=" * 65)
print("Q1: MINIMUM DETECTABLE EFFECT (N=200, alpha=0.05, power=0.80)")
print("=" * 65)

N_target = 200
ALPHA    = 0.05
POWER_TARGET = 0.80
z_alpha  = norm.ppf(1 - ALPHA / 2)
z_beta   = norm.ppf(POWER_TARGET)

# Analytical formula: minimum detectable delta given p_disc
# Power = 0.80  =>  z_beta = ncp - z_alpha  (one dominant tail)
# => delta = (z_alpha + z_beta) * sqrt(p_disc) / sqrt(N)
print("\n--- Minimum detectable |pA - pB| by assumed p_disc value ---")
print(f"{'p_disc':>8} {'min_delta':>12} {'min |pA-pB|':>14} {'min diff%':>10}")
print("-" * 50)

# For McNemar with marginal pA=pB=p, p_disc ~ 2*p*(1-p)*(1-rho) roughly.
# More useful: vary p_disc directly.
for p_disc_val in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]:
    min_delta = (z_alpha + z_beta) * math.sqrt(p_disc_val) / math.sqrt(N_target)
    # Approximate |pA-pB|: delta = |b-c|, and b+c = p_disc
    # If pA > pB: b < c, delta = c - b; pB - pA ≈ delta (rough)
    min_diff_pct = min_delta * 100
    print(f"{p_disc_val:>8.2f} {min_delta:>12.6f} {'≈ ' + f'{min_diff_pct:.2f}%':>14} {min_diff_pct:>10.2f}")

# Find the specific baseline where p_disc is natural for accuracy ~55%
# and rho=0.5
print("\n--- Minimum detectable accuracy difference by baseline pA ---")
print(f"{'pA':>6} {'pB_min':>9} {'diff_min':>10} {'p_disc':>9} {'n_disc_exp':>12}")
print("-" * 52)

for pA_val in [0.50, 0.54, 0.56, 0.58, 0.60, 0.65, 0.70]:
    def power_fn(pB):
        if pB <= pA_val:
            return 0.0
        pw, _, _, _, _, _ = mcnemar_power(N_target, pA_val, pB, alpha=ALPHA)
        return pw

    # Find minimum pB such that power >= 0.80
    try:
        pB_min = brentq(lambda pB: power_fn(pB) - POWER_TARGET,
                        pA_val + 0.001, 0.999, xtol=1e-6)
        diff_min = pB_min - pA_val
        _, n_disc, b, c, p_disc_val, _ = mcnemar_power(N_target, pA_val, pB_min, alpha=ALPHA)
    except ValueError:
        pB_min = float('nan')
        diff_min = float('nan')
        p_disc_val = float('nan')
        n_disc = float('nan')
    print(f"{pA_val:>6.2f} {pB_min:>9.4f} {diff_min:>10.4f} {p_disc_val:>9.4f} {n_disc:>12.1f}")


# -----------------------------------------------------------------------
# Q2: Power to detect significance at N=200 given N=50 pilot results
# -----------------------------------------------------------------------
print("\n")
print("=" * 65)
print("Q2: POWER AT N=200 GIVEN PILOT (N=50): hied=54%, single=56%, debate=58%")
print("=" * 65)

pilot_accs = {"hied": 0.54, "single": 0.56, "debate": 0.58}
N_full = 200

print(f"\nAssumptions:")
print(f"  - Accuracies hold at N=200 (proportions are stable)")
print(f"  - Within-pair correlation rho = 0.5 (moderate, typical for LLM variants)")
print(f"  - Two-sided alpha = {ALPHA}")

pairs = [
    ("hied",   "single"),
    ("hied",   "debate"),
    ("single", "debate"),
]

print(f"\n{'Pair':>22} {'pA':>6} {'pB':>6} {'diff':>6} {'p_disc':>8} "
      f"{'n_disc':>8} {'power':>8} {'sig?':>6}")
print("-" * 78)

for (nameA, nameB) in pairs:
    pA_v = pilot_accs[nameA]
    pB_v = pilot_accs[nameB]
    pw, n_disc, b, c, p_disc_v, delta_v = mcnemar_power(N_full, pA_v, pB_v, alpha=ALPHA)
    sig = "YES" if pw >= 0.80 else ("MAYBE" if pw >= 0.50 else "LOW")
    print(f"{'(' + nameA + ' vs ' + nameB + ')':>22} {pA_v:>6.2f} {pB_v:>6.2f} "
          f"{pB_v - pA_v:>+6.2f} {p_disc_v:>8.4f} {n_disc:>8.1f} {pw:>8.4f} {sig:>6}")

# Sensitivity to rho
print(f"\n--- Sensitivity to within-pair correlation rho ---")
print(f"{'rho':>6} ", end="")
for (nameA, nameB) in pairs:
    print(f"{'(' + nameA[:3] + ' vs ' + nameB[:3] + ')':>16}", end="")
print()
print("-" * 6 + "-" * 16 * len(pairs))

for rho_val in [0.0, 0.2, 0.3, 0.5, 0.7, 0.9]:
    print(f"{rho_val:>6.1f} ", end="")
    for (nameA, nameB) in pairs:
        pA_v = pilot_accs[nameA]
        pB_v = pilot_accs[nameB]
        pw, _, _, _, _, _ = mcnemar_power(N_full, pA_v, pB_v, alpha=ALPHA, rho=rho_val)
        print(f"{pw:>16.4f}", end="")
    print()


# -----------------------------------------------------------------------
# Q3: Per-pair detailed analysis at N=200
# -----------------------------------------------------------------------
print("\n")
print("=" * 65)
print("Q3: PER-PAIR DETAILED ANALYSIS AT N=200")
print("=" * 65)

rho_default = 0.5

for (nameA, nameB) in pairs:
    pA_v = pilot_accs[nameA]
    pB_v = pilot_accs[nameB]
    pw, n_disc, b, c, p_disc_v, delta_v = mcnemar_power(
        N_full, pA_v, pB_v, alpha=ALPHA, rho=rho_default
    )
    p11, p10, p01, p00 = joint_table(pA_v, pB_v, rho=rho_default)

    print(f"\n  Pair: {nameA} (pA={pA_v:.2f}) vs {nameB} (pB={pB_v:.2f})")
    print(f"  {'─'*55}")
    print(f"  Joint probability table (rho={rho_default}):")
    print(f"    {'':12} {nameB}_correct  {nameB}_wrong")
    print(f"    {nameA}_correct   {p11:>9.4f}      {p10:>9.4f}  | {pA_v:.4f}")
    print(f"    {nameA}_wrong     {p01:>9.4f}      {p00:>9.4f}  | {1-pA_v:.4f}")
    print(f"    {'':12} {'─'*9}      {'─'*9}")
    print(f"    {'':12} {pB_v:>9.4f}      {1-pB_v:.4f}")
    print()
    print(f"  Expected counts at N={N_full}:")
    print(f"    Both correct  (b+b type 11): {p11 * N_full:>7.1f}")
    print(f"    {nameA} only correct   (b):  {b  * N_full:>7.1f}")
    print(f"    {nameB} only correct   (c):  {c  * N_full:>7.1f}")
    print(f"    Neither correct       (00): {p00 * N_full:>7.1f}")
    print()
    print(f"  Discordant pairs (b+c = p_disc): {n_disc:>7.1f}  (={p_disc_v*100:.1f}% of N)")
    print(f"  |b - c| = delta:                 {delta_v:>7.4f}")
    print(f"  Non-centrality (ncp):            {delta_v * math.sqrt(N_full) / math.sqrt(p_disc_v):>7.4f}")
    print(f"  Power at N={N_full}, alpha={ALPHA}:     {pw:>7.4f}  ({pw*100:.1f}%)")

    # N needed for 80% power
    def pw_fn(n):
        p, _, _, _, _, _ = mcnemar_power(int(n), pA_v, pB_v, alpha=ALPHA, rho=rho_default)
        return p

    try:
        n80 = brentq(lambda n: pw_fn(n) - 0.80, 10, 5000, xtol=1)
        n90 = brentq(lambda n: pw_fn(n) - 0.90, 10, 5000, xtol=1)
        print(f"  N needed for 80% power:          {n80:>7.0f}")
        print(f"  N needed for 90% power:          {n90:>7.0f}")
    except ValueError:
        print(f"  N needed for 80% power:          >5000 (effect too small)")


# -----------------------------------------------------------------------
# Summary table
# -----------------------------------------------------------------------
print("\n")
print("=" * 65)
print("SUMMARY TABLE: All pairs at N=200, rho=0.5")
print("=" * 65)
print(f"\n{'Pair':>22} {'diff':>6} {'n_disc':>8} {'power':>8} {'N_80%':>8} {'N_90%':>8}")
print("-" * 62)

for (nameA, nameB) in pairs:
    pA_v = pilot_accs[nameA]
    pB_v = pilot_accs[nameB]
    pw, n_disc, b, c, p_disc_v, delta_v = mcnemar_power(
        N_full, pA_v, pB_v, alpha=ALPHA, rho=rho_default
    )
    try:
        n80 = brentq(lambda n: mcnemar_power(int(n), pA_v, pB_v, alpha=ALPHA, rho=rho_default)[0] - 0.80,
                     10, 50000, xtol=1)
        n90 = brentq(lambda n: mcnemar_power(int(n), pA_v, pB_v, alpha=ALPHA, rho=rho_default)[0] - 0.90,
                     10, 50000, xtol=1)
    except ValueError:
        n80 = n90 = float('inf')
    print(f"{'(' + nameA + ' vs ' + nameB + ')':>22} {pB_v-pA_v:>+6.2f} {n_disc:>8.1f} "
          f"{pw:>8.4f} {n80:>8.0f} {n90:>8.0f}")

print("\n(rho = within-pair correlation between prompt variants)")
print("(n_disc = expected discordant pairs out of N=200)")
print()
