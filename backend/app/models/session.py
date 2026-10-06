from datetime import date, datetime

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class ExamSession(Base):
    """An examination session (PRD FR-01). Named ExamSession to avoid clashing with a DB session."""

    __tablename__ = "session"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    academic_year: Mapped[str]
    semester: Mapped[str]
    start_date: Mapped[date]
    end_date: Mapped[date]
    working_days: Mapped[list[int]] = mapped_column(JSON)  # Monday = 0
    slots_per_day: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
