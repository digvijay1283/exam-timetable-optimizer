"""Shared helpers for constraint functions.

Every constraint takes `(ctx, slot, room, ok)` where `slot` and `room` are int arrays indexed by
exam and `ok` is None (every exam has a valid slot and room) or a boolean mask of the exams that
do. Exams outside the mask are counted only by the "unassigned" hard constraint and are skipped
by every other check (docs/SPEC_DECISIONS.md section 2).
"""
from __future__ import annotations

import numpy as np

from app.optimization.context import OptimizationContext


def pair_weights(ctx: OptimizationContext, ok: np.ndarray | None) -> np.ndarray:
    """Shared-student counts of conflicting pairs, zeroed where either exam is unassigned."""
    if ok is None:
        return ctx.pair_c
    return ctx.pair_c * (ok[ctx.pair_i] & ok[ctx.pair_j])


def masked_count(flags: np.ndarray, ok: np.ndarray | None) -> int:
    return int(flags.sum() if ok is None else (flags & ok).sum())
