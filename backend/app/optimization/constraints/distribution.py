"""Soft: spread exams evenly over the exam days."""
from __future__ import annotations

import numpy as np

from app.optimization.context import OptimizationContext


def distribution_penalty(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    """Exams scheduled on a day beyond the fair share ceil(E / D), summed over days."""
    days = ctx.slot_day_index[slot if ok is None else slot[ok]]
    per_day = np.bincount(days, minlength=ctx.n_days)
    return int(np.maximum(0, per_day - ctx.fair_exams_per_day).sum())
