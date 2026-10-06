from datetime import datetime

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class OptimizationRun(Base):
    """One GA (or baseline) run, with everything needed to reproduce it and live progress."""

    __tablename__ = "optimization_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(default="ga")  # ga | greedy | greedy_cost_aware | ...
    status: Mapped[str] = mapped_column(default="queued")  # queued | running | completed | failed
    # reproducibility
    seed: Mapped[int | None] = mapped_column(nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)  # GAParams
    weights: Mapped[dict] = mapped_column(JSON, default=dict)
    dataset_hash: Mapped[str] = mapped_column(default="")
    # live progress
    current_generation: Mapped[int] = mapped_column(default=0)
    total_generations: Mapped[int] = mapped_column(default=0)
    history: Mapped[list] = mapped_column(JSON, default=list)  # per-generation stats
    # outcome
    initial_penalty: Mapped[float | None] = mapped_column(nullable=True)
    best_penalty: Mapped[float | None] = mapped_column(nullable=True)
    best_fitness: Mapped[float | None] = mapped_column(nullable=True)
    hard_violations: Mapped[int | None] = mapped_column(nullable=True)
    generations_run: Mapped[int | None] = mapped_column(nullable=True)
    stopped_by: Mapped[str | None] = mapped_column(nullable=True)
    runtime_seconds: Mapped[float | None] = mapped_column(nullable=True)
    timetable_id: Mapped[int | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
