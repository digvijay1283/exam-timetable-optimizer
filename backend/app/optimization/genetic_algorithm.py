"""The genetic algorithm loop (Architecture section 8).

Generate population -> evaluate -> keep elites -> tournament selection -> crossover -> mutation
-> repair -> evaluate -> new population -> record metrics -> stop?
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Callable

import numpy as np

from app.optimization.chromosome import Chromosome
from app.optimization.context import OptimizationContext
from app.optimization.crossover import CROSSOVERS
from app.optimization.fitness import Evaluation
from app.optimization.mutation import default_mutation_ops, mutate
from app.optimization.params import GAParams
from app.optimization.population import initial_population
from app.optimization.repair import repair
from app.optimization.selection import tournament_select

IMPROVEMENT_EPS = 1e-9


@dataclass(frozen=True)
class GenerationStats:
    generation: int
    best_penalty: float
    mean_penalty: float
    worst_penalty: float
    best_hard: int
    feasible_fraction: float  # share of the population with zero hard violations

    @property
    def best_fitness(self) -> float:
        return 1.0 / (1.0 + self.best_penalty)


@dataclass
class GAResult:
    best: Chromosome
    evaluation: Evaluation
    initial_penalty: float  # best penalty in the initial population
    history: list[GenerationStats]
    generations_run: int
    runtime_seconds: float
    stopped_by: str  # "max_generations" | "target_reached" | "no_improvement"
    params: GAParams

    @property
    def valid(self) -> bool:
        return self.evaluation.hard_violations == 0

    def history_dicts(self) -> list[dict]:
        return [asdict(h) | {"best_fitness": h.best_fitness} for h in self.history]


ProgressCallback = Callable[[GenerationStats], None]


def _stats(generation: int, pop: list[Chromosome]) -> GenerationStats:
    penalties = np.array([c.penalty for c in pop])
    hard = np.array([c.hard_violations for c in pop])
    best = int(np.argmin(penalties))
    return GenerationStats(
        generation=generation,
        best_penalty=float(penalties[best]),
        mean_penalty=float(penalties.mean()),
        worst_penalty=float(penalties.max()),
        best_hard=int(hard[best]),
        feasible_fraction=float((hard == 0).mean()),
    )


def run_ga(
    ctx: OptimizationContext,
    params: GAParams | None = None,
    progress: ProgressCallback | None = None,
) -> GAResult:
    params = params or GAParams()
    params.validate()
    started = time.perf_counter()
    rng = np.random.default_rng(params.seed)
    crossover = CROSSOVERS[params.crossover_type]
    ops = params.mutation_ops if params.mutation_ops is not None else default_mutation_ops(ctx)
    size, n_elite = params.population_size, params.elite_count

    pop = initial_population(ctx, size, rng)
    for c in pop:
        c.evaluate(ctx)
    stats = _stats(0, pop)
    history = [stats]
    initial_penalty = stats.best_penalty
    if progress:
        progress(stats)

    best_penalty = stats.best_penalty
    stale = 0
    stopped_by = "max_generations"
    generation = 0
    for generation in range(1, params.generations + 1):
        penalties = np.array([c.penalty for c in pop])
        order = np.argsort(penalties, kind="stable")
        next_pop = [pop[int(i)] for i in order[:n_elite]]

        n_children = size - n_elite
        n_pairs = (n_children + 1) // 2
        winners = tournament_select(penalties, params.tournament_size, 2 * n_pairs, rng)
        children: list[Chromosome] = []
        for p in range(n_pairs):
            a, b = pop[int(winners[2 * p])], pop[int(winners[2 * p + 1])]
            if rng.random() < params.crossover_rate:
                pair = crossover(a, b, rng)
                dirty = True
            else:
                pair = (a.copy(), b.copy())
                dirty = False
            for child in pair:
                changed = dirty
                if rng.random() < params.mutation_rate:
                    mutate(ctx, child, rng, ops)
                    changed = True
                if changed:
                    if params.repair:
                        repair(ctx, child, rng, params.repair_attempts, params.repair_mode)
                    child.evaluate(ctx)
                children.append(child)
        next_pop.extend(children[:n_children])
        pop = next_pop

        stats = _stats(generation, pop)
        history.append(stats)
        if progress:
            progress(stats)

        if stats.best_penalty < best_penalty - IMPROVEMENT_EPS:
            best_penalty, stale = stats.best_penalty, 0
        else:
            stale += 1
        if params.early_stopping:
            if (
                params.target_penalty is not None
                and stats.best_hard == 0
                and stats.best_penalty <= params.target_penalty
            ):
                stopped_by = "target_reached"
                break
            if stale >= params.patience:
                stopped_by = "no_improvement"
                break

    best = min(pop, key=lambda c: c.penalty).copy()
    evaluation = best.evaluate(ctx)
    return GAResult(
        best=best,
        evaluation=evaluation,
        initial_penalty=initial_penalty,
        history=history,
        generations_run=generation,
        runtime_seconds=time.perf_counter() - started,
        stopped_by=stopped_by,
        params=params,
    )
