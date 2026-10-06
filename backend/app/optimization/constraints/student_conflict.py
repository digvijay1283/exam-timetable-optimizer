"""H1: exams sharing students must not be in the same slot."""
from __future__ import annotations

import numpy as np

from app.optimization.constraints._common import pair_weights
from app.optimization.context import OptimizationContext


def student_clashes(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    """Number of student clash incidents: sum of C[i][j] over same-slot pairs."""
    same = slot[ctx.pair_i] == slot[ctx.pair_j]
    return int((pair_weights(ctx, ok) * same).sum())
