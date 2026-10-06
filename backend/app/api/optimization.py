from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import models as orm
from app.api.deps import fail, get_db, get_jobs, session_or_404
from app.core.config import Weights
from app.optimization.context import build_context
from app.schemas.optimization import BaselineRequest, GAParamsIn, ProgressOut, RunOut, RunRequest, WeightsIn
from app.services.dataset_service import load_dataset_from_db
from app.services.feasibility_service import check_feasibility
from app.services.job_service import JobRunner

router = APIRouter(tags=["optimization"])


def _precheck(db: DbSession, session_id: int, weights: WeightsIn) -> None:
    """Block runs on empty or provably infeasible data with readable messages (SPEC section 11)."""
    dataset = load_dataset_from_db(db, session_id).dataset
    missing = [
        f"no {name} imported yet"
        for name, rows in (("exams", dataset.exams), ("rooms", dataset.rooms), ("slots", dataset.slots)) if not rows
    ]
    if missing:
        raise HTTPException(422, detail={"errors": missing, "warnings": []})
    report = check_feasibility(build_context(dataset, Weights(**weights.model_dump())))
    if not report.ok:
        raise fail(report)


def _start(db: DbSession, jobs: JobRunner, run: orm.OptimizationRun) -> orm.OptimizationRun:
    db.add(run)
    db.commit()
    jobs.submit(run.id)
    db.refresh(run)
    return run


@router.post("/api/optimization/run", response_model=RunOut, status_code=202)
def start_run(body: RunRequest, db: DbSession = Depends(get_db), jobs: JobRunner = Depends(get_jobs)):
    session_or_404(db, body.session_id)
    try:
        params = body.params.to_params()
    except ValueError as exc:
        raise HTTPException(422, detail={"errors": [str(exc)], "warnings": []})
    _precheck(db, body.session_id, body.weights)
    run = orm.OptimizationRun(
        session_id=body.session_id, method=body.method, seed=body.params.seed,
        params=asdict(params), weights=body.weights.model_dump(),
        total_generations=params.generations if body.method == "ga" else 0,
    )
    return _start(db, jobs, run)


@router.post("/api/baseline/run", response_model=RunOut, status_code=202)
def start_baseline(body: BaselineRequest, db: DbSession = Depends(get_db), jobs: JobRunner = Depends(get_jobs)):
    session_or_404(db, body.session_id)
    _precheck(db, body.session_id, body.weights)
    run = orm.OptimizationRun(
        session_id=body.session_id, method=body.method, seed=body.seed,
        params=GAParamsIn(seed=body.seed).model_dump(), weights=body.weights.model_dump(),
    )
    return _start(db, jobs, run)


def _run_or_404(db: DbSession, run_id: int) -> orm.OptimizationRun:
    run = db.get(orm.OptimizationRun, run_id)
    if run is None:
        raise HTTPException(404, f"run {run_id} not found")
    return run


@router.get("/api/optimization/{run_id}", response_model=RunOut)
def get_run(run_id: int, db: DbSession = Depends(get_db)):
    return _run_or_404(db, run_id)


@router.get("/api/optimization/{run_id}/progress", response_model=ProgressOut)
def get_progress(run_id: int, db: DbSession = Depends(get_db)):
    run = _run_or_404(db, run_id)
    return ProgressOut(
        run_id=run.id, status=run.status, current_generation=run.current_generation,
        total_generations=run.total_generations, best_penalty=run.best_penalty,
        best_fitness=run.best_fitness, timetable_id=run.timetable_id, error=run.error, history=run.history or [],
    )


@router.get("/api/sessions/{session_id}/runs", response_model=list[RunOut])
def list_runs(session_id: int, db: DbSession = Depends(get_db)):
    session_or_404(db, session_id)
    return db.scalars(
        select(orm.OptimizationRun).where(orm.OptimizationRun.session_id == session_id).order_by(orm.OptimizationRun.id.desc())
    ).all()
