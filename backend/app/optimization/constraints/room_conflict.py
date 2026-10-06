"""H3: at most one exam per room per slot."""
from __future__ import annotations

import numpy as np

from app.optimization.context import OptimizationContext


def room_collisions(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    """Colliding exam pairs: C(k, 2) for every (room, slot) holding k exams."""
    if ok is not None:
        slot, room = slot[ok], room[ok]
    counts = np.bincount(slot * ctx.n_rooms + room, minlength=ctx.n_slots * ctx.n_rooms)
    return int((counts * (counts - 1) // 2).sum())
