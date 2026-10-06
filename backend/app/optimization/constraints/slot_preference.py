"""Soft: avoid undesirable slots; priority exams care more."""
from __future__ import annotations

import numpy as np

from app.optimization.context import OptimizationContext


def slot_preference_penalty(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    cost = ctx.slot_pref[slot] * (1 + ctx.priority)
    return int(cost.sum() if ok is None else cost[ok].sum())
