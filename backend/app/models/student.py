from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Student(Base):
    __tablename__ = "student"
    __table_args__ = (UniqueConstraint("session_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str]  # student_id from the CSV
    department: Mapped[str] = mapped_column(default="")
    semester: Mapped[str] = mapped_column(default="")
