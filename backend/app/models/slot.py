from datetime import date, time

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Slot(Base):
    __tablename__ = "slot"
    __table_args__ = (UniqueConstraint("session_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str]  # slot_id, e.g. S03
    date: Mapped[date]
    start_time: Mapped[time]
    end_time: Mapped[time]
    slot_number: Mapped[int] = mapped_column(default=0)
    pref_penalty: Mapped[int] = mapped_column(default=0)
