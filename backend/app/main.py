"""FastAPI application factory.

    uvicorn app.main:create_app --factory --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import update

from app import models as orm
from app.api import experiments, exams, optimization, rooms, sessions, slots, students, timetables
from app.database.session import default_database_url, init_db, make_engine, make_session_factory
from app.services.experiment_service import FIGURES_DIR
from app.services.job_service import JobRunner


def create_app(database_url: str | None = None, job_mode: str = "process") -> FastAPI:
    url = database_url or default_database_url()
    engine = make_engine(url)
    session_factory = make_session_factory(engine)
    jobs = JobRunner(url, mode=job_mode)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        # Runs that were queued or running when the server last stopped can never finish.
        with session_factory() as db:
            db.execute(
                update(orm.OptimizationRun)
                .where(orm.OptimizationRun.status.in_(["queued", "running"]))
                .values(status="failed", error="interrupted by server restart", finished_at=datetime.now(timezone.utc))
            )
            db.commit()
        yield
        jobs.shutdown()
        engine.dispose()

    app = FastAPI(
        title="Examination Timetable Optimizer",
        description="Constraint-aware genetic algorithm for examination timetable generation.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.session_factory = session_factory
    app.state.jobs = jobs
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/api/experiments/figures", StaticFiles(directory=FIGURES_DIR), name="experiment-figures")
    for module in (sessions, exams, students, rooms, slots, optimization, timetables, experiments):
        app.include_router(module.router)

    @app.get("/api/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    return app
