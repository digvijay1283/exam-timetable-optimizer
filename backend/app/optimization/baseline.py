"""Reference schedulers the GA is compared against (PRD section 12, docs/SPEC_DECISIONS.md section 8).

greedy              deterministic, conflict-aware: hardest exam first, earliest feasible slot, smallest
                    sufficient room. This is the baseline described in the PRD.
greedy_cost_aware   same order, but each exam takes the feasible slot with the least incremental soft
                    penalty. A much stronger baseline, included so the GA is not compared to a strawman.
randomized_greedy   hardest-first with a random feasible slot and random tie-breaks (a seeded
                    distribution; this is also the GA's initial-population generator).
random_feasible     every exam gets a random time-fitting slot and a random suitable room, ignoring
                    clashes. Shows how much the structure of the problem matters.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

from app.optimization.chromosome import Chromosome
from app.optimization.context import OptimizationContext
from app.optimization.fitness import Evaluation
from app.optimization.placement import Occupancy, SlotMode, choose_placement
from app.optimization.population import constructive_individual


@dataclass
class BaselineResult:
    name: str
    chromosome: Chromosome
    evaluation: Evaluation
    runtime_seconds: float
    seed: int | None

    @property
    def valid(self) -> bool:
        return self.evaluation.hard_violations == 0


def _deterministic_order(ctx: OptimizationContext) -> np.ndarray:
    # lexsort: last key is primary. Primary: conflict degree desc; then shared students desc; then index.
    return np.lexsort((np.arange(ctx.n_exams), -ctx.weighted_degree, -ctx.degree))


def _sequential(ctx: OptimizationContext, mode: SlotMode) -> Chromosome:
    occ = Occupancy(ctx)
    rng = np.random.default_rng(0)  # only used to break exact cost ties; no effect in "first" mode
    for i in _deterministic_order(ctx):
        slot, room = choose_placement(occ, int(i), rng, mode)
        occ.place(int(i), slot, room)
    return Chromosome(occ.slot_of.copy(), occ.room_of.copy())


def greedy(ctx: OptimizationContext, seed: int | None = None) -> Chromosome:
    return _sequential(ctx, "first")


def greedy_cost_aware(ctx: OptimizationContext, seed: int | None = None) -> Chromosome:
    return _sequential(ctx, "best")


def randomized_greedy(ctx: OptimizationContext, seed: int | None = 0) -> Chromosome:
    return constructive_individual(ctx, np.random.default_rng(seed), "random")


def random_feasible(ctx: OptimizationContext, seed: int | None = 0) -> Chromosome:
    rng = np.random.default_rng(seed)
    slot = np.empty(ctx.n_exams, dtype=np.int64)
    room = np.empty(ctx.n_exams, dtype=np.int64)
    for i in range(ctx.n_exams):
        slot[i] = rng.choice(np.flatnonzero(ctx.slot_ok[i]))
        room[i] = rng.choice(np.flatnonzero(ctx.room_ok[i]))
    return Chromosome(slot, room)


BASELINES: dict[str, Callable[[OptimizationContext, int | None], Chromosome]] = {
    "greedy": greedy,
    "greedy_cost_aware": greedy_cost_aware,
    "randomized_greedy": randomized_greedy,
    "random_feasible": random_feasible,
}
DETERMINISTIC = {"greedy", "greedy_cost_aware"}


def run_baseline(ctx: OptimizationContext, name: str, seed: int | None = 0) -> BaselineResult:
    if name not in BASELINES:
        raise ValueError(f"unknown baseline '{name}'; choose from {sorted(BASELINES)}")
    started = time.perf_counter()
    chrom = BASELINES[name](ctx, seed)
    evaluation = chrom.evaluate(ctx)
    return BaselineResult(
        name=name,
        chromosome=chrom,
        evaluation=evaluation,
        runtime_seconds=time.perf_counter() - started,
        seed=None if name in DETERMINISTIC else seed,
    )
