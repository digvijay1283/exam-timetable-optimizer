from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Exam(Base):
    __tablename__ = "exam"
    __table_args__ = (UniqueConstraint("session_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str]  # exam_id from the CSV, e.g. EXM001
    subject_code: Mapped[str]
    subject_name: Mapped[str]
    department: Mapped[str]
    semester: Mapped[str]
    duration_minutes: Mapped[int]
    student_count: Mapped[int]
    exam_type: Mapped[str]
    priority: Mapped[int] = mapped_column(default=0)
