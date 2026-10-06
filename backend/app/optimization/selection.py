"""Tournament selection."""
from __future__ import annotations

import numpy as np


def tournament_select(penalties: np.ndarray, k: int, n: int, rng: np.random.Generator) -> np.ndarray:
    """Indices of `n` winners; each wins a tournament among `k` random entrants (lowest penalty)."""
    entrants = rng.integers(0, len(penalties), size=(n, k))
    best = np.argmin(penalties[entrants], axis=1)
    return entrants[np.arange(n), best]
