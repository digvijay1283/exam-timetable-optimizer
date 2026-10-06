"""Aggregate per-seed convergence histories (best penalty per generation)."""
from __future__ import annotations

import numpy as np


def stack_histories(per_seed: dict[str, dict], key: str = "best") -> np.ndarray:
    """(n_seeds, n_generations + 1) array from {seed: {"best": [...], ...}}, seeds in numeric order."""
    rows = [np.asarray(per_seed[s][key], dtype=float) for s in sorted(per_seed, key=int)]
    length = min(len(r) for r in rows)
    return np.vstack([r[:length] for r in rows])


def mean_std_band(curves: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    std = curves.std(axis=0, ddof=1) if curves.shape[0] > 1 else np.zeros(curves.shape[1])
    return curves.mean(axis=0), std


def fitness_from_penalty(penalty: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + penalty)


def generations_to_reach(curve: np.ndarray, fraction: float = 0.95) -> int:
    """First generation where the curve has closed `fraction` of the gap between start and end."""
    start, end = float(curve[0]), float(curve[-1])
    if start <= end:
        return 0
    target = start - fraction * (start - end)
    return int(np.argmax(curve <= target))
