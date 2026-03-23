"""Demographic base rate priors for ICD-10 disorders.

Population-level priors based on epidemiological literature. These adjust
confidence as a soft signal — they never override criterion-based evidence.

Sources:
    - WHO ICD-10 Clinical Descriptions and Diagnostic Guidelines
    - Chinese National Mental Health Survey (Huang et al., 2019, Lancet Psychiatry)
    - GBD 2019 Mental Disorders Collaborators, Lancet Psychiatry 2022
"""
from __future__ import annotations

# Gender ratios: female_rate / male_rate (>1.0 = more common in females)
GENDER_RATIOS: dict[str, float] = {
    "F32": 1.7,    # Depression: ~1.7x more common in females
    "F33": 1.7,    # Recurrent depression: same ratio
    "F31": 1.2,    # Bipolar: roughly equal, slight female excess
    "F41.1": 1.8,  # GAD: ~1.8x more common in females
    "F41.0": 2.0,  # Panic: ~2x more common in females
    "F40": 1.5,    # Phobic anxiety: more common in females
    "F42": 1.0,    # OCD: roughly equal
    "F43.1": 2.0,  # PTSD: ~2x more common in females
    "F43.2": 1.0,  # Adjustment: roughly equal
    "F45": 1.5,    # Somatoform: more common in females
    "F20": 0.8,    # Schizophrenia: slightly more common in males
    "F22": 1.0,    # Persistent delusional: roughly equal
    "F51": 1.3,    # Sleep disorders: slightly more in females
}

# Typical age-of-onset ranges: (peak_start, peak_end)
AGE_ONSET_RANGES: dict[str, tuple[int, int]] = {
    "F32": (20, 50),
    "F33": (25, 55),
    "F31": (18, 35),
    "F41.1": (25, 55),
    "F41.0": (20, 40),
    "F40": (15, 35),
    "F42": (15, 30),
    "F43.1": (18, 65),
    "F43.2": (18, 65),
    "F45": (20, 50),
    "F20": (18, 30),
    "F22": (35, 55),
    "F51": (30, 60),
}


def compute_demographic_prior(
    disorder_code: str,
    age: int | None = None,
    gender: str | None = None,
) -> float:
    """Compute a demographic prior score for a disorder.

    Returns a value in [0.0, 1.0] where:
        0.5 = neutral (no demographic info or uninformative)
        > 0.5 = demographics support this disorder
        < 0.5 = demographics argue against this disorder

    The max effect is deliberately small (gender: +/-0.1, age: +/-0.2)
    so that demographics nudge but never override criterion evidence.
    """
    factors = []

    # Gender factor
    if gender is not None:
        ratio = GENDER_RATIOS.get(disorder_code, 1.0)
        is_female = gender in ("女", "female", "Female", "F", "f")
        is_male = gender in ("男", "male", "Male", "M", "m")

        if is_female:
            gender_score = 0.5 + 0.1 * (ratio - 1.0)
        elif is_male:
            gender_score = 0.5 - 0.1 * (ratio - 1.0)
        else:
            gender_score = 0.5
        factors.append(max(0.0, min(1.0, gender_score)))

    # Age factor
    if age is not None and isinstance(age, (int, float)):
        age = int(age)
        onset_range = AGE_ONSET_RANGES.get(disorder_code)
        if onset_range is not None:
            peak_start, peak_end = onset_range
            if peak_start <= age <= peak_end:
                age_score = 0.6
            else:
                distance = min(abs(age - peak_start), abs(age - peak_end))
                age_score = max(0.3, 0.6 - 0.01 * distance)
            factors.append(age_score)

    if not factors:
        return 0.5

    return sum(factors) / len(factors)
