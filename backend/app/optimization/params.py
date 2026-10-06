"""Genetic algorithm parameters (PRD section 8; docs/SPEC_DECISIONS.md section 7)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class GAParams:
    population_size: int = 100
    generations: int = 300
    crossover_rate: float = 0.80
    mutation_rate: float = 0.10  # probability that a child is mutated
    elite_count: int = 5
    tournament_size: int = 3
    seed: int = 42

    mutation_ops: int | None = None  # operations per mutated child; None = max(1, ceil(5% of exams))
    crossover_type: Literal["uniform", "two_point"] = "uniform"
    repair: bool = True
    repair_attempts: int = 100
    repair_mode: Literal["best", "random"] = "best"

    # Stopping. Comparative experiments set early_stopping=False so every run has equal length.
    early_stopping: bool = True
    patience: int = 50
    target_penalty: float | None = None

    def validate(self) -> None:
        if self.population_size < 2:
            raise ValueError("population_size must be >= 2")
        if self.generations < 0:
            raise ValueError("generations must be >= 0")
        if not 0 <= self.crossover_rate <= 1 or not 0 <= self.mutation_rate <= 1:
            raise ValueError("crossover_rate and mutation_rate must be within [0, 1]")
        if not 0 <= self.elite_count < self.population_size:
            raise ValueError("elite_count must be in [0, population_size)")
        if self.tournament_size < 1:
            raise ValueError("tournament_size must be >= 1")
        if self.repair_attempts < 0:
            raise ValueError("repair_attempts must be >= 0")

    def as_dict(self) -> dict:
        return asdict(self)
