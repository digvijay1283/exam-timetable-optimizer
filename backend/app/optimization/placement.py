"""Incremental slot/room placement shared by initialization, repair and the baselines.

`Occupancy` tracks, while exams are placed one at a time, how many students each unplaced exam
would clash with in every slot and which rooms are taken, so "which slots are feasible for this
exam" is a few vectorised operations.
"""
from __future__ import annotations

from typing import Literal

import numpy as np

from app.optimization.context import OptimizationContext

SlotMode = Literal["random", "best", "first"]
EXPLORE_SPAN = 3  # violations within which fallback slots are chosen at random when exploring


class Occupancy:
    def __init__(self, ctx: OptimizationContext):
        self.ctx = ctx
        n, s, r = ctx.n_exams, ctx.n_slots, ctx.n_rooms
        self.clash = np.zeros((n, s), dtype=np.int64)  # students exam i shares with exams placed in slot s
        self.day_clash = np.zeros((n, ctx.n_days), dtype=np.int64)  # ... with exams placed on day d
        self.room_count = np.zeros((s, r), dtype=np.int64)
        self.day_count = np.zeros(ctx.n_days, dtype=np.int64)
        self.slot_of = np.full(n, -1, dtype=np.int64)
        self.room_of = np.full(n, -1, dtype=np.int64)

    def place(self, i: int, s: int, r: int) -> None:
        self.slot_of[i], self.room_of[i] = s, r
        self.clash[:, s] += self.ctx.conflict[:, i]
        self.day_clash[:, self.ctx.slot_day_index[s]] += self.ctx.conflict[:, i]
        if r >= 0:
            self.room_count[s, r] += 1
        self.day_count[self.ctx.slot_day_index[s]] += 1

    def remove(self, i: int) -> None:
        s, r = int(self.slot_of[i]), int(self.room_of[i])
        if s < 0:
            return
        self.clash[:, s] -= self.ctx.conflict[:, i]
        self.day_clash[:, self.ctx.slot_day_index[s]] -= self.ctx.conflict[:, i]
        if r >= 0:
            self.room_count[s, r] -= 1
        self.day_count[self.ctx.slot_day_index[s]] -= 1
        self.slot_of[i], self.room_of[i] = -1, -1

    def student_clash(self, i: int) -> np.ndarray:
        """Hard student violations of putting exam i into each slot: shared students in that slot,
        plus (under H8) shared students elsewhere on the same day."""
        if not self.ctx.params.one_exam_per_day:
            return self.clash[i]
        return self.day_clash[i, self.ctx.slot_day_index]

    def feasible_slots(self, i: int) -> np.ndarray:
        """Slots where exam i fits in time, clashes with nobody and still has a free suitable room."""
        ctx = self.ctx
        free_room = (ctx.room_ok[i][None, :] & (self.room_count == 0)).any(axis=1)
        return ctx.slot_ok[i] & (self.student_clash(i) == 0) & free_room

    def best_fit_room(self, i: int, s: int) -> int:
        """Smallest sufficient free room for exam i in slot s, or -1."""
        ctx = self.ctx
        candidates = np.flatnonzero(ctx.room_ok[i] & (self.room_count[s] == 0))
        if len(candidates) == 0:
            return -1
        return int(candidates[np.argmin(ctx.room_capacity[candidates])])

    def soft_cost(self, i: int) -> np.ndarray:
        """Incremental weighted soft penalty of putting exam i into each slot, given placed exams."""
        ctx, w = self.ctx, self.ctx.weights
        neighbours = np.flatnonzero((ctx.conflict[i] > 0) & (self.slot_of >= 0))
        if len(neighbours):
            placed_slots = self.slot_of[neighbours]
            shared = ctx.conflict[i, neighbours]
            cost = (w.consecutive * ctx.pair_consecutive[:, placed_slots] + w.gap * ctx.pair_gap[:, placed_slots]) @ shared
        else:
            cost = np.zeros(ctx.n_slots)
        cost = cost + w.slot_pref * ctx.slot_pref * (1 + ctx.priority[i])
        over = self.day_count[ctx.slot_day_index] >= ctx.fair_exams_per_day
        return cost + w.distribution * over


def choose_placement(
    occ: Occupancy, i: int, rng: np.random.Generator, mode: SlotMode = "random", explore: bool = False
) -> tuple[int, int]:
    """Pick (slot, room) for exam i.

    mode: "random" a random feasible slot; "best" the feasible slot with least incremental soft
    penalty (random tie-break); "first" the earliest feasible slot. If no slot is fully feasible
    the least-violating slot is used and the leftover violation is left to the penalty. With
    `explore` (used by repair), slots within a few violations of the least-violating one compete at
    random, so repair can push a clashing neighbour out instead of cycling in a local minimum.
    """
    ctx = occ.ctx
    feasible = np.flatnonzero(occ.feasible_slots(i))
    if len(feasible):
        if mode == "random":
            s = int(rng.choice(feasible))
        elif mode == "first":
            s = int(feasible[0])
        else:
            cost = occ.soft_cost(i)[feasible] + rng.random(len(feasible)) * 1e-6
            s = int(feasible[np.argmin(cost)])
        return s, occ.best_fit_room(i, s)

    # No fully feasible slot: minimise (hard violations, soft cost) among the slots that fit in time.
    fits = ctx.slot_ok[i] if ctx.slot_ok[i].any() else np.ones(ctx.n_slots, dtype=bool)
    has_room = (ctx.room_ok[i][None, :] & (occ.room_count == 0)).any(axis=1)
    cost = ctx.weights.hard * (occ.student_clash(i) + (~has_room)) + occ.soft_cost(i)
    noise = ctx.weights.hard * EXPLORE_SPAN if explore else 1e-6
    cost = np.where(fits, cost, np.inf) + rng.random(ctx.n_slots) * noise
    s = int(np.argmin(cost))
    r = occ.best_fit_room(i, s)
    if r < 0:  # every suitable room is taken in this slot: share the smallest suitable one
        suitable = np.flatnonzero(ctx.room_ok[i])
        if len(suitable):
            r = int(suitable[np.argmin(ctx.room_capacity[suitable])])
        else:  # no suitable room at all (ruled out by the feasibility check); use the largest available
            available = np.flatnonzero(ctx.room_available)
            pool = available if len(available) else np.arange(ctx.n_rooms)
            r = int(pool[np.argmax(ctx.room_capacity[pool])])
    return s, r
