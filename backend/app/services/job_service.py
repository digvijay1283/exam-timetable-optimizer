"""Optimization jobs. The GA is CPU-bound, so it runs in a separate process and reports progress
through the database (docs/SPEC_DECISIONS.md section 12); the API only reads the run row."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import update

from app import models as orm
from app.core.config import Weights
from app.database.session import make_engine, make_session_factory
from app.optimization.baseline import run_baseline
from app.optimization.context import build_context
from app.optimization.genetic_algorithm import GenerationStats, run_ga
from app.optimization.params import GAParams
from app.services.dataset_service import load_dataset_from_db
from app.services.timetable_service import persist_chromosome

PROGRESS_EVERY = 3  # generations between progress writes


def dataset_hash(dataset) -> str:
    """Fingerprint of the in-database input data, stored with the run."""
    digest = hashlib.sha256()
    digest.update(json.dumps(
        [[e.exam_id, e.duration_minutes, e.student_count, e.exam_type, e.priority] for e in dataset.exams]
        + [[r.room_id, r.capacity, r.room_type, r.available] for r in dataset.rooms]
        + [[s.slot_id, str(s.date), str(s.start_time), str(s.end_time)] for s in dataset.slots]
        + sorted([list(p) for p in dataset.enrollments]),
    ).encode())
    return digest.hexdigest()[:16]


def _stats_dict(s: GenerationStats) -> dict:
    return {
        "generation": s.generation, "best_penalty": s.best_penalty, "mean_penalty": s.mean_penalty,
        "worst_penalty": s.worst_penalty, "best_hard": s.best_hard,
        "feasible_fraction": s.feasible_fraction, "best_fitness": s.best_fitness,
    }


def execute_run(database_url: str, run_id: int) -> None:
    """Run one optimization to completion and store its result. Safe to call in a worker process."""
    engine = make_engine(database_url)
    factory = make_session_factory(engine)
    try:
        with factory() as db:
            run = db.get(orm.OptimizationRun, run_id)
            try:
                _execute(db, run)
            except Exception as exc:  # recorded on the run, never raised into the pool
                db.rollback()
                db.execute(
                    update(orm.OptimizationRun)
                    .where(orm.OptimizationRun.id == run_id)
                    .values(status="failed", error=f"{type(exc).__name__}: {exc}"[:2000],
                            finished_at=datetime.now(timezone.utc))
                )
                db.commit()
    finally:
        engine.dispose()


def _execute(db, run: orm.OptimizationRun) -> None:
    run.status = "running"
    db.commit()
    loaded = load_dataset_from_db(db, run.session_id)
    ctx = build_context(loaded.dataset, Weights(**run.weights))
    run.dataset_hash = dataset_hash(loaded.dataset)

    if run.method == "ga":
        params = GAParams(**run.params)
        run.total_generations = params.generations
        db.commit()
        history: list[dict] = []

        def on_progress(stats: GenerationStats) -> None:
            history.append(_stats_dict(stats))
            if stats.generation % PROGRESS_EVERY == 0 or stats.generation == params.generations:
                run.current_generation = stats.generation
                run.best_penalty = stats.best_penalty
                run.best_fitness = stats.best_fitness
                run.history = list(history)
                db.commit()

        result = run_ga(ctx, params, on_progress)
        chromosome, evaluation = result.best, result.evaluation
        run.initial_penalty = result.initial_penalty
        run.generations_run = result.generations_run
        run.stopped_by = result.stopped_by
        run.runtime_seconds = result.runtime_seconds
        run.history = [_stats_dict(s) for s in result.history]
        run.current_generation = result.generations_run
        name = f"GA run #{run.id} (seed {params.seed})"
    else:
        result = run_baseline(ctx, run.method, run.seed)
        chromosome, evaluation = result.chromosome, result.evaluation
        run.initial_penalty = evaluation.penalty
        run.runtime_seconds = result.runtime_seconds
        run.generations_run = 0
        run.stopped_by = "baseline"
        name = f"{run.method} baseline (run #{run.id})"

    timetable = persist_chromosome(db, run.session_id, run.id, name, loaded, ctx, chromosome, evaluation)
    run.timetable_id = timetable.id
    run.best_penalty = evaluation.penalty
    run.best_fitness = evaluation.fitness
    run.hard_violations = evaluation.hard_violations
    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    db.commit()


class JobRunner:
    """Runs optimizations either in a process pool (normal use) or inline (tests, tiny jobs)."""

    def __init__(self, database_url: str, mode: str = "process", max_workers: int = 2):
        if mode not in ("process", "inline"):
            raise ValueError("mode must be 'process' or 'inline'")
        self.database_url = database_url
        self.mode = mode
        self._pool = ProcessPoolExecutor(max_workers=max_workers) if mode == "process" else None

    def submit(self, run_id: int) -> None:
        if self._pool is None:
            execute_run(self.database_url, run_id)
        else:
            self._pool.submit(execute_run, self.database_url, run_id)

    def shutdown(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
