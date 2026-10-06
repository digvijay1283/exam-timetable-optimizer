"""Soft: students with exams too close together (same day non-adjacent, or on adjacent days)."""
from __future__ import annotations

import numpy as np

from app.optimization.constraints._common import pair_weights
from app.optimization.context import OptimizationContext


def short_gaps(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    flags = ctx.pair_gap[slot[ctx.pair_i], slot[ctx.pair_j]]
    return int((pair_weights(ctx, ok) * flags).sum())
