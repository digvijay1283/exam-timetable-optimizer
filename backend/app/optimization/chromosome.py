"""Chromosome: one complete timetable as two index arrays (docs/SPEC_DECISIONS.md section 6)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.core.domain import Assignment
from app.optimization.context import OptimizationContext
from app.optimization.fitness import Evaluation, evaluate


@dataclass
class Chromosome:
    """slot[i] / room[i] are the slot and room indices assigned to exam i."""

    slot: np.ndarray
    room: np.ndarray
    penalty: float = math.inf
    hard_violations: int = -1
    fitness: float = 0.0

    def copy(self) -> "Chromosome":
        return Chromosome(self.slot.copy(), self.room.copy(), self.penalty, self.hard_violations, self.fitness)

    def evaluate(self, ctx: OptimizationContext) -> Evaluation:
        ev = evaluate(ctx, self.slot, self.room)
        self.penalty, self.hard_violations, self.fitness = ev.penalty, ev.hard_violations, ev.fitness
        return ev

    def assignments(self, ctx: OptimizationContext) -> list[Assignment]:
        return [
            Assignment(ctx.exam_ids[i], ctx.slot_ids[int(self.slot[i])], ctx.room_ids[int(self.room[i])])
            for i in range(ctx.n_exams)
        ]

    @classmethod
    def from_assignments(cls, ctx: OptimizationContext, assignments: list[Assignment]) -> "Chromosome":
        exam_idx, slot_idx, room_idx = ctx.exam_index(), ctx.slot_index(), ctx.room_index()
        slot = np.full(ctx.n_exams, -1, dtype=np.int64)
        room = np.full(ctx.n_exams, -1, dtype=np.int64)
        for exam_id, slot_id, room_id in assignments:
            i = exam_idx[exam_id]
            slot[i], room[i] = slot_idx[slot_id], room_idx[room_id]
        return cls(slot, room)
