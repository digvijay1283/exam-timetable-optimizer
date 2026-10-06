from datetime import datetime

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class Timetable(Base):
    __tablename__ = "timetable"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("optimization_run.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str]
    fitness: Mapped[float]
    penalty: Mapped[float]
    hard_violations: Mapped[int]
    status: Mapped[str]  # draft | approved | superseded | infeasible
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)  # per-constraint penalty components
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class TimetableEntry(Base):
    __tablename__ = "timetable_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    timetable_id: Mapped[int] = mapped_column(ForeignKey("timetable.id", ondelete="CASCADE"), index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exam.id", ondelete="CASCADE"))
    slot_id: Mapped[int] = mapped_column(ForeignKey("slot.id", ondelete="CASCADE"))
    room_id: Mapped[int] = mapped_column(ForeignKey("room.id", ondelete="CASCADE"))
