"""Weighted penalty and fitness (PRD section 7, docs/SPEC_DECISIONS.md sections 2, 4, 5)."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from app.optimization.constraints import (
    assigned_mask,
    capacity_violations,
    consecutive_conflicts,
    distribution_penalty,
    duration_violations,
    room_collisions,
    room_type_mismatches,
    room_utilization_penalty,
    short_gaps,
    slot_preference_penalty,
    student_clashes,
    unassigned,
    unavailable_rooms,
)
from app.optimization.context import OptimizationContext


@dataclass(frozen=True)
class Evaluation:
    # hard-constraint breakdown
    student_clashes: int
    room_collisions: int
    capacity_violations: int
    unassigned: int
    unavailable_rooms: int
    room_type_mismatches: int
    duration_violations: int
    # soft components (unweighted)
    consecutive: int
    short_gaps: int
    distribution: int
    slot_preference: int
    room_utilization: float
    # totals
    hard_violations: int
    penalty: float
    fitness: float

    @property
    def valid(self) -> bool:
        return self.hard_violations == 0

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate(ctx: OptimizationContext, slot: np.ndarray, room: np.ndarray) -> Evaluation:
    """Score a timetable given as slot/room index arrays (one entry per exam).

    An index outside range (e.g. -1) marks the exam unassigned: it counts once under H4 and is
    skipped by every other check.
    """
    mask = assigned_mask(ctx, slot, room)
    if mask.all():
        ok = None
    else:
        ok = mask
        slot, room = np.where(mask, slot, 0), np.where(mask, room, 0)

    clashes = student_clashes(ctx, slot, room, ok)
    collisions = room_collisions(ctx, slot, room, ok)
    capacity = capacity_violations(ctx, slot, room, ok)
    missing = unassigned(ctx, slot, room, ok)
    unavailable = unavailable_rooms(ctx, slot, room, ok)
    mismatches = room_type_mismatches(ctx, slot, room, ok)
    too_long = duration_violations(ctx, slot, room, ok)
    hard = clashes + collisions + capacity + missing + unavailable + mismatches + too_long

    consecutive = consecutive_conflicts(ctx, slot, room, ok)
    gaps = short_gaps(ctx, slot, room, ok)
    spread = distribution_penalty(ctx, slot, room, ok)
    preference = slot_preference_penalty(ctx, slot, room, ok)
    utilization = room_utilization_penalty(ctx, slot, room, ok)

    w = ctx.weights
    penalty = (
        w.hard * hard
        + w.consecutive * consecutive
        + w.gap * gaps
        + w.distribution * spread
        + w.slot_pref * preference
        + w.room_util * utilization
    )
    return Evaluation(
        student_clashes=clashes,
        room_collisions=collisions,
        capacity_violations=capacity,
        unassigned=missing,
        unavailable_rooms=unavailable,
        room_type_mismatches=mismatches,
        duration_violations=too_long,
        consecutive=consecutive,
        short_gaps=gaps,
        distribution=spread,
        slot_preference=preference,
        room_utilization=utilization,
        hard_violations=hard,
        penalty=float(penalty),
        fitness=1.0 / (1.0 + float(penalty)),
    )
