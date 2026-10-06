"""H4: every exam has a valid slot and room; H7: the exam must fit inside its slot."""
from __future__ import annotations

import numpy as np

from app.optimization.constraints._common import masked_count
from app.optimization.context import OptimizationContext


def assigned_mask(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray) -> np.ndarray:
    """True for exams whose slot and room indices both exist."""
    return (slot >= 0) & (slot < ctx.n_slots) & (room >= 0) & (room < ctx.n_rooms)


def unassigned(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    return 0 if ok is None else int((~ok).sum())


def duration_violations(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray, ok: np.ndarray | None) -> int:
    return masked_count(~ctx.slot_ok[np.arange(ctx.n_exams), slot], ok)
