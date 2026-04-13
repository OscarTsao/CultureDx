"""Helpers for reproducible CultureDx runs."""
from __future__ import annotations

import random


def apply_global_seed(seed: int) -> None:
    """Apply the configured seed to local pseudo-random generators."""
    random.seed(seed)
    try:
        import numpy as np
    except ModuleNotFoundError:
        return
    np.random.seed(seed)
