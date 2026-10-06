"""Soft: students sitting back-to-back exams on the same day."""
from __future__ import annotations

import numpy as np

from app.optimization.constraints._common import pair_weights
from app.optimization.context import OptimizationContext


def consecutive_conflicts(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    """Sum of C[i][j] over pairs in adjacent slots of the same day."""
    flags = ctx.pair_consecutive[slot[ctx.pair_i], slot[ctx.pair_j]]
    return int((pair_weights(ctx, ok) * flags).sum())
