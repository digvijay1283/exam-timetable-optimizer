"""H2: the room must be large enough for the exam."""
from __future__ import annotations

import numpy as np

from app.optimization.constraints._common import masked_count
from app.optimization.context import OptimizationContext


def capacity_violations(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    return masked_count(ctx.room_capacity[room] < ctx.student_count, ok)
