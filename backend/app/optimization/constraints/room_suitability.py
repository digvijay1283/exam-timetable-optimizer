"""H5: only available rooms; H6: room type must suit the exam type."""
from __future__ import annotations

import numpy as np

from app.optimization.constraints._common import masked_count
from app.optimization.context import OptimizationContext


def unavailable_rooms(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    return masked_count(~ctx.room_available[room], ok)


def room_type_mismatches(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    return masked_count(~ctx.room_type_ok[np.arange(ctx.n_exams), room], ok)
