"""Per-run experiment records (PRD section 11) and dataset fingerprinting."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from app.optimization.baseline import BaselineResult
from app.optimization.genetic_algorithm import GAResult

DATASET_FILES = ("exams.csv", "students.csv", "enrollments.csv", "rooms.csv", "slots.csv")


def dataset_fingerprint(data_dir: str | Path) -> str:
    """Short SHA-256 over the dataset's CSV files, stored with every run for reproducibility."""
    digest = hashlib.sha256()
    for name in DATASET_FILES:
        digest.update((Path(data_dir) / name).read_bytes())
    return digest.hexdigest()[:16]


@dataclass
class RunRecord:
    run_id: str
    experiment: str
    config: str
    method: str  # "ga" or a baseline name
    dataset: str
    dataset_hash: str
    seed: int | None
    # GA parameters (blank for baselines)
    population_size: int | None = None
    generations: int | None = None
    crossover_rate: float | None = None
    mutation_rate: float | None = None
    elite_count: int | None = None
    tournament_size: int | None = None
    crossover_type: str | None = None
    repair: bool | None = None
    repair_mode: str | None = None
    mutation_ops: int | None = None
    # outcome
    initial_penalty: float = 0.0
    final_penalty: float = 0.0
    final_fitness: float = 0.0
    hard_violations: int = 0
    valid: bool = True
    consecutive: int = 0
    short_gaps: int = 0
    distribution: int = 0
    slot_preference: int = 0
    room_utilization: float = 0.0
    generations_run: int | None = None
    stopped_by: str | None = None
    runtime_seconds: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def columns() -> list[str]:
        return [f.name for f in fields(RunRecord)]


def _outcome(ev) -> dict:
    return {
        "final_penalty": ev.penalty,
        "final_fitness": ev.fitness,
        "hard_violations": ev.hard_violations,
        "valid": ev.hard_violations == 0,
        "consecutive": ev.consecutive,
        "short_gaps": ev.short_gaps,
        "distribution": ev.distribution,
        "slot_preference": ev.slot_preference,
        "room_utilization": ev.room_utilization,
    }


def ga_record(res: GAResult, *, run_id: str, experiment: str, config: str, dataset: str, dataset_hash: str, mutation_ops: int) -> RunRecord:
    p = res.params
    return RunRecord(
        run_id=run_id, experiment=experiment, config=config, method="ga",
        dataset=dataset, dataset_hash=dataset_hash, seed=p.seed,
        population_size=p.population_size, generations=p.generations,
        crossover_rate=p.crossover_rate, mutation_rate=p.mutation_rate,
        elite_count=p.elite_count, tournament_size=p.tournament_size,
        crossover_type=p.crossover_type, repair=p.repair, repair_mode=p.repair_mode,
        mutation_ops=mutation_ops,
        initial_penalty=res.initial_penalty,
        generations_run=res.generations_run, stopped_by=res.stopped_by,
        runtime_seconds=res.runtime_seconds,
        **_outcome(res.evaluation),
    )


def baseline_record(res: BaselineResult, *, run_id: str, experiment: str, dataset: str, dataset_hash: str) -> RunRecord:
    ev = res.evaluation
    return RunRecord(
        run_id=run_id, experiment=experiment, config=res.name, method=res.name,
        dataset=dataset, dataset_hash=dataset_hash, seed=res.seed,
        initial_penalty=ev.penalty, runtime_seconds=res.runtime_seconds,
        **_outcome(ev),
    )
