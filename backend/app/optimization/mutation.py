"""Slot, room and swap mutation (Architecture section 12). All operate in place on a chromosome."""
from __future__ import annotations

import math

import numpy as np

from app.optimization.chromosome import Chromosome
from app.optimization.context import OptimizationContext


def _other(candidates: np.ndarray, current: int, rng: np.random.Generator) -> int | None:
    options = candidates[candidates != current]
    return int(rng.choice(options)) if len(options) else None


def slot_mutation(ctx: OptimizationContext, chrom: Chromosome, rng: np.random.Generator) -> None:
    i = int(rng.integers(ctx.n_exams))
    new = _other(np.flatnonzero(ctx.slot_ok[i]), int(chrom.slot[i]), rng)
    if new is not None:
        chrom.slot[i] = new


def room_mutation(ctx: OptimizationContext, chrom: Chromosome, rng: np.random.Generator) -> None:
    i = int(rng.integers(ctx.n_exams))
    new = _other(np.flatnonzero(ctx.room_ok[i]), int(chrom.room[i]), rng)
    if new is not None:
        chrom.room[i] = new


def swap_mutation(ctx: OptimizationContext, chrom: Chromosome, rng: np.random.Generator) -> None:
    if ctx.n_exams < 2:
        return
    i, j = rng.choice(ctx.n_exams, size=2, replace=False)
    chrom.slot[i], chrom.slot[j] = chrom.slot[j], chrom.slot[i]


OPERATORS = (slot_mutation, room_mutation, swap_mutation)


def default_mutation_ops(ctx: OptimizationContext) -> int:
    return max(1, math.ceil(0.05 * ctx.n_exams))


def mutate(ctx: OptimizationContext, chrom: Chromosome, rng: np.random.Generator, ops: int) -> None:
    """Apply `ops` mutation operations, each chosen uniformly from the three operators."""
    for _ in range(ops):
        OPERATORS[int(rng.integers(len(OPERATORS)))](ctx, chrom, rng)
