"""Constraint-based repair (PRD section 8, Architecture section 13).

Detects exams involved in a violation (student clash, room collision, unsuitable room or slot),
removes one, and re-places it in a feasible slot with the smallest sufficient room, until none
remain or the attempt budget is spent. Violations that cannot be repaired stay in the penalty so
the GA can still rank the chromosome.
"""
from __future__ import annotations

import numpy as np

from app.optimization.chromosome import Chromosome
from app.optimization.context import OptimizationContext
from app.optimization.placement import Occupancy, choose_placement


def _violators(ctx: OptimizationContext, occ: Occupancy) -> np.ndarray:
    ar = np.arange(ctx.n_exams)
    slot, room = occ.slot_of, occ.room_of
    bad = ~ctx.room_ok[ar, room]  # capacity, availability or room type
    bad |= ~ctx.slot_ok[ar, slot]  # exam longer than its slot
    bad |= occ.clash[ar, slot] > 0  # shares students with another exam in the same slot
    _, first = np.unique(slot * ctx.n_rooms + room, return_index=True)
    sharing = np.ones(ctx.n_exams, dtype=bool)
    sharing[first] = False  # every occupant of a room/slot cell except the first
    return bad | sharing


def repair(
    ctx: OptimizationContext,
    chrom: Chromosome,
    rng: np.random.Generator,
    max_attempts: int = 100,
    mode: str = "best",
) -> int:
    """Repair `chrom` in place; returns the number of exams moved."""
    occ = Occupancy(ctx)
    for i in range(ctx.n_exams):
        occ.place(i, int(chrom.slot[i]), int(chrom.room[i]))
    moves = 0
    while moves < max_attempts:
        bad = np.flatnonzero(_violators(ctx, occ))
        if len(bad) == 0:
            break
        i = int(rng.choice(bad))
        occ.remove(i)
        slot, room = choose_placement(occ, i, rng, mode)  # type: ignore[arg-type]
        occ.place(i, slot, room)
        moves += 1
    chrom.slot[:] = occ.slot_of
    chrom.room[:] = occ.room_of
    return moves
