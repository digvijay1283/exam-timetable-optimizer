"""Crossover. A gene is an exam's (slot, room) pair and is inherited as a unit."""
from __future__ import annotations

import numpy as np

from app.optimization.chromosome import Chromosome


def uniform_crossover(a: Chromosome, b: Chromosome, rng: np.random.Generator) -> tuple[Chromosome, Chromosome]:
    take_a = rng.random(len(a.slot)) < 0.5
    return (
        Chromosome(np.where(take_a, a.slot, b.slot), np.where(take_a, a.room, b.room)),
        Chromosome(np.where(take_a, b.slot, a.slot), np.where(take_a, b.room, a.room)),
    )


def two_point_crossover(a: Chromosome, b: Chromosome, rng: np.random.Generator) -> tuple[Chromosome, Chromosome]:
    n = len(a.slot)
    if n < 2:
        return a.copy(), b.copy()
    p, q = sorted(rng.choice(n + 1, size=2, replace=False))
    swap = np.zeros(n, dtype=bool)
    swap[p:q] = True
    return (
        Chromosome(np.where(swap, b.slot, a.slot), np.where(swap, b.room, a.room)),
        Chromosome(np.where(swap, a.slot, b.slot), np.where(swap, a.room, b.room)),
    )


CROSSOVERS = {"uniform": uniform_crossover, "two_point": two_point_crossover}
