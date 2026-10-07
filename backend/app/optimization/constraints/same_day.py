"""H8: a student sits at most one exam per day."""
from __future__ import annotations

import numpy as np

from app.optimization.constraints._common import pair_weights
from app.optimization.context import OptimizationContext


def same_day_conflicts(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    """Sum of C[i][j] over pairs in different slots of the same day (same-slot pairs are H1)."""
    if not ctx.params.one_exam_per_day:
        return 0
    flags = ctx.pair_same_day[slot[ctx.pair_i], slot[ctx.pair_j]]
    return int((pair_weights(ctx, ok) * flags).sum())
