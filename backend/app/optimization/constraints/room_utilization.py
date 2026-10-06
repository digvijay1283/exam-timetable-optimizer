"""Soft: avoid wasting seats (assign the smallest sufficient room)."""
from __future__ import annotations

import numpy as np

from app.optimization.context import OptimizationContext


def room_utilization_penalty(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> float:
    """Sum over exams of the wasted seat fraction (capacity - students) / capacity, floored at 0."""
    capacity = ctx.room_capacity[room]
    waste = np.maximum(0, capacity - ctx.student_count) / capacity
    return float(waste.sum() if ok is None else waste[ok].sum())
