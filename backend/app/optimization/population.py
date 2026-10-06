"""Conflict-aware population initialization (PRD section 8, Architecture section 9)."""
from __future__ import annotations

import numpy as np

from app.optimization.chromosome import Chromosome
from app.optimization.context import OptimizationContext
from app.optimization.placement import Occupancy, SlotMode, choose_placement


def exam_order(ctx: OptimizationContext, rng: np.random.Generator) -> np.ndarray:
    """Exams by descending conflict degree (then shared students), ties broken randomly."""
    return np.lexsort((rng.random(ctx.n_exams), -ctx.weighted_degree, -ctx.degree))


def constructive_individual(
    ctx: OptimizationContext, rng: np.random.Generator, mode: SlotMode = "random"
) -> Chromosome:
    """Place exams hardest-first into a feasible slot and the smallest sufficient room."""
    occ = Occupancy(ctx)
    for i in exam_order(ctx, rng):
        slot, room = choose_placement(occ, int(i), rng, mode)
        occ.place(int(i), slot, room)
    return Chromosome(occ.slot_of.copy(), occ.room_of.copy())


def initial_population(ctx: OptimizationContext, size: int, rng: np.random.Generator) -> list[Chromosome]:
    return [constructive_individual(ctx, rng, "random") for _ in range(size)]
