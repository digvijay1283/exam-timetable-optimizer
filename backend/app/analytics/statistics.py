"""Descriptive statistics and significance tests for the experiment tables (PRD section 11)."""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from scipy import stats as scipy_stats


def summarize(values: Sequence[float]) -> dict[str, float]:
    """Mean, median, sample standard deviation, min, max (n-1 denominator; 0 for a single value)."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {"n": 0, "mean": math.nan, "median": math.nan, "std": math.nan, "min": math.nan, "max": math.nan}
    return {
        "n": int(arr.size),
        "mean": float(arr.mean()),
        "median": float(np.median(arr)),
        "std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def improvement_percent(baseline: float, ga: float) -> float | None:
    """((Baseline - GA) / Baseline) x 100; None when the baseline penalty is not positive."""
    if baseline is None or not baseline > 0:
        return None
    return (baseline - ga) / baseline * 100.0


def mann_whitney_less(ga: Sequence[float], other: Sequence[float]) -> dict[str, float] | None:
    """One-sided Mann-Whitney U test: are GA penalties stochastically smaller than `other`?

    Returns {"u": ..., "p": ...}, or None when either sample has fewer than 2 observations.
    """
    if len(ga) < 2 or len(other) < 2:
        return None
    res = scipy_stats.mannwhitneyu(ga, other, alternative="less")
    return {"u": float(res.statistic), "p": float(res.pvalue)}


def cliffs_delta(ga: Sequence[float], other: Sequence[float]) -> float:
    """Effect size in [-1, 1]; negative means GA values tend to be smaller (better)."""
    a, b = np.asarray(ga, dtype=float), np.asarray(other, dtype=float)
    if a.size == 0 or b.size == 0:
        return math.nan
    greater = (a[:, None] > b[None, :]).sum()
    less = (a[:, None] < b[None, :]).sum()
    return float((greater - less) / (a.size * b.size))
